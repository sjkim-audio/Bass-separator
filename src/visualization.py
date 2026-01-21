import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

# 오디오 데이터 시각화
def plot_spectrogram(audio_path, title="Spectrogram", sr=44100):

    y, sr = librosa.load(audio_path, sr=sr)

    plt.figure(figsize=(12, 4))

    # STFT (주파수 변환)
    D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)

    librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')
    plt.colorbar(format='%+2.0f dB')
    plt.title(title)
    plt.tight_layout()
    plt.show()

# 두 오디오 데이터 시각화 비교
def compare_tracks(mix_path, bass_path):

    y_mix, sr = librosa.load(mix_path, sr=None)
    y_bass, _ = librosa.load(bass_path, sr=sr)

    plt.figure(figsize=(14, 6))

    plt.subplot(2, 1, 1)
    librosa.display.waveshow(y_mix, sr=sr, alpha=0.6, color='gray')
    plt.title("Original Mixture")

    plt.subplot(2, 1, 2)
    librosa.display.waveshow(y_bass, sr=sr, alpha=0.8, color='blue')
    plt.title("Separated Bass")

    plt.tight_layout()
    plt.show()
