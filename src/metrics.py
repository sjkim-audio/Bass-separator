import museval
import numpy as np
import librosa
import scipy.signal

def align_audio(ref, est, sr=44100):
    """
    Synchronizes the estimated audio with the reference audio using cross-correlation.
    This corrects minor latency issues introduced by the separation model.
    """
    # Use the first 30 seconds for alignment to speed up calculation
    max_len = sr * 30
    
    # Convert to mono for correlation calculation
    ref_mono = np.mean(ref, axis=0) if ref.ndim > 1 else ref
    est_mono = np.mean(est, axis=0) if est.ndim > 1 else est
    
    # Calculate cross-correlation
    correlation = scipy.signal.correlate(
        ref_mono[:max_len], 
        est_mono[:max_len], 
        mode='full'
    )
    
    # Find the lag (shift amount)
    lag = np.argmax(correlation) - (len(est_mono[:max_len]) - 1)
    
    # Apply shift
    if lag > 0:
        # Estimated is ahead of Reference
        est = est[:, lag:]
        ref = ref[:, :-lag]
    elif lag < 0:
        # Estimated is behind Reference (Latency)
        lag = abs(lag)
        est = est[:, :-lag]
        ref = ref[:, lag:]
        
    return ref, est

def evaluate_separation(reference_path, estimated_path, align=True):
    """
    Evaluates separation quality using BSSEval v4 metrics (SDR, SIR, SAR).
    
    Args:
        reference_path (str): Path to the ground truth (clean) file.
        estimated_path (str): Path to the separated (model output) file.
        align (bool): Whether to correct temporal alignment before evaluation.
        
    Returns:
        dict: Dictionary containing median SDR, SIR, and SAR scores.
    """
    # 1. Load Audio (Keep original SR)
    ref, sr = librosa.load(reference_path, sr=None, mono=False)
    est, _ = librosa.load(estimated_path, sr=sr, mono=False)

    # 2. Ensure Channel Dimension (Mono -> Stereo shape)
    if ref.ndim == 1: ref = ref[np.newaxis, :]
    if est.ndim == 1: est = est[np.newaxis, :]

    # 3. Trim to Minimum Length
    min_len = min(ref.shape[1], est.shape[1])
    ref = ref[:, :min_len]
    est = est[:, :min_len]

    # 4. Temporal Alignment (Crucial for deep learning models)
    if align:
        ref, est = align_audio(ref, est, sr)

    # 5. Reshape for Museval: (n_sources, n_samples, n_channels)
    # We evaluate 1 source (Bass)
    ref_eval = ref.T[np.newaxis, :, :]
    est_eval = est.T[np.newaxis, :, :]

    # 6. Run BSSEval v4
    # win=sr sets the evaluation window to 1 second
    sdr, isr, sir, sar, _ = museval.eval_bss_v4(ref_eval, est_eval, win=sr)

    # 7. Aggregate Results (Median)
    metrics = {
        "SDR": np.nanmedian(sdr),
        "SIR": np.nanmedian(sir),
        "SAR": np.nanmedian(sar)
    }

    return metrics
