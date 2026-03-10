# src/core/pipeline.py
import librosa
from typing import Tuple, List

from src.models.events import NoteEvent
from src.transcription.tracker import get_f0_crepe_robust
from src.transcription.parser import PitchParser
from src.transcription.fingering import ViterbiSmartFingering
from src.transcription.quantization import RhythmicQuantizer
from src.renderers.tab_renderer import TabRenderer

def run_transcription_pipeline(audio_path: str) -> Tuple[str, float, List[NoteEvent]]:
    """
    [Fix] E2E 도메인 파이프라인: 객체 지향적 모듈 호출 및 데이터 체이닝 복원
    """
    sr = 16000
    hop_length = 160
    
    # 1. 오디오 로드
    y, _ = librosa.load(audio_path, sr=sr, mono=True)
    
    # 2. 피치 및 신뢰도 추적 (CREPE)
    f0_array, confidence_array = get_f0_crepe_robust(y, sr=sr, hop_length=hop_length)
    
    # 3. 이벤트 파싱 (PitchParser 인스턴스화)
    parser = PitchParser(sr=sr, hop_length=hop_length)
    raw_events = parser.parse_f0_to_events(f0_array, confidence_array)
    
    # 4. 최적 운지법 계산 (ViterbiSmartFingering 인스턴스화 및 decode 호출)
    viterbi_decoder = ViterbiSmartFingering()
    fingered_events = viterbi_decoder.decode(raw_events, parser.get_fret_candidates)
    
    # 5. 리듬 양자화 (BPM 추정 포함)
    quantizer = RhythmicQuantizer(sr=sr, hop_length=hop_length)
    bpm = quantizer.estimate_bpm_and_grid(y)
    quantized_events = quantizer.quantize_events(fingered_events)
    
    # 6. ASCII 타브 렌더링
    ascii_tab = TabRenderer.render_tab(quantized_events, bpm)
    
    return ascii_tab, bpm, quantized_events
