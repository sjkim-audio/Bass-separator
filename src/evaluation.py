import os
import numpy as np
import librosa
import scipy.signal
import museval
import matplotlib.pyplot as plt

def align_audio(ref, est, sr=44100):
    """
    [전처리] Cross-Correlation을 사용하여 두 오디오 간의 시간 지연(Latency)을 보정
    """
    # 1. 길이 맞추기 (짧은 쪽에 맞춤)
    min_len = min(ref.shape[1], est.shape[1])
    ref = ref[:, :min_len]
    est = est[:, :min_len]
    
    # 2. 정렬을 위해 모노로 변환 (속도 최적화: 앞부분 30초만 사용)
    max_corr_len = sr * 30
    ref_mono = np.mean(ref, axis=0) if ref.ndim > 1 else ref
    est_mono = np.mean(est, axis=0) if est.ndim > 1 else est
    
    curr_len = min(len(ref_mono), max_corr_len)
    
    # 3. 상호 상관관계 계산
    correlation = scipy.signal.correlate(
        ref_mono[:curr_len], 
        est_mono[:curr_len], 
        mode='full'
    )
    
    # 4. 가장 높은 상관관계를 갖는 지점(Lag) 찾기
    lag = np.argmax(correlation) - (curr_len - 1)
    
    # 5. 시간 이동 적용 (Shift)
    if lag > 0:
        # Est가 Ref보다 앞서 있음 -> 뒤로 밀기
        est = est[:, lag:]
        ref = ref[:, :-lag]
    elif lag < 0:
        # Est가 Ref보다 뒤쳐짐 (Latency) -> 앞으로 당기기
        lag = abs(lag)
        est = est[:, :-lag]
        ref = ref[:, lag:]
        
    return ref, est

def calculate_metrics(reference_path, estimated_path, win_sec=1.0):
    """
    [평가] BSSEval v4를 사용하여 구간별(Window) SDR, SIR, SAR 계산
    """
    # 1. 오디오 로드
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _ = librosa.load(estimated_path, sr=sr, mono=False)
    
    # 2. 채널 차원 확보 (1D -> 2D)
    if ref.ndim == 1: ref = ref[np.newaxis, :]
    if est.ndim == 1: est = est[np.newaxis, :]
    
    # 3. 시간 정렬 수행
    ref, est = align_audio(ref, est, sr)
    
    # 4. Museval 입력 형태 변환: (n_sources, n_samples, n_channels)
    # n_sources=1 (Single Track Evaluation)
    ref_eval = ref.T[np.newaxis, :, :]
    est_eval = est.T[np.newaxis, :, :]
    
    # 5. 평가 실행 (win_sec 단위로 분할 평가)
    # win 파라미터는 샘플 수 단위임
    win_samples = int(win_sec * sr)
    sdr, isr, sir, sar, _ = museval.eval_bss_v4(ref_eval, est_eval, win=win_samples, hop=win_samples)
    
    # 6. 결과 딕셔너리 반환 (차원 축소: 1, Windows -> Windows)
    return {
        "SDR": sdr.squeeze(),
        "SIR": sir.squeeze(),
        "SAR": sar.squeeze(),
        "sr": sr,
        "hop_sec": win_sec
    }

def visualize_metrics(metrics, title="Separation Quality Over Time"):
    """
    [시각화] 시간에 따른 성능 지표 변화를 그래프로 출력
    """
    sdr = metrics['SDR']
    sir = metrics['SIR']
    sar = metrics['SAR']
    hop = metrics['hop_sec']
    
    # 시간축 생성
    time_axis = np.arange(len(sdr)) * hop
    
    # 전체 평균 계산 (NaN 제외)
    avg_sdr = np.nanmedian(sdr)
    avg_sir = np.nanmedian(sir)
    avg_sar = np.nanmedian(sar)
    
    plt.figure(figsize=(14, 6))
    
    # 메인 플롯
    plt.plot(time_axis, sdr, label=f'SDR (Overall Quality): avg {avg_sdr:.1f}dB', color='dodgerblue', linewidth=2)
    plt.plot(time_axis, sir, label=f'SIR (Interference): avg {avg_sir:.1f}dB', color='forestgreen', linewidth=1.5, linestyle='--', alpha=0.7)
    plt.plot(time_axis, sar, label=f'SAR (Artifacts): avg {avg_sar:.1f}dB', color='salmon', linewidth=1.5, linestyle=':', alpha=0.7)
    
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel("Time (seconds)", fontsize=12)
    plt.ylabel("Score (dB)", fontsize=12)
    plt.legend(loc='lower right', frameon=True, fontsize=11)
    plt.grid(True, linestyle='-', alpha=0.3)
    
    # 점수 범위 고정 (가독성을 위해 -10 ~ 30dB 사이 표시, 필요 시 조정)
    plt.ylim(-5, 30)
    
    plt.tight_layout()
    plt.show()

def run_evaluation(ref_path, est_path, show_plot=True):
    """
    [메인] 파일 경로만 넣으면 모든 과정을 수행하는 래퍼 함수
    """
    print(f"📊 Processing: {os.path.basename(est_path)}")
    
    try:
        # 1. 계산
        metrics = calculate_metrics(ref_path, est_path)
        
        # 2. 콘솔 출력
        print("-" * 40)
        print(f"🔹 Summary Statistics")
        print("-" * 40)
        print(f"✅ Median SDR: {np.nanmedian(metrics['SDR']):.2f} dB")
        print(f"✅ Median SIR: {np.nanmedian(metrics['SIR']):.2f} dB")
        print(f"✅ Median SAR: {np.nanmedian(metrics['SAR']):.2f} dB")
        print("-" * 40)
        
        # 3. 그래프 출력
        if show_plot:
            visualize_metrics(metrics, title=f"Quality Analysis: {os.path.basename(est_path)}")
            
        return metrics
        
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return None
