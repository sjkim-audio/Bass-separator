import librosa
from typing import Tuple, List

from src.models.events import NoteEvent
from src.transcription.tracker import get_f0_crepe_robust
from src.transcription.parser import PitchParser
from src.transcription.fingering import ViterbiSmartFingering
from src.transcription.quantization import RhythmicQuantizer
from src.renderers.tab_renderer import TabRenderer

def run_transcription_pipeline(bass_path: str, bassless_path: str) -> Tuple[str, float, List[NoteEvent]]:
    """
    [Phase 7] E2E 도메인 파이프라인: 다중 트랙 기반 템포 추출 및 양자화 체이닝
    """
    sr = 16000
    hop_length = 160
    
    # 1. 오디오 멀티 로드 (피치 추적용 Bass, 템포 추적용 MR)
    y_bass, _ = librosa.load(bass_path, sr=sr, mono=True)
    y_bassless, _ = librosa.load(bassless_path, sr=sr, mono=True)
    
    # 2. 피치 및 신뢰도 추적 (CREPE)
    # 🔴 [수정] 튜닝 결과에 따라 onset_mask 반환값을 추가로 받음
    f0_array, confidence_array, onset_mask = get_f0_crepe_robust(y_bass, sr=sr, hop_length=hop_length)

    # 3. 이벤트 파싱 (기계적 결함 1차 필터링)
    parser = PitchParser(sr=sr, hop_length=hop_length)
    # 🔴 [수정] onset_mask를 파서에 주입하여 연타 분할 기능 활성화
    raw_events = parser.parse_f0_to_events(f0_array, confidence_array, onset_mask)
    
    # 4. 최적 운지법 계산 (Viterbi HMM)
    viterbi_decoder = ViterbiSmartFingering()
    fingered_events = viterbi_decoder.decode(raw_events, parser.get_fret_candidates)
    
    # 5. 리듬 양자화 (Global Tempo Map 기반)
    quantizer = RhythmicQuantizer(sr=sr, hop_length=hop_length)
    # Bassless MR을 1순위로, Bass를 Fallback으로 전달
    bpm = quantizer.estimate_bpm_and_grid(y_bassless, y_bass)
    quantized_events = quantizer.quantize_events(fingered_events)
    
    # 6. ASCII 타브 렌더링 (Sustain 시각화 포함)
    ascii_tab = TabRenderer.render_tab(quantized_events, bpm)
    
    return ascii_tab, bpm, quantized_events
