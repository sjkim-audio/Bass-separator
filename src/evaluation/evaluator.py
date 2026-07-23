import os
import warnings
import logging
import numpy as np
import librosa
import scipy.signal
import traceback
import soundfile as sf
import asyncio
from scipy import signal

from typing import List, Dict

import museval
import mir_eval
import pretty_midi

from src.models.events import NoteEvent

# 서드파티 라이브러리의 자잘한 경고 메시지 억제 (평가 로그 가독성 확보)
warnings.filterwarnings('ignore', module='librosa')
warnings.filterwarnings('ignore', module='pretty_midi')

def align_audio(ref_audio, est_audio, sr):
    """
    상호 상관(Cross-correlation)을 사용하여 두 1D 오디오 배열의 위상 지연을 맞춥니다.
    """
    # 1D 배열로 강제 변환 (차원 충돌 방지)
    ref_audio = np.atleast_1d(ref_audio).squeeze()
    est_audio = np.atleast_1d(est_audio).squeeze()
    
    correlation = signal.correlate(ref_audio, est_audio, mode='full')
    lags = signal.correlation_lags(len(ref_audio), len(est_audio), mode='full')
    lag = lags[np.argmax(correlation)]
    
    # 1D 슬라이싱 적용
    if lag > 0:
        est_audio = est_audio[lag:]
        ref_audio = ref_audio[:len(est_audio)]
    elif lag < 0:
        ref_audio = ref_audio[-lag:]
        est_audio = est_audio[:len(ref_audio)]
        
    min_len = min(len(ref_audio), len(est_audio))
    return ref_audio[:min_len], est_audio[:min_len]

def evaluate_separation(ref_path: str, est_path: str, align: bool = False):
    """
    SDR, SIR, SAR 평가 로직 (museval 대신 안정적인 mir_eval 사용)
    """
    ref_audio, sr = librosa.load(ref_path, sr=None, mono=True)
    est_audio, _ = librosa.load(est_path, sr=sr, mono=True)
    
    if align:
        ref_audio, est_audio = align_audio(ref_audio, est_audio, sr)
    else:
        min_len = min(len(ref_audio), len(est_audio))
        ref_audio = ref_audio[:min_len]
        est_audio = est_audio[:min_len]
    
    # mir_eval BSS는 [sources, samples] 2D 구조를 요구하므로 차원 추가
    ref_sources = ref_audio[np.newaxis, :]
    est_sources = est_audio[np.newaxis, :]
    
    try:
        sdr, sir, sar, _ = mir_eval.separation.bss_eval_sources(ref_sources, est_sources)
        return {"SDR": sdr, "SIR": sir, "SAR": sar}
    except Exception as e:
        print(f"⚠️ BSS_Eval 에러: {e}")
        return {"SDR": [np.nan], "SIR": [np.nan], "SAR": [np.nan]}

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
        notes = []
        
        for instrument in pm.instruments:
            if not instrument.is_drum:
                notes.extend(instrument.notes)
                
        # [수정] 동시 타현 시 높은 피치가 최종적으로 마스킹(우선순위 획득)하도록 
        # (시작 시간 오름차순, 피치 오름차순)으로 정렬
        notes.sort(key=lambda x: (x.start, x.pitch))

        final_intervals = []
        final_pitches = []
        
        for note in notes:
            start = note.start
            end = note.end
            freq = pretty_midi.note_number_to_hz(note.pitch)

            # 새 노트가 차지하는 구간을 기존 노트들에서 정밀하게 도려냄 (서스테인 보존 로직)
            new_intervals = []
            new_pitches = []
            for (st, ed), p in zip(final_intervals, final_pitches):
                # 겹치지 않는 구간은 그대로 보존
                if ed <= start or st >= end:
                    new_intervals.append([st, ed])
                    new_pitches.append(p)
                else:
                    # 겹치는 구간 발생 시 앞뒤로 분할(Split)하여 서스테인 꼬리를 살림
                    if st < start:
                        new_intervals.append([st, start])
                        new_pitches.append(p)
                    if ed > end:
                        new_intervals.append([end, ed])
                        new_pitches.append(p)
            
            final_intervals = new_intervals
            final_pitches = new_pitches
            
            # 새 노트 삽입
            final_intervals.append([start, end])
            final_pitches.append(freq)
            
        if not final_intervals:
            return np.empty((0, 2)), np.empty((0,))
            
        # 다시 시간순 정렬 (마스킹 과정에서 순서가 섞였을 수 있으므로 재정렬)
        sorted_indices = np.argsort([iv[0] for iv in final_intervals])
        intervals_arr = np.array(final_intervals)[sorted_indices]
        pitches_arr = np.array(final_pitches)[sorted_indices]
        
        return intervals_arr, pitches_arr

    # [디버그용 임시 코드] 정적 메서드로 명확히 분리
    @staticmethod
    def debug_octave_shift(ref_intervals, ref_pitches, est_intervals, est_pitches):
        print("\n--- 🔍 [DEBUG] MIDI Pitch Comparison (First 10 notes) ---")
        
        ref_midi = np.round(librosa.hz_to_midi(ref_pitches[:10])) if len(ref_pitches) > 0 else []
        est_midi = np.round(librosa.hz_to_midi(est_pitches[:10])) if len(est_pitches) > 0 else []
        
        print(f"✅ 정답 (GT) MIDI: {ref_midi}")
        print(f"🤖 예측 (EST) MIDI: {est_midi}")
        
        if len(ref_midi) > 0 and len(est_midi) > 0:
            diff = np.mean(est_midi[:min(len(ref_midi), len(est_midi))] - ref_midi[:min(len(ref_midi), len(est_midi))])
            print(f"📊 평균 시프트(Shift): {diff:.2f} semitones")
            
            if diff > 10: 
                print("⚠️ 진단: 모델이 GT보다 1옥타브 높게 예측 중입니다 (+12). (Harmonic Lock-on 의심)")
            elif diff < -10: 
                print("⚠️ 진단: 모델이 GT보다 1옥타브 낮게 예측 중입니다 (-12). (VSTi Transposition 의심)")
        print("----------------------------------------------------------\n")

    @staticmethod
    def _events_to_mir_eval(events: List[NoteEvent], use_quantized: bool = False):
        intervals, pitches = [], []
        for e in events:
            if use_quantized and e.quantized_time is not None and e.quantized_duration is not None:
                onset, offset = e.quantized_time, e.quantized_time + e.quantized_duration
            else:
                onset = e.time
                
                # [수정] 비정상적인 지속시간(Duration)에 대한 명시적 로깅 방어선 구축
                if e.duration <= 0:
                    logging.warning(
                        f"⚠️ [평가 경고] 비정상적인 지속시간(Duration <= 0) 감지됨 "
                        f"(Onset: {onset:.3f}s, Note: {e.midi_note}). 파이프라인의 시간 역전 버그일 수 있습니다. "
                        f"평가를 위해 50ms로 강제 보정합니다."
                    )
                    duration = 0.05
                else:
                    duration = e.duration
                    
                offset = onset + duration
                
            intervals.append([onset, offset])
            
            raw_pitch = getattr(e, 'pitch', None)
            if raw_pitch is not None:
                pitches.append(raw_pitch)
            else:
                pitches.append(librosa.midi_to_hz(e.midi_note))
            
        if not intervals:
            return np.empty((0, 2)), np.empty((0,))
        return np.array(intervals), np.array(pitches)

    @staticmethod
    def evaluate(ref_midi_path: str, est_events: List[NoteEvent], test_quantized: bool = False, onset_tolerance: float = 0.1) -> Dict[str, float]:
        ref_intervals, ref_pitches = TranscriptionEvaluator.load_midi_to_mir_eval(ref_midi_path)
        est_intervals, est_pitches = TranscriptionEvaluator._events_to_mir_eval(est_events, use_quantized=test_quantized)
        
        # 예외 상황에서도 스키마 무결성을 보장하기 위한 템플릿
        empty_schema = {
            "Onset_Precision": 0.0, "Onset_Recall": 0.0, "Onset_F1": 0.0,
            "Onset_Pitch_Precision": 0.0, "Onset_Pitch_Recall": 0.0, "Onset_Pitch_F1": 0.0,
            "Chroma_F1": 0.0, "Octave_Error_Rate": 0.0,
            "Strict_Precision": 0.0, "Strict_Recall": 0.0, "Strict_F1": 0.0
        }

        if len(ref_intervals) == 0 and len(est_intervals) == 0:
            perfect_schema = empty_schema.copy()
            for k in perfect_schema:
                if "Error" not in k: perfect_schema[k] = 1.0
            return perfect_schema
        elif len(ref_intervals) == 0 or len(est_intervals) == 0:
             return empty_schema.copy()

        # 🚨 [추가] mir_eval 채점 직전에 디버그 함수 호출 (raw 모드일 때만 1회 출력되도록 제어)
        if not test_quantized:
            TranscriptionEvaluator.debug_octave_shift(ref_intervals, ref_pitches, est_intervals, est_pitches)

        # 1. 원본 엄격 평가 (기존 로직)
        scores = mir_eval.transcription.evaluate(
            ref_intervals, ref_pitches, est_intervals, est_pitches,
            onset_tolerance=onset_tolerance, 
            pitch_tolerance=50.0, 
            offset_ratio=0.2, 
            offset_min_tolerance=0.05
        )
        
        # 2. 옥타브 무시(Chroma) 평가
        ref_pitches_chroma = librosa.midi_to_hz((librosa.hz_to_midi(ref_pitches) % 12) + 48)
        est_pitches_chroma = librosa.midi_to_hz((librosa.hz_to_midi(est_pitches) % 12) + 48)
        
        scores_chroma = mir_eval.transcription.evaluate(
            ref_intervals, ref_pitches_chroma, est_intervals, est_pitches_chroma,
            onset_tolerance=onset_tolerance, 
            pitch_tolerance=50.0, 
            offset_ratio=0.2, 
            offset_min_tolerance=0.05
        )

        chroma_f1 = round(scores_chroma.get('F-measure_no_offset', 0.0), 4)
        strict_pitch_f1 = round(scores.get('F-measure_no_offset', 0.0), 4)

        return {
            "Onset_Precision": round(scores.get('Onset_Precision', 0.0), 4),
            "Onset_Recall": round(scores.get('Onset_Recall', 0.0), 4),
            "Onset_F1": round(scores.get('Onset_F-measure', 0.0), 4),
            
            "Onset_Pitch_Precision": round(scores.get('Precision_no_offset', 0.0), 4),
            "Onset_Pitch_Recall": round(scores.get('Recall_no_offset', 0.0), 4),
            "Onset_Pitch_F1": strict_pitch_f1,
            
            "Chroma_F1": chroma_f1,
            "Octave_Error_Rate": round(chroma_f1 - strict_pitch_f1, 4),
            
            "Strict_Precision": round(scores.get('Precision', 0.0), 4),
            "Strict_Recall": round(scores.get('Recall', 0.0), 4),
            "Strict_F1": round(scores.get('F-measure', 0.0), 4)
        }

async def run_transcription_evaluation(ref_midi_path: str, audio_path: str, is_isolated: bool = False, onset_tolerance: float = 0.1, ref_audio_path: str = None) -> dict:
    print(f"🎵 [Transcription] Processing Audio: {os.path.basename(audio_path)}")
    from src.core.pipeline import run_transcription_pipeline
    
    bass_path = audio_path
    bassless_path = None
    separation_metrics = {} # 분리 성능을 담을 빈 딕셔너리 초기화
    
    try:
        if not is_isolated:
            from src.core.demucs_runner import separate_and_generate_stems
            print("⏳ 믹스 음원이 감지되었습니다. Demucs 음원 분리를 먼저 수행합니다...")
            temp_out_dir = "outputs/eval_temp"
            bass_path, bassless_path = await separate_and_generate_stems(audio_path, output_dir=temp_out_dir)
            
            if ref_audio_path and os.path.exists(ref_audio_path):
                print("⏱️ 정답 오디오를 기반으로 Demucs 위상 지연(Latency) 보정을 수행합니다...")
                ref_audio, sr = librosa.load(ref_audio_path, sr=None, mono=True)
                est_audio, _ = librosa.load(bass_path, sr=sr, mono=True)
                
                _, aligned_est = align_audio(ref_audio, est_audio, sr)
                
                aligned_bass_path = os.path.join(temp_out_dir, "bass_aligned.wav")
                sf.write(aligned_bass_path, aligned_est, sr)
                bass_path = aligned_bass_path
                
                # ---------------------------------------------------------
                # 생성된(보정된) 베이스 파형에 대한 음원 분리 채점 실행
                # ---------------------------------------------------------
                try:
                    sep_raw = evaluate_separation(ref_audio_path, bass_path, align=False)
                    separation_metrics = {
                        "SDR": float(np.nanmedian(sep_raw["SDR"])),
                        "SIR": float(np.nanmedian(sep_raw["SIR"])),
                        "SAR": float(np.nanmedian(sep_raw["SAR"]))
                    }
                    print(f"✅ [Separation] Median SDR: {separation_metrics['SDR']:.2f} dB")
                except Exception as e:
                    print(f"⚠️ [Separation] 분리 성능 채점 실패: {e}")
            else:
                print("⚠️ [경고] ref_audio_path가 제공되지 않아 E2E 위상 지연 보정을 건너뜁니다.")
                
        else:
            print("⚡ 단일 베이스 트랙(Isolated) 모드입니다. Demucs를 생략하고 즉시 채보를 시작합니다.")

        # ---------------------------------------------------------
        # [복구됨] 실제 Transcription 파이프라인 가동 및 채점 로직
        # ---------------------------------------------------------
        loop = asyncio.get_running_loop()
        _, _, fingered_events, quantized_events = await loop.run_in_executor(
            None, run_transcription_pipeline, bass_path, bassless_path
        )
        
        metrics_raw = TranscriptionEvaluator.evaluate(ref_midi_path, fingered_events, test_quantized=False, onset_tolerance=onset_tolerance)
        metrics_quantized = TranscriptionEvaluator.evaluate(ref_midi_path, quantized_events, test_quantized=True, onset_tolerance=onset_tolerance)
        
        print("-" * 40)
        print("🔹 Transcription Summary (mir_eval)")
        print("-" * 40)
        print(f"✅ [Raw] Onset-Pitch F1-Score        : {metrics_raw['Onset_Pitch_F1'] * 100:.2f}%")
        print(f"✅ [Quantized] Onset-Pitch F1-Score  : {metrics_quantized['Onset_Pitch_F1'] * 100:.2f}%")
        print(f"✅ [Quantized] Chroma F1-Score       : {metrics_quantized.get('Chroma_F1', 0.0) * 100:.2f}%")
        print(f"⚠️ [Quantized] Octave Error Rate     : {metrics_quantized.get('Octave_Error_Rate', 0.0) * 100:.2f}%")
        print("-" * 40)
        # ---------------------------------------------------------
        
        return {
            "raw": metrics_raw,
            "quantized": metrics_quantized,
            "separation": separation_metrics
        }
        
    except Exception as e:
        print(f"❌ Error during transcription evaluation: {e}")
        import traceback
        traceback.print_exc()
        return {}
