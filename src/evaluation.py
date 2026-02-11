import os
import numpy as np
import librosa
import scipy.signal
import museval
from museval import metrics  # 핵심: metrics 모듈을 명시적으로 임포트

def align_audio(ref, est, sr=44100):
    """
    [전처리] Cross-Correlation을 사용하여 두 오디오 간의 시간 지연(Latency)을 보정
    """
    min_len = min(ref.shape[1], est.shape[1])
    ref = ref[:, :min_len]
    est = est[:, :min_len]
    
    max_corr_len = sr * 30
    ref_mono = np.mean(ref, axis=0) if ref.ndim > 1 else ref
    est_mono = np.mean(est, axis=0) if est.ndim > 1 else est
    
    curr_len = min(len(ref_mono), max_corr_len)
    
    correlation = scipy.signal.correlate(
        ref_mono[:curr_len], 
        est_mono[:curr_len], 
        mode='full'
    )
    
    lag = np.argmax(correlation) - (curr_len - 1)
    
    if lag > 0:
        est = est[:, lag:]
        ref = ref[:, :-lag]
    elif lag < 0:
        lag = abs(lag)
        est = est[:, :-lag]
        ref = ref[:, lag:]
        
    return ref, est

def calculate_metrics(reference_path, estimated_path, win_sec=1.0):
    """
    [평가] museval.metrics.bss_eval을 사용하여 구간별 SDR, SIR, SAR 계산
    """
    # 1. 오디오 로드
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _ = librosa.load(estimated_path, sr=sr, mono=False)
    
    # 2. 채널 차원 확보
    if ref.ndim == 1: ref = ref[np.newaxis, :]
    if est.ndim == 1: est = est[np.newaxis, :]
    
    # 3. 시간 정렬
    ref, est = align_audio(ref, est, sr)
    
    # 4. Museval 형태 변환: (n_src, n_samples, n_channels)
    ref_eval = ref.T[np.newaxis, :, :]
    est_eval = est.T[np.newaxis, :, :]
    
    # 5. 평가 실행 (함수명 및 인자 수정됨)
    # win -> window, hop -> hop
    win_samples = int(win_sec * sr)
    
    # museval.metrics.bss_eval 사용
    sdr, isr, sir, sar, _ = metrics.bss_eval(
        ref_eval, 
        est_eval, 
        window=win_samples, 
        hop=win_samples
    )
    
    return {
        "SDR": sdr.squeeze(),
        "SIR": sir.squeeze(),
        "SAR": sar.squeeze(),
        "sr": sr,
        "hop_sec": win_sec
    }

def visualize_metrics(metrics, title="Separation Quality Over Time"):
    # (이전 코드와 동일, 생략 가능하지만 완전성을 위해 유지하는 것이 좋음)
    import matplotlib.pyplot as plt
    
    sdr = metrics['SDR']
    sir = metrics['SIR']
    sar = metrics['SAR']
    hop = metrics['hop_sec']
    
    time_axis = np.arange(len(sdr)) * hop
    
    avg_sdr = np.nanmedian(sdr)
    avg_sir = np.nanmedian(sir)
    avg_sar = np.nanmedian(sar)
    
    plt.figure(figsize=(14, 6))
    plt.plot(time_axis, sdr, label=f'SDR (Overall Quality): avg {avg_sdr:.1f}dB', color='dodgerblue', linewidth=2)
    plt.plot(time_axis, sir, label=f'SIR (Interference): avg {avg_sir:.1f}dB', color='forestgreen', linewidth=1.5, linestyle='--', alpha=0.7)
    plt.plot(time_axis, sar, label=f'SAR (Artifacts): avg {avg_sar:.1f}dB', color='salmon', linewidth=1.5, linestyle=':', alpha=0.7)
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel("Time (seconds)", fontsize=12)
    plt.ylabel("Score (dB)", fontsize=12)
    plt.legend(loc='lower right', frameon=True, fontsize=11)
    plt.grid(True, linestyle='-', alpha=0.3)
    plt.ylim(-5, 30)
    plt.tight_layout()
    plt.show()

def run_evaluation(ref_path, est_path, show_plot=True):
    print(f"📊 Processing: {os.path.basename(est_path)}")
    try:
        metrics_data = calculate_metrics(ref_path, est_path)
        
        print("-" * 40)
        print(f"🔹 Summary Statistics")
        print("-" * 40)
        print(f"✅ Median SDR: {np.nanmedian(metrics_data['SDR']):.2f} dB")
        print(f"✅ Median SIR: {np.nanmedian(metrics_data['SIR']):.2f} dB")
        print(f"✅ Median SAR: {np.nanmedian(metrics_data['SAR']):.2f} dB")
        print("-" * 40)
        
        if show_plot:
            visualize_metrics(metrics_data, title=f"Quality Analysis: {os.path.basename(est_path)}")
            
        return metrics_data
        
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        import traceback
        traceback.print_exc() # 에러 상세 출력 추가
        return None
