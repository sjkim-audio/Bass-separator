import math
from typing import List
from models.events import NoteEvent

class TabRenderer:
    """
    불변 객체인 NoteEvent 리스트를 입력받아 16분음표 단위의 ASCII 타브 악보를 렌더링하는 클래스.
    """
    # parser.py의 tuning [28(E), 33(A), 38(D), 43(G)]에 대응하는 인덱스.
    # 출력 시 베이스 타브 악보의 표준 규격에 따라 G(3) -> D(2) -> A(1) -> E(0) 순으로 렌더링.
    STRING_ORDER = [3, 2, 1, 0]
    STRING_NAMES = {3: "G", 2: "D", 1: "A", 0: "E"}

    @staticmethod
    def render_quantized_tab(events: List[NoteEvent], bpm: float):
        if not events:
            print("⚠️ 렌더링할 유효한 노트 이벤트가 없습니다.")
            return

        print(f"🎸 Quantized Bass Tab (BPM: {round(bpm)})")
        print()

        # 양자화된 격자(Grid) 정보를 기반으로 총 필요 마디(Measure) 수 산출
        valid_grids = [e.grid_index for e in events if e.grid_index is not None]
        if not valid_grids:
            print("⚠️ 양자화된 격자 정보가 없습니다. Quantizer 로직을 확인하십시오.")
            return
            
        max_grid = max(valid_grids)
        total_measures = math.ceil((max_grid + 1) / 16)
        if total_measures == 0:
            total_measures = 1

        # 타브 버퍼 초기화 (4현 x 마디 수 x 16격자). 기본 16분음표 길이는 3칸('---')으로 고정.
        tab_buffer = {
            s_idx: [["---" for _ in range(16)] for _ in range(total_measures)] 
            for s_idx in TabRenderer.STRING_ORDER
        }

        # 이벤트 맵핑 (O(N) 복잡도)
        for event in events:
            if event.grid_index is None or event.string_idx is None or event.fret is None:
                continue
            
            m_idx = event.grid_index // 16
            step_idx = event.grid_index % 16
            s_idx = event.string_idx

            if s_idx not in tab_buffer:
                continue # 5현/6현 등 미지원 튜닝 예외 처리

            fret_str = str(event.fret)
            
            # 셀 포맷팅: 1자리 프렛은 '-0-', 2자리 프렛은 '12-' 형태를 유지하여 시각적 격자 정렬
            if len(fret_str) == 1:
                cell = f"-{fret_str}-"
            elif len(fret_str) == 2:
                cell = f"{fret_str}-"
            else:
                cell = fret_str[:3] # 3자리 이상 예외 발생 시 강제 절삭

            tab_buffer[s_idx][m_idx][step_idx] = cell

        # 가독성을 위해 2마디 단위(32격자)로 개행하며 콘솔 출력
        measures_per_line = 2 
        for line_start in range(0, total_measures, measures_per_line):
            line_end = min(line_start + measures_per_line, total_measures)
            
            for s_idx in TabRenderer.STRING_ORDER:
                row_str = f"{TabRenderer.STRING_NAMES[s_idx]} |"
                for m_idx in range(line_start, line_end):
                    measure_str = "".join(tab_buffer[s_idx][m_idx])
                    row_str += f"{measure_str}|"
                print(row_str)
            print() # 시스템 줄바꿈 간격 확보
