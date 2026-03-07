import math
from typing import List
from models.events import NoteEvent

class TabRenderer:
    STRING_ORDER = [3, 2, 1, 0]
    STRING_NAMES = {3: "G", 2: "D", 1: "A", 0: "E"}

    @staticmethod
    def render_quantized_tab(events: List[NoteEvent], bpm: float) -> str:
        if not events:
            return "⚠️ 렌더링할 유효한 노트 이벤트가 없습니다."

        # 문자열 누적을 위한 리스트 (String concatenation 최적화)
        output_lines = []
        output_lines.append(f"🎸 Quantized Bass Tab (BPM: {round(bpm)})\n")

        valid_grids = [e.grid_index for e in events if e.grid_index is not None]
        if not valid_grids:
            return "⚠️ 양자화된 격자 정보가 없습니다. Quantizer 로직을 확인하십시오."
            
        max_grid = max(valid_grids)
        total_measures = math.ceil((max_grid + 1) / 16)
        if total_measures == 0:
            total_measures = 1

        tab_buffer = {
            s_idx: [["---" for _ in range(16)] for _ in range(total_measures)] 
            for s_idx in TabRenderer.STRING_ORDER
        }

        for event in events:
            if event.grid_index is None or event.string_idx is None or event.fret is None:
                continue
            
            m_idx = event.grid_index // 16
            step_idx = event.grid_index % 16
            s_idx = event.string_idx

            if s_idx not in tab_buffer:
                continue 

            fret_str = str(event.fret)
            if len(fret_str) == 1:
                cell = f"-{fret_str}-"
            elif len(fret_str) == 2:
                cell = f"{fret_str}-"
            else:
                cell = fret_str[:3]

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
