# 먼저 설치 필요: pip install museval
import museval
import numpy as np
import librosa

def evaluate_separation(reference_path, estimated_path):
    """
    업계 표준 BSSEval v4 방식으로 SDR, SIR, SAR을 측정하는 함수
    """
    # 1. 오디오 로드 (museval은 (n_channels, n_samples) 형태를 원함)
    # 반드시 원본(reference)과 분리본(estimated)의 길이가 같아야 함
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _ = librosa.load(estimated_path, sr=None, mono=False)
    
    # 길이가 다르면 짧은 쪽에 맞춤 (필수 전처리)
    min_len = min(ref.shape[1], est.shape[1])
    ref = ref[:, :min_len]
    est = est[:, :min_len]

    # 형태 변환 (Shape 맞추기: 채널, 샘플, 1) -> museval 요구사항
    # 모노일 경우 차원 추가 필요
    if ref.ndim == 1:
        ref = ref.reshape(1, -1)
        est = est.reshape(1, -1)
        
    ref = ref.reshape(ref.shape[0], ref.shape[1], 1)
    est = est.reshape(est.shape[0], est.shape[1], 1)

    # 2. 평가 실행 (BSSEval)
    # win: 평가 윈도우 크기 (보통 1초=44100 샘플 단위로 쪼개서 평균냄)
    sdr, isr, sir, sar, _ = museval.eval_bss_v4(ref, est, win=sr)

    # 3. 결과값 평균내기 (구간별 평균)
    metrics = {
        "SDR (종합 점수)": np.nanmedian(sdr),
        "SIR (분리도/간섭)": np.nanmedian(sir),
        "SAR (음질/아티팩트)": np.nanmedian(sar)
    }
    
    return metrics
