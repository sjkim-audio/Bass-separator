import os
import numpy as np
import librosa
import scipy.signal
import traceback
from typing import List, Dict

import museval
import mir_eval
import pretty_midi

from src.models.events import NoteEvent

def align_audio(ref: np.ndarray, est: np.ndarray, sr: int = 44100):
    max_len = sr * 30  
    ref_mono = np.mean(ref, axis=0) if ref.ndim > 1 else ref
    est_mono = np.mean(est, axis=0) if est.ndim > 1 else est
    
    correlation = scipy.signal.correlate(ref_mono[:max_len], est_mono[:max_len], mode='full')
    lag = int(np.argmax(correlation) - (len(est_mono[:max_len]) - 1))
    
    if lag > 0:
        est = est[:, lag:]
        ref = ref[:, :-lag]
    elif lag < 0:
        lag = abs(lag)
        est = est[:, :-lag]
        ref = ref[:, lag:]
        
    return ref, est

def evaluate_separation(reference_path: str, estimated_path: str, align: bool = True) -> dict:
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _ = librosa.load(estimated_path, sr=sr, mono=False)

    if ref.ndim == 1: ref = ref[np.newaxis, :]
    if est.ndim == 1: est = est[np.newaxis, :]

    min_len = min(ref.shape[1], est.shape[1])
    ref = ref[:, :min_len]
    est = est[:, :min_len]

    if align:
        ref, est = align_audio(ref, est, sr)

    ref_eval = ref.T[np.newaxis, :, :]
    est_eval = est.T[np.newaxis, :, :]

    sdr, isr, sir, sar, _ = museval.eval_bss_v4(ref_eval, est_eval, win=sr)

    return {
        "SDR": sdr.squeeze(),
        "SIR": sir.squeeze(),
        "SAR": sar.squeeze(),
        "sr": sr,
        "hop_sec": 1.0
    }

def run_separation_evaluation(ref_path: str, est_path: str, align: bool = True) -> dict:
    print(f"📊 [Separation] Processing: {os.path.basename(est_path)}")
    try:
        metrics = evaluate_separation(ref_path, est_path, align=align)
        print("-" * 40)
        print("🔹 Separation Summary (BSSEval v4)")
        print("-" * 40)
        print(f"✅ Median SDR: {np.nanmedian(metrics['SDR']):.2f} dB")
        print(f"✅ Median SIR: {np.nanmedian(metrics['SIR']):.2f} dB")
        print(f"✅ Median SAR: {np.nanmedian(metrics['SAR']):.2f} dB")
        print("-" * 40)
        return metrics
    except Exception as e:
        print(f"❌ Error during separation evaluation: {e}")
        traceback.print_exc()
        return {}

class TranscriptionEvaluator:
    @staticmethod
    def load_midi_to_mir_eval(midi_path: str):
        pm = pretty_midi.PrettyMIDI(midi_path)
        intervals, pitches = [], []
        
        for instrument in pm.instruments:
            if not instrument.is_drum:
                for note in instrument.notes:
                    intervals.append([note.start, note.end])
                    pitches.append(pretty_midi.note_number_to_hz(note.pitch))
                    
        if not intervals:
            return np.empty((0, 2)), np.empty((0,))
        return np.array(intervals), np.array(pitches)

    @staticmethod
    def _events_to_mir_eval(events: List[NoteEvent], use_quantized: bool = False):
        intervals, pitches = [], []
        for e in events:
            if use_quantized and e.quantized_time is not None and e.quantized_duration is not None:
                onset, offset = e.quantized_time, e.quantized_time + e.quantized_duration
            else:
                onset = e.time
                offset = onset + (e.duration if e.duration > 0 else 0.05)
                
            intervals.append([onset, offset])
            pitches.append(librosa.midi_to_hz(e.midi_note))
            
        if not intervals:
            return np.empty((0, 2)), np.empty((0,))
        return np.array(intervals), np.array(pitches)

    @staticmethod
    def evaluate(ref_midi_path: str, est_events: List[NoteEvent], test_quantized: bool = False) -> Dict[str, float]:
        ref_intervals, ref_pitches = TranscriptionEvaluator.load_midi_to_mir_eval(ref_midi_path)
        est_intervals, est_pitches = TranscriptionEvaluator._events_to_mir_eval(est_events, use_quantized=test_quantized)
        
        if len(ref_intervals) == 0 and len(est_intervals) == 0:
            return {"Onset_F1": 1.0, "Onset_Pitch_F1": 1.0}
        elif len(ref_intervals) == 0 or len(est_intervals) == 0:
             return {"Onset_F1": 0.0, "Onset_Pitch_F1": 0.0}

        scores = mir_eval.transcription.evaluate(
            ref_intervals, ref_pitches, est_intervals, est_pitches,
            onset_tolerance=0.05, pitch_tolerance=50.0, offset_ratio=0.2, offset_min_tolerance=0.05
        )
        
        return {
            "Onset_Precision": round(scores['Precision_no_offset'], 4),
            "Onset_Recall": round(scores['Recall_no_offset'], 4),
            "Onset_F1": round(scores['F-measure_no_offset'], 4),
            "Onset_Pitch_Precision": round(scores['Precision'], 4),
            "Onset_Pitch_Recall": round(scores['Recall'], 4),
            "Onset_Pitch_F1": round(scores['F-measure'], 4)
        }

async def run_transcription_evaluation(ref_midi_path: str, audio_path: str, is_isolated: bool = False) -> dict:
    """
    [래퍼] 파이프라인을 구동하여 채보를 수행하고 정확도를 산출한다.
    is_isolated=True일 경우 무거운 Demucs 분리 과정을 생략하고 즉시 평가를 진행한다.
    """
    print(f"🎵 [Transcription] Processing Audio: {os.path.basename(audio_path)}")
    from src.core.pipeline import run_transcription_pipeline
    
    bass_path = audio_path
    bassless_path = None
    
    try:
        if not is_isolated:
            # 1. 믹스 음원일 경우 Demucs를 가동하여 스템 분리
            from src.core.demucs_runner import separate_and_generate_stems
            print("⏳ 믹스 음원이 감지되었습니다. Demucs 음원 분리를 먼저 수행합니다...")
            temp_out_dir = "outputs/eval_temp"
            bass_path, bassless_path = await separate_and_generate_stems(audio_path, output_dir=temp_out_dir)
        else:
            print("⚡ 단일 베이스 트랙(Isolated) 모드입니다. Demucs를 생략하고 즉시 채보를 시작합니다.")
            
        # 2. Phase 7 파이프라인 실행
        # (단일 베이스일 경우 bassless_path에 None이 유지되며, Quantizer 내부의 Fallback이 정상 작동함)
        _, _, quantized_events = run_transcription_pipeline(bass_path, bassless_path)
        
        # 3. 평가 진행 (현재는 Raw 이벤트 기준)
        metrics = TranscriptionEvaluator.evaluate(ref_midi_path, quantized_events, test_quantized=False)
        
        print("-" * 40)
        print("🔹 Transcription Summary (mir_eval)")
        print("-" * 40)
        print(f"✅ Onset-Pitch Precision : {metrics['Onset_Pitch_Precision'] * 100:.2f}%")
        print(f"✅ Onset-Pitch Recall    : {metrics['Onset_Pitch_Recall'] * 100:.2f}%")
        print(f"✅ Onset-Pitch F1-Score  : {metrics['Onset_Pitch_F1'] * 100:.2f}%")
        print("-" * 40)
        return metrics
        
    except Exception as e:
        print(f"❌ Error during transcription evaluation: {e}")
        import traceback
        traceback.print_exc()
        return {}