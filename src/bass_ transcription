# src/bass_transcription.py

import os
import numpy as np
import pandas as pd
import librosa
import scipy.signal
import torch
import torchcrepe
import matplotlib.pyplot as plt
import pretty_midi

# ==================================================================================
# 1. Helper Functions & Post-Processing (Core Logic)
# ==================================================================================

def clean_octave_errors_smart(f0_array, onset_mask, valid_threshold=12, window_size=7, onset_tolerance=2):
    """
    [Error Correction] Onset 기반 스마트 옥타브 오류 보정
    - Onset(어택) 부근에서 발생한 옥타브 도약은 의도된 연주(Slap 등)로 간주하여 보존.
    - 지속음(Sustain) 도중 발생한 옥타브 튐 현상만 배음(Harmonics) 에러로 간주하여 강제 보정.
    """
    f0_clean = f0_array.copy()
    
    # 유효한 구간만 처리
    mask = (f0_clean > 0) & (~np.isnan(f0_clean))
    if np.sum(mask) == 0:
        return f0_clean
        
    # Hz -> MIDI 변환
    midi_notes = np.zeros_like(f0_clean)
    midi_notes[mask] = librosa.hz_to_midi(f0_clean[mask])
    
    # 이동 중앙값(Rolling Median)으로 전체적인 멜로디 트렌드 파악
    midi_series = pd.Series(midi_notes)
    trend = midi_series.where(mask).rolling(window=window_size, center=True, min_periods=1).median().values
    
    indices = np.where(mask)[0]
    
    for i in indices:
        if np.isnan(trend[i]): continue
        diff = midi_notes[i] - trend[i]
        
        # ±1 옥타브 또는 ±2 옥타브 에러 범위 내인지 확인
        is_octave_jump = (10 <= diff <= 14) or (22 <= diff <= 26) or (-14 <= diff <= -10)
        
        if is_octave_jump:
            # 현재 프레임 근처(±onset_tolerance)에 Onset이 있는지 확인
            start_idx = max(0, i - onset_tolerance)
            end_idx = min(len(onset_mask), i + onset_tolerance + 1)
            is_intentional_attack = np.any(onset_mask[start_idx:end_idx])
            
            # 의도된 어택(Onset)이 없는 경우에만 기계적 에러로 간주하고 보정 실행
            if not is_intentional_attack:
                if 10 <= diff <= 14:
                    midi_notes[i] -= 12
                elif 22 <= diff <= 26:
                    midi_notes[i] -= 24
                elif -14 <= diff <= -10:
                    midi_notes[i] += 12

    # 보정된 MIDI -> Hz 복구
    f0_clean[mask] = librosa.midi_to_hz(midi_notes[mask])
    return f0_clean

def post_process_refinement(f0, hop_length, sr, min_duration_ms=50):
    """
    [Refinement] 고음 노이즈 제거 + 양자화(Quantization) + 짧은 노이즈 제거
    """
    f0_clean = f0.copy()
    
    # 1. High Frequency Cutoff (200Hz 이상 삭제)
    f0_clean[f0_clean > 200] = np.nan

    # 2. Quantization (Hz -> MIDI Note 반올림 -> Hz)
    valid_mask = ~np.isnan(f0_clean)
    if np.sum(valid_mask) > 0:
        midi_float = librosa.hz_to_midi(f0_clean[valid_mask])
        midi_round = np.round(midi_float)
        f0_clean[valid_mask] = librosa.midi_to_hz(midi_round)

    # 3. Short Note Removal (짧은 잡음 제거)
    min_frames = int((min_duration_ms / 1000) * (sr / hop_length))
    
    temp_notes = f0_clean.copy()
    temp_notes[np.isnan(temp_notes)] = -1
    
    series = pd.Series(temp_notes)
    groups = (series != series.shift()).cumsum()
    counts = series.groupby(groups).transform('count')
    
    mask_short = (counts < min_frames) & (series != -1)
    f0_clean[mask_short] = np.nan
    
    return f0_clean

# ==================================================================================
# 2. Main Pitch Tracking Function (CREPE)
# ==================================================================================

def get_f0_crepe_robust(audio, sr, hop_length=160, fmin=40, fmax=500, smooth_kernel=3, chunk_duration=30):
    """
    [Main Pipeline] 프로덕션 환경에 최적화된 베이스 전용 피치 트래커
    (Pre-processing -> VRAM Safe Chunking -> Onset Detection -> Smart Post-processing)
    """
    # 1. [Pre] High-pass Filter (35Hz Cutoff for Rumble noise)
    sos = scipy.signal.butter(4, 35, 'hp', fs=sr, output='sos')
    audio = scipy.signal.sosfilt(sos, audio)

    # 2. [Pre] Audio Normalization
    if np.max(np.abs(audio)) < 1e-6:
        return np.zeros(len(audio) // hop_length) 
    audio = librosa.util.normalize(audio)

    # 3. Setup Device
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # 4. [Inference] CREPE Inference (VRAM-Safe Chunking)
    chunk_samples = int(chunk_duration * sr)
    # 프레임 밀림 현상 방지를 위해 chunk_samples를 hop_length의 배수로 정렬
    chunk_samples -= (chunk_samples % hop_length) 
    total_samples = len(audio)
    
    f0_list = []
    confidence_list = []
    
    for start_idx in range(0, total_samples, chunk_samples):
        end_idx = min(start_idx + chunk_samples, total_samples)
        audio_chunk = audio[start_idx:end_idx]
        
        # 마지막 청크가 1024 샘플 미만일 경우 패딩 처리 (CREPE 내부 에러 방지)
        if len(audio_chunk) < 1024:
            pad_len = 1024 - len(audio_chunk)
            audio_chunk = np.pad(audio_chunk, (0, pad_len), mode='constant')

        audio_tensor = torch.tensor(audio_chunk).float().unsqueeze(0).to(device)
        
        # 서버 VRAM 부하를 평탄화하기 위해 batch_size를 256으로 하향 조정
        f0_chunk, conf_chunk = torchcrepe.predict(
            audio_tensor,
            sr,
            hop_length=hop_length,
            fmin=fmin,
            fmax=fmax,
            model='full',
            decoder=torchcrepe.decode.argmax, 
            return_periodicity=True,
            device=device,
            batch_size=256 
        )
        
        f0_list.append(f0_chunk.squeeze().cpu().numpy())
        confidence_list.append(conf_chunk.squeeze().cpu().numpy())
        
        # 명시적인 VRAM 가비지 컬렉션 수행
        del audio_tensor, f0_chunk, conf_chunk
        if device == 'cuda':
            torch.cuda.empty_cache()
            
    # 분할된 청크 결과 병합
    f0 = np.concatenate(f0_list)
    confidence = np.concatenate(confidence_list)
    
    # 패딩으로 인해 늘어난 프레임 길이를 원본 기대 길이로 정확히 절사
    expected_frames = 1 + int(total_samples // hop_length)
    f0 = f0[:expected_frames]
    confidence = confidence[:expected_frames]

    # 5. [Post] Onset Detection (어택 지점 추출)
    onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
    
    onset_mask = np.zeros(len(f0), dtype=bool)
    valid_onsets = onset_frames[onset_frames < len(f0)]
    onset_mask[valid_onsets] = True

    # 6. [Post] Median Filter (Spike Removal)
    # NaN 결측치가 없는 연속된 상태에서 스파이크를 먼저 평탄화
    if smooth_kernel > 1:
        f0_series = pd.Series(f0)
        f0 = f0_series.rolling(window=smooth_kernel, center=True, min_periods=1).median().values

    # 7. [Post] Smart Octave Error Correction (어택 기반 예외 처리)
    f0 = clean_octave_errors_smart(f0, onset_mask, window_size=7, onset_tolerance=2)

    # 8. [Post] Confidence Masking
    # 보정 연산이 모두 끝난 후, 모델의 신뢰도가 낮은 구간만 마스킹 처리
    f0[confidence < 0.15] = np.nan 

    # 9. [Post] Final Refinement (Quantization & 200Hz Cutoff)
    f0 = post_process_refinement(f0, hop_length, sr)

    return f0

# ==================================================================================
# 3. Visualization & Export Functions
# ==================================================================================

def plot_piano_roll(f0_array, sr, hop_length):
    """
    [Viz] 최적화된 범위의 피아노 롤 시각화
    """
    valid_mask = ~np.isnan(f0_array) & (f0_array > 0)
    if np.sum(valid_mask) == 0:
        print("⚠️ 표시할 유효한 데이터가 없습니다.")
        return

    midi_notes = np.zeros_like(f0_array)
    midi_notes[valid_mask] = librosa.hz_to_midi(f0_array[valid_mask])
    
    times = librosa.frames_to_time(np.arange(len(f0_array)), sr=sr, hop_length=hop_length)

    plt.figure(figsize=(14, 6))
    plt.scatter(times[valid_mask], midi_notes[valid_mask], 
                c='dodgerblue', s=15, alpha=0.7, marker='s', edgecolors='none')

    # Y축 범위 자동 조절
    min_note_val = int(np.floor(np.min(midi_notes[valid_mask])))
    max_note_val = int(np.ceil(np.max(midi_notes[valid_mask])))
    
    plot_min = min_note_val - 1
    plot_max = max_note_val + 1
    
    yticks = np.arange(plot_min, plot_max + 1)
    yticklabels = [librosa.midi_to_note(n) for n in yticks]

    plt.ylim(plot_min, plot_max)
    plt.yticks(yticks, yticklabels, fontsize=9)
    plt.grid(axis='y', linestyle='-', alpha=0.3, color='gray') 
    plt.grid(axis='x', linestyle='--', alpha=0.3)
    
    plt.title(f"Bass Line Piano Roll ({librosa.midi_to_note(min_note_val)} ~ {librosa.midi_to_note(max_note_val)})")
    plt.xlabel("Time (seconds)")
    plt.ylabel("Note")
    plt.tight_layout()
    plt.show()

def save_to_midi(f0_array, sr, hop_length, output_path, velocity=100):
    """
    [Export] f0 데이터를 MIDI 파일로 변환 (Note Grouping 적용)
    """
    pm = pretty_midi.PrettyMIDI()
    bass_program = pretty_midi.instrument_name_to_program('Electric Bass (finger)')
    bass_inst = pretty_midi.Instrument(program=bass_program)
    
    frame_time = hop_length / sr
    current_note = None
    start_time = 0.0
    
    for i, hz in enumerate(f0_array):
        time = i * frame_time
        is_valid = (not np.isnan(hz)) and (hz > 0)
        midi_note = int(round(librosa.hz_to_midi(hz))) if is_valid else None
        
        # Note Grouping Logic
        if current_note is not None:
            if (not is_valid) or (midi_note != current_note):
                note = pretty_midi.Note(velocity=velocity, pitch=current_note, start=start_time, end=time)
                bass_inst.notes.append(note)
                current_note = None
        
        if is_valid:
            if current_note is None:
                current_note = midi_note
                start_time = time
                
    if current_note is not None:
         note = pretty_midi.Note(velocity=velocity, pitch=current_note, start=start_time, end=len(f0_array) * frame_time)
         bass_inst.notes.append(note)

    pm.instruments.append(bass_inst)
    pm.write(output_path)
    print(f"💾 MIDI Saved: {output_path}")

# ==================================================================================
# 4. Pipeline Wrapper (Optional)
# ==================================================================================

def run_pipeline(audio_path, output_midi="output.mid"):
    """
    오디오 로드부터 MIDI 저장까지 한 번에 실행
    """
    print(f"📂 Loading: {audio_path}")
    y, sr = librosa.load(audio_path, sr=16000)
    
    print("🚀 Running Pitch Tracking...")
    f0 = get_f0_crepe_robust(y, sr, hop_length=160)
    
    print("📊 Visualizing...")
    plot_piano_roll(f0, sr=16000, hop_length=160)
    
    print("💾 Exporting MIDI...")
    save_to_midi(f0, sr=16000, hop_length=160, output_path=output_midi)
    
    return f0
