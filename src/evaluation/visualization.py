import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

def plot_spectrogram(y, sr, title="Spectrogram", ax=None, add_colorbar=False):
    """
    Plots the log-power spectrogram of an audio signal.
    """
    # STFT computation
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)

    # If no axes provided, create a new figure
    if ax is None:
        plt.figure(figsize=(12, 4))
        ax = plt.gca()

    # Draw spectrogram
    img = librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log', ax=ax)
    ax.set_title(title)
    
    # Add colorbar only if explicitly requested (usually for single plots)
    if add_colorbar and ax is not None:
        plt.colorbar(img, ax=ax, format='%+2.0f dB')
        
    return img

def compare_separation_visuals(ref_path, est_path, sr=44100):
    """
    Visually compares the Ground Truth (Reference) vs. Estimated Separation.
    """
    # Load Audio
    y_ref, _ = librosa.load(ref_path, sr=sr)
    y_est, _ = librosa.load(est_path, sr=sr)
    
    # Trim to minimum length
    min_len = min(len(y_ref), len(y_est))
    y_ref = y_ref[:min_len]
    y_est = y_est[:min_len]

    # Setup Plot (2 Rows x 2 Columns)
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    # 1. Waveform Comparison
    librosa.display.waveshow(y_ref, sr=sr, alpha=0.6, color='gray', ax=axes[0, 0])
    axes[0, 0].set_title("Waveform: Ground Truth (Clean Bass)")
    axes[0, 0].set_ylabel("Amplitude")

    librosa.display.waveshow(y_est, sr=sr, alpha=0.8, color='dodgerblue', ax=axes[1, 0])
    axes[1, 0].set_title("Waveform: Separated Output")
    axes[1, 0].set_ylabel("Amplitude")

    # 2. Spectrogram Comparison
    # We pass add_colorbar=False because we will add a shared one later
    plot_spectrogram(y_ref, sr, title="Spectrogram: Ground Truth", ax=axes[0, 1])
    img = plot_spectrogram(y_est, sr, title="Spectrogram: Separated Output", ax=axes[1, 1])
    
    # 3. Add Shared Colorbar manually to the right
    # [left, bottom, width, height] in figure coordinate
    plt.subplots_adjust(right=0.9) # Make room on the right
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7]) 
    fig.colorbar(img, cax=cbar_ax, format='%+2.0f dB')
    cbar_ax.set_ylabel('Intensity (dB)', rotation=270, labelpad=15)
    
    plt.suptitle(f"Separation Quality Analysis\nRef: {ref_path.split('/')[-1]} | Est: {est_path.split('/')[-1]}", fontsize=14)
    # plt.tight_layout() # Warning: tight_layout conflicts with add_axes, so we rely on manual adjust
    plt.show()

# Legacy support
def plot_single_track(audio_path, title="Spectrogram", sr=44100):
    y, sr = librosa.load(audio_path, sr=sr)
    img = plot_spectrogram(y, sr, title)
    plt.colorbar(img, format='%+2.0f dB')
    plt.tight_layout()
    plt.show()

def visualize_metrics(metrics, title="Separation Quality Over Time"):
    
    sdr = metrics['SDR']
    sir = metrics['SIR']
    sar = metrics['SAR']
    hop = metrics['hop_sec']

    if sdr is None or sir is None or sar is None:
        print("Error: Metrics dictionary must contain SDR, SIR, and SAR.")
        return
    
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

def plot_piano_roll(f0_array, sr=16000, hop_length=160):
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
