import math
from typing import List
from src.models.events import NoteEvent

class TabRenderer:
    STRING_ORDER = [3, 2, 1, 0]
    STRING_NAMES = {3: "G", 2: "D", 1: "A", 0: "E"}

    @staticmethod
    def render_tab(events: List[NoteEvent], bpm: float) -> str:
        if not events:
            return "⚠️ 렌더링할 유효한 노트 이벤트가 없습니다."

        output_lines = []
        is_fallback = bpm <= 0
        
        if is_fallback:
            output_lines.append(f"🎸 Unquantized Bass Tab (Fallback Rendering - Time Based)\n")
        else:
            output_lines.append(f"🎸 Quantized Bass Tab (BPM: {round(bpm)})\n")

        # 양자화된 시간 및 지속 길이를 격자 인덱스로 투영
        virtual_grids = []
        durations_in_grids = []
        
        for e in events:
            if is_fallback:
                grid = int(e.time * 10)
                dur_grid = max(1, int(e.duration * 10))
            else:
                grid = e.grid_index if e.grid_index is not None else int(e.time * 10)
                grid_interval = (60.0 / bpm) / 4 if bpm > 0 else 0.1
                q_dur = e.quantized_duration if e.quantized_duration else e.duration
                dur_grid = max(1, int(round(q_dur / grid_interval)))
                
            virtual_grids.append(grid)
            durations_in_grids.append(dur_grid)
            
        # 렌더링할 총 마디(Measure) 수 계산
        max_grid = 0
        for g, d in zip(virtual_grids, durations_in_grids):
            max_grid = max(max_grid, g + d)
            
        total_measures = math.ceil((max_grid + 1) / 16)
        total_measures = max(1, total_measures)

        # 3글자 단위 빈 격자판 초기화
        tab_buffer = {
            s_idx: [["---" for _ in range(16)] for _ in range(total_measures)] 
            for s_idx in TabRenderer.STRING_ORDER
        }

        for idx, event in enumerate(events):
            if event.string_idx is None or event.fret is None:
                continue
            
            start_grid = virtual_grids[idx]
            dur_grid = durations_in_grids[idx]
            s_idx = event.string_idx

            m_idx = start_grid // 16
            step_idx = start_grid % 16
            
            # 1. Onset 타격음 렌더링 (숫자 배치)
            if m_idx < total_measures:
                fret_str = str(event.fret)
                if len(fret_str) == 1:
                    cell = f"-{fret_str}-"
                elif len(fret_str) == 2:
                    cell = f"{fret_str}-"
                else:
                    cell = fret_str[:3]
                    
                # Monophonic Enforcer 덕분에 무조건 덮어쓰기 가능 (충돌 해결 완료)
                tab_buffer[s_idx][m_idx][step_idx] = cell.ljust(3, "-")

            # 2. Duration 서스테인(~) 기호 렌더링
            for d in range(1, dur_grid):
                sus_grid = start_grid + d
                sus_m_idx = sus_grid // 16
                sus_step_idx = sus_grid % 16
                
                if sus_m_idx < total_measures:
                    # 해당 격자가 비어있을 때만 서스테인 기호 표기 (다음 노트 침범 방지)
                    if tab_buffer[s_idx][sus_m_idx][sus_step_idx] == "---":
                        tab_buffer[s_idx][sus_m_idx][sus_step_idx] = "~~~"

        # 최종 텍스트 병합 출력
        measures_per_line = 2 
        for line_start in range(0, total_measures, measures_per_line):
            line_end = min(line_start + measures_per_line, total_measures)
            
            for s_idx in TabRenderer.STRING_ORDER:
                row_str = f"{TabRenderer.STRING_NAMES[s_idx]} |"
                for m_idx in range(line_start, line_end):
                    measure_str = "".join(tab_buffer[s_idx][m_idx])
                    row_str += f"{measure_str}|"
                output_lines.append(row_str)
            output_lines.append("") # 줄바꿈

        return "\n".join(output_lines)
