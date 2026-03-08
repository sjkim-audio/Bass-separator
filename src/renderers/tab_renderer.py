import math
from typing import List
from models.events import NoteEvent

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

        # [Fix] Fallback 모드 시 물리적 시간을 가상의 그리드 인덱스로 변환 (100ms 단위)
        virtual_grids = []
        for e in events:
            if is_fallback:
                grid = int(e.time * 10) # 1초 = 10칸
            else:
                grid = e.grid_index if e.grid_index is not None else int(e.time * 10)
            virtual_grids.append(grid)
            
        max_grid = max(virtual_grids) if virtual_grids else 0
        total_measures = math.ceil((max_grid + 1) / 16)
        total_measures = max(1, total_measures)

        tab_buffer = {
            s_idx: [["---" for _ in range(16)] for _ in range(total_measures)] 
            for s_idx in TabRenderer.STRING_ORDER
        }

        for idx, event in enumerate(events):
            if event.string_idx is None or event.fret is None:
                continue
            
            grid_pos = virtual_grids[idx]
            m_idx = grid_pos // 16
            step_idx = grid_pos % 16
            s_idx = event.string_idx

            if s_idx not in tab_buffer:
                continue 

            new_fret_str = str(event.fret)
            existing_cell = tab_buffer[s_idx][m_idx][step_idx]

            # [교정] 충돌 감지 및 병합 로직
            if existing_cell == "---":
                if len(new_fret_str) == 1:
                    cell = f"-{new_fret_str}-"
                elif len(new_fret_str) == 2:
                    cell = f"{new_fret_str}-"
                else:
                    cell = new_fret_str[:3]
            else:
                # 기존 데이터가 존재할 경우 (Collision)
                # 하이픈을 제거하고 새로운 노트를 이어붙임 (예: "-5-" + "7" -> "57-")
                prev_fret = existing_cell.replace("-", "")
                merged = f"{prev_fret}{new_fret_str}"
                
                # ASCII 셀 크기(3자) 강제 맞춤
                if len(merged) <= 3:
                    cell = merged.ljust(3, "-")
                else:
                    cell = merged[:3] # 공간 부족 시 강제 절삭

            tab_buffer[s_idx][m_idx][step_idx] = cell

        measures_per_line = 2 
        for line_start in range(0, total_measures, measures_per_line):
            line_end = min(line_start + measures_per_line, total_measures)
            
            for s_idx in TabRenderer.STRING_ORDER:
                row_str = f"{TabRenderer.STRING_NAMES[s_idx]} |"
                for m_idx in range(line_start, line_end):
                    measure_str = "".join(tab_buffer[s_idx][m_idx])
                    row_str += f"{measure_str}|"
                output_lines.append(row_str)
            output_lines.append("") # 개행

        return "\n".join(output_lines)
