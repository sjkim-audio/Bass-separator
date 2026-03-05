import os
import numpy as np
import librosa
import scipy.signal
import museval
import traceback

def align_audio(ref: np.ndarray, est: np.ndarray, sr: int = 44100):
    """
    [전처리] Cross-Correlation을 사용하여 두 오디오 간의 미세한 시간 지연(Latency)을 보정한다.
    딥러닝 분리 모델이 유발하는 위상 밀림 현상을 평가 전에 정렬해야 정확한 SDR 산출이 가능하다.
    """
    max_len = sr * 30  # 연산 속도 최적화를 위해 초반 30초만 사용하여 지연량 추정
    
    ref_mono = np.mean(ref, axis=0) if ref.ndim > 1 else ref
    est_mono = np.mean(est, axis=0) if est.ndim > 1 else est
    
    correlation = scipy.signal.correlate(
        ref_mono[:max_len], 
        est_mono[:max_len], 
        mode='full'
    )
    
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
    """
    [평가] BSSEval v4 표준 규격을 사용하여 SDR, SIR, SAR 지표를 산출한다.
    """
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _ = librosa.load(estimated_path, sr=sr, mono=False)

    if ref.ndim == 1: ref = ref[np.newaxis, :]
    if est.ndim == 1: est = est[np.newaxis, :]

    min_len = min(ref.shape[1], est.shape[1])
    ref = ref[:, :min_len]
    est = est[:, :min_len]

    if align:
        ref, est = align_audio(ref, est, sr)

    # Museval 규격: (n_sources, n_samples, n_channels)
    ref_eval = ref.T[np.newaxis, :, :]
    est_eval = est.T[np.newaxis, :, :]

    # 1초(win=sr) 단위의 윈도우로 평가 수행
    sdr, isr, sir, sar, _ = museval.eval_bss_v4(ref_eval, est_eval, win=sr)

    return {
        "SDR": sdr.squeeze(),
        "SIR": sir.squeeze(),
        "SAR": sar.squeeze(),
        "sr": sr,
        "hop_sec": 1.0
    }

def run_evaluation(ref_path: str, est_path: str, align: bool = True) -> dict:
    """
    [래퍼] 평가를 실행하고 콘솔에 중앙값(Median) 요약을 출력한다.
    """
    print(f"📊 Processing: {os.path.basename(est_path)}")
    try:
        metrics_data = evaluate_separation(ref_path, est_path, align=align)
        
        print("-" * 40)
        print("🔹 Summary Statistics (BSSEval v4)")
        print("-" * 40)
        print(f"✅ Median SDR: {np.nanmedian(metrics_data['SDR']):.2f} dB")
        print(f"✅ Median SIR: {np.nanmedian(metrics_data['SIR']):.2f} dB")
        print(f"✅ Median SAR: {np.nanmedian(metrics_data['SAR']):.2f} dB")
        print("-" * 40)
        
        return metrics_data
        
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        traceback.print_exc()
        return {}
