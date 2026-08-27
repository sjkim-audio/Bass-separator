import numpy as np
import pandas as pd
import librosa
import scipy.signal
import torch
import torchcrepe
import gc

def clean_octave_errors_smart(f0_array, onset_mask):
    """
    온셋(Onset) 경계를 기준으로 시계열 데이터를 독립 조각(Segment)으로 분할한 뒤,
    각 조각의 중앙값(진짜 기음)을 기준으로 배음 에러(옥타브 도약)를 격리하여 평탄화합니다.
    """
    f0_clean = f0_array.copy()
    mask = (f0_clean > 0) & (~np.isnan(f0_clean))
    
    if np.sum(mask) == 0:
        return f0_clean
        
    midi_notes = np.full_like(f0_clean, np.nan)
    midi_notes[mask] = librosa.hz_to_midi(f0_clean[mask])
    
    onset_indices = np.where(onset_mask)[0]
    
    if len(onset_indices) == 0:
        onset_indices = np.array([0])
    elif onset_indices[0] != 0:
        onset_indices = np.insert(onset_indices, 0, 0)
        
    boundaries = np.append(onset_indices, len(f0_clean))
    
    for i in range(len(boundaries) - 1):
        start_idx = boundaries[i]
        end_idx = boundaries[i+1]
        
        segment_mask = mask[start_idx:end_idx]
        if np.sum(segment_mask) == 0:
            continue
            
        segment_midi = midi_notes[start_idx:end_idx]
        valid_midi = segment_midi[segment_mask]
        
        segment_median = np.median(valid_midi)
        
        for j in range(end_idx - start_idx):
            if not segment_mask[j]:
                continue
            
            diff = segment_midi[j] - segment_median
            
            if 10.0 <= diff <= 14.0:
                segment_midi[j] -= 12.0
            elif 22.0 <= diff <= 26.0:
                segment_midi[j] -= 24.0
            elif -14.0 <= diff <= -10.0:
                segment_midi[j] += 12.0
            elif -26.0 <= diff <= -22.0:
                segment_midi[j] += 24.0
                
        midi_notes[start_idx:end_idx] = segment_midi
        
    f0_clean[mask] = librosa.midi_to_hz(midi_notes[mask])
    return f0_clean

def get_f0_crepe_robust(audio, sr, hop_length=160, fmin=40, fmax=500, chunk_duration=30, model_capacity='tiny', batch_size=512):
    sos = scipy.signal.butter(4, 35, 'hp', fs=sr, output='sos')
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
                with torch.no_grad():
                    f0_chunk, conf_chunk = torchcrepe.predict(
                        audio_tensor, sr, hop_length=hop_length, fmin=fmin, fmax=fmax,
                        model=model_capacity, decoder=torchcrepe.decode.argmax, 
                        return_periodicity=True, device=device, batch_size=current_batch 
                    )
                success = True
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    del audio_tensor
                    if device == 'cuda':
                        torch.cuda.empty_cache()
                        torch.cuda.ipc_collect()
                    gc.collect()
                    
                    if current_batch <= 1:
                        raise RuntimeError("❌ CUDA OOM: 배치 사이즈를 1까지 줄였으나 메모리가 부족합니다.")
                    
                    current_batch //= 2
                    print(f"⚠️ GPU OOM 감지. 배치 사이즈 {current_batch}로 재시도...")
                    audio_tensor = torch.tensor(audio_chunk).unsqueeze(0).to(device)
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
    
    # 🚨 [최종 교정됨] Time-Conditioned Peak Evaluation
    # 1프레임(10ms)짜리 우발적 노이즈 스파이크를 배제하고, 저역대 파장 형성의 최소 물리 시간인 20ms(2프레임) 이상의 신뢰도 충족을 요구함.
    artifact_resistant_onsets = []
    for idx in valid_onsets:
        end_eval_idx = min(idx + 5, len(confidence))
        # 40ms(5프레임) 윈도우 내에서 confidence >= 0.4 인 프레임의 개수 산출
        high_conf_frames = np.sum(confidence[idx:end_eval_idx] >= 0.4)
        if high_conf_frames >= 2:
            artifact_resistant_onsets.append(idx)
            
    if artifact_resistant_onsets:
        onset_mask[np.array(artifact_resistant_onsets, dtype=int)] = True

    mask_low = (f0 < 80) & (confidence < 0.2)
    mask_mid = (f0 >= 80) & (f0 <= 200) & (confidence < 0.4)
    mask_high = (f0 > 200) & (confidence < 0.6)

    f0[mask_low | mask_mid | mask_high] = np.nan
    f0[f0 > fmax] = np.nan

    f0 = clean_octave_errors_smart(f0, onset_mask)

    return f0, confidence, onset_mask
