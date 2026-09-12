import os
import json
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

def plot_spectrogram(y, sr, title="Spectrogram", ax=None, add_colorbar=False):
    """
    Plots the log-power spectrogram of an audio signal.
    """
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)

    if ax is None:
        plt.figure(figsize=(12, 4))
        ax = plt.gca()

    img = librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log', ax=ax)
    ax.set_title(title)
    
    if add_colorbar and ax is not None:
        plt.colorbar(img, ax=ax, format='%+2.0f dB')
        
    return img

def compare_separation_visuals(ref_path, est_path, sr=44100):
    """
    Visually compares the Ground Truth (Reference) vs. Estimated Separation.
    """
    y_ref, _ = librosa.load(ref_path, sr=sr)
    y_est, _ = librosa.load(est_path, sr=sr)
    
    min_len = min(len(y_ref), len(y_est))
    y_ref = y_ref[:min_len]
    y_est = y_est[:min_len]

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    librosa.display.waveshow(y_ref, sr=sr, alpha=0.6, color='gray', ax=axes[0, 0])
    axes[0, 0].set_title("Waveform: Ground Truth (Clean Bass)")
    axes[0, 0].set_ylabel("Amplitude")

    librosa.display.waveshow(y_est, sr=sr, alpha=0.8, color='dodgerblue', ax=axes[1, 0])
    axes[1, 0].set_title("Waveform: Separated Output")
    axes[1, 0].set_ylabel("Amplitude")

    plot_spectrogram(y_ref, sr, title="Spectrogram: Ground Truth", ax=axes[0, 1])
    img = plot_spectrogram(y_est, sr, title="Spectrogram: Separated Output", ax=axes[1, 1])
    
    plt.subplots_adjust(right=0.9)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7]) 
    fig.colorbar(img, cax=cbar_ax, format='%+2.0f dB')
    cbar_ax.set_ylabel('Intensity (dB)', rotation=270, labelpad=15)
    
    plt.suptitle(f"Separation Quality Analysis\nRef: {ref_path.split('/')[-1]} | Est: {est_path.split('/')[-1]}", fontsize=14)
    plt.show()

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

def visualize_batch_results(json_path: str):
    """
    [Macro-level Visualization] 
    대규모 배치 평가(batch_results.json) 결과를 파싱하여 거시적 성능 트렌드를 시각화합니다.
    """
    if not os.path.exists(json_path):
        print(f"❌ 파일을 찾을 수 없습니다: {json_path}")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    records = []
    for item in data.get('details', []):
        track = item.get('track', 'Unknown')
        metrics = item.get('metrics', {})
        
        if 'quantized' in metrics:
            f1 = metrics['quantized'].get('Onset_Pitch_F1', 0)
            sdr = metrics.get('separation', {}).get('SDR', np.nan)
            records.append({'Track': track, 'F1_Score': f1, 'SDR': sdr})
            
    if not records:
        print("⚠️ 시각화할 유효한 평가 데이터가 JSON 파일에 존재하지 않습니다.")
        return
        
    df = pd.DataFrame(records)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    sns.set_theme(style="whitegrid")

    # 1. Boxplot (Outlier detection)
    sns.boxplot(y=df['F1_Score'], ax=axes[0], color='skyblue')
    axes[0].set_title('E2E F1 Score Distribution', fontweight='bold')
    axes[0].set_ylabel('F1 Score')

    # 2. Scatter Plot (Cascading Error Correlation)
    if not df['SDR'].isna().all():
        sns.regplot(x='SDR', y='F1_Score', data=df, ax=axes[1], scatter_kws={'alpha':0.6}, line_kws={'color':'red'})
        axes[1].set_title('Correlation: Separation (SDR) vs Transcription (F1)', fontweight='bold')
        axes[1].set_xlabel('SDR (dB)')
        axes[1].set_ylabel('F1 Score')
    else:
        axes[1].text(0.5, 0.5, 'SDR Data Not Available\n(Isolated Mode or Missing)', ha='center', va='center', fontsize=12)
        axes[1].set_title('Correlation Unavailable')

    # 3. KDE Plot (Density Distribution)
    sns.kdeplot(df['F1_Score'], fill=True, ax=axes[2], color='coral')
    axes[2].set_title('F1 Score Density', fontweight='bold')
    axes[2].set_xlabel('F1 Score')

    plt.tight_layout()
    plt.show()
