import numpy as np
import pandas as pd
import librosa
import scipy.signal
import torch
import torchcrepe

def clean_octave_errors_smart(f0_array, onset_mask, window_size=7, onset_tolerance=4):
    f0_clean = f0_array.copy()
    mask = (f0_clean > 0) & (~np.isnan(f0_clean))
    if np.sum(mask) == 0:
        return f0_clean
        
    midi_notes = np.zeros_like(f0_clean)
    midi_notes[mask] = librosa.hz_to_midi(f0_clean[mask])
    
    midi_series = pd.Series(midi_notes)
    trend = midi_series.where(mask).rolling(window=window_size, center=True, min_periods=1).median().values
    
    indices = np.where(mask)[0]
    for i in indices:
        if np.isnan(trend[i]): continue
        diff = midi_notes[i] - trend[i]
        
        is_octave_jump = (10 <= diff <= 14) or (22 <= diff <= 26) or (-14 <= diff <= -10)
        
        if is_octave_jump:
            start_idx = max(0, i - onset_tolerance)
            end_idx = min(len(onset_mask), i + onset_tolerance + 1)
            is_intentional_attack = np.any(onset_mask[start_idx:end_idx])
            
            if not is_intentional_attack:
                if 10 <= diff <= 14:
                    midi_notes[i] -= 12
                elif 22 <= diff <= 26:
                    midi_notes[i] -= 24
                elif -14 <= diff <= -10:
                    midi_notes[i] += 12

    f0_clean[mask] = librosa.midi_to_hz(midi_notes[mask])
    return f0_clean

# 🔴 [수정] 5현 베이스 및 Augmentation 다운튜닝 커버를 위해 fmin=30으로 하향
def get_f0_crepe_robust(audio, sr, hop_length=160, fmin=30, fmax=500, chunk_duration=30, model_capacity='tiny', batch_size=512):
    # 🔴 [수정] 저음역대 손실 방지를 위해 HPF Cutoff를 35Hz -> 25Hz로 하향
    sos = scipy.signal.butter(4, 25, 'hp', fs=sr, output='sos')
    audio = scipy.signal.sosfilt(sos, audio)
    audio = audio.astype(np.float32)

    if np.max(np.abs(audio)) < 1e-6:
        return np.zeros(len(audio) // hop_length), np.zeros(len(audio) // hop_length), np.zeros(len(audio) // hop_length, dtype=bool)
    audio = librosa.util.normalize(audio)

    if torch.cuda.is_available():
        device = 'cuda'
    elif torch.backends.mps.is_available():
        device = 'mps'
    else:
        device = 'cpu'
        print("⚠️ 경고: GPU가 감지되지 않아 연산이 매우 느려질 수 있습니다.")
    
    chunk_samples = int(chunk_duration * sr)
    chunk_samples -= (chunk_samples % hop_length) 
    total_samples = len(audio)
    
    f0_list = []
    confidence_list = []
    
    for start_idx in range(0, total_samples, chunk_samples):
        end_idx = min(start_idx + chunk_samples, total_samples)
        audio_chunk = audio[start_idx:end_idx]
        
        if len(audio_chunk) < 1024:
            pad_len = 1024 - len(audio_chunk)
            audio_chunk = np.pad(audio_chunk, (0, pad_len), mode='constant')

        audio_tensor = torch.tensor(audio_chunk).unsqueeze(0).to(device)
        
        current_batch = batch_size
        success = False
        
        while not success:
            try:
                f0_chunk, conf_chunk = torchcrepe.predict(
                    audio_tensor, sr, hop_length=hop_length, fmin=fmin, fmax=fmax,
                    model=model_capacity, decoder=torchcrepe.decode.argmax, 
                    return_periodicity=True, device=device, batch_size=current_batch 
                )
                success = True
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    if current_batch <= 1:
                        raise RuntimeError("❌ CUDA OOM: 배치 사이즈를 1까지 줄였으나 메모리가 부족합니다. chunk_duration을 줄이십시오.")
                    current_batch //= 2
                    print(f"⚠️ GPU OOM 감지됨. 배치 사이즈를 {current_batch}(으)로 줄이고 재시도합니다...")
                    if device == 'cuda':
                        torch.cuda.empty_cache()
                else:
                    raise e 
        
        f0_chunk = f0_chunk.squeeze().cpu().numpy()
        conf_chunk = conf_chunk.squeeze().cpu().numpy()
        
        if end_idx < total_samples:
            f0_chunk = f0_chunk[:-1]
            conf_chunk = conf_chunk[:-1]
            
        f0_list.append(f0_chunk)
        confidence_list.append(conf_chunk)
        
        del audio_tensor, f0_chunk, conf_chunk
        if device == 'cuda':
            torch.cuda.empty_cache()
            
    f0 = np.concatenate(f0_list)
    confidence = np.concatenate(confidence_list)
    
    expected_frames = 1 + int(total_samples // hop_length)
    f0 = f0[:expected_frames]
    confidence = confidence[:expected_frames]

    onset_env = librosa.onset.onset_strength(y=audio, sr=sr, hop_length=hop_length, fmax=400, aggregate=np.median)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, hop_length=hop_length, wait=3, pre_avg=3, post_avg=3, delta=0.06)
    
    onset_mask = np.zeros(len(f0), dtype=bool)
    valid_onsets = onset_frames[onset_frames < len(f0)]
    onset_mask[valid_onsets] = True

    f0 = clean_octave_errors_smart(f0, onset_mask, window_size=7, onset_tolerance=4)

    mask_low = (f0 < 80) & (confidence < 0.2)
    mask_mid = (f0 >= 80) & (f0 <= 200) & (confidence < 0.4)
    mask_high = (f0 > 200) & (confidence < 0.6)

    f0[mask_low | mask_mid | mask_high] = np.nan
    f0[f0 > fmax] = np.nan

    return f0, confidence, onset_mask