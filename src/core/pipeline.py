# src/core/pipeline.py (신규 작성)
import librosa
from typing import Tuple, List

from models.events import NoteEvent
from transcription.tracker import get_f0_crepe_robust
from transcription.parser import parse_f0_to_events
from transcription.fingering import FingeringOptimizer
from transcription.quantization import RhythmicQuantizer
from renderers.tab_renderer import TabRenderer

def run_transcription_pipeline(audio_path: str) -> Tuple[str, float, List[NoteEvent]]:
    """
    [Fix] E2E 도메인 파이프라인: 분리된 오디오를 입력받아 최종 데이터를 반환하는 순수 함수.
    """
    sr = 16000
    hop_length = 160
    
    # 1. 오디오 로드
    y, _ = librosa.load(audio_path, sr=sr, mono=True)
    
    # 2. 피치 및 신뢰도 추적 (CREPE)
    f0_array, confidence_array = get_f0_crepe_robust(y, sr=sr, hop_length=hop_length)
    
    # 3. 이벤트 파싱 (Unquantized)
    # Parser가 confidence_array를 받아 NoteEvent.confidence에 할당한다고 가정
    raw_events = parse_f0_to_events(f0_array, confidence_array, hop_length, sr)
    
    # 4. 최적 운지법 계산 (Viterbi)
    optimizer = FingeringOptimizer()
    fingered_events = optimizer.optimize(raw_events)
    
    # 5. 리듬 양자화 (BPM 추정 포함)
    quantizer = RhythmicQuantizer(sr=sr, hop_length=hop_length)
    bpm = quantizer.estimate_bpm_and_grid(y)
    quantized_events = quantizer.quantize_events(fingered_events)
    
    # 6. ASCII 타브 렌더링
    ascii_tab = TabRenderer.render_tab(quantized_events, bpm)
    
    return ascii_tab, bpm, quantized_events
