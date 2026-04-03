import librosa
from typing import Tuple, List, Optional

from src.models.events import NoteEvent
from src.transcription.tracker import get_f0_crepe_robust
from src.transcription.parser import PitchParser
from src.transcription.fingering import ViterbiSmartFingering
from src.transcription.quantization import RhythmicQuantizer
from src.renderers.tab_renderer import TabRenderer

def run_transcription_pipeline(bass_path: str, bassless_path: Optional[str] = None) -> Tuple[str, float, List[NoteEvent]]:
    sr = 16000
    hop_length = 160
    
    y_bass, _ = librosa.load(bass_path, sr=sr, mono=True)
    y_bassless = None
    
    if bassless_path is not None and bassless_path != bass_path:
        y_bassless, _ = librosa.load(bassless_path, sr=sr, mono=True)
    
    f0_array, confidence_array, onset_mask = get_f0_crepe_robust(y_bass, sr=sr, hop_length=hop_length)

    parser = PitchParser(sr=sr, hop_length=hop_length)
    raw_events = parser.parse_f0_to_events(f0_array, confidence_array, onset_mask)
    
    viterbi_decoder = ViterbiSmartFingering()
    fingered_events = viterbi_decoder.decode(raw_events, parser.get_fret_candidates)
    
    quantizer = RhythmicQuantizer(sr=sr, hop_length=hop_length)
    bpm = quantizer.estimate_bpm_and_grid(y_bassless, y_bass)
    quantized_events = quantizer.quantize_events(fingered_events)
    
    ascii_tab = TabRenderer.render_tab(quantized_events, bpm)
    
    return ascii_tab, bpm, quantized_events