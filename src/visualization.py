{
  "nbformat": 4,
  "nbformat_minor": 0,
  "metadata": {
    "colab": {
      "provenance": [],
      "authorship_tag": "ABX9TyNevH2fV6iKVfWQW8cdBn9i",
      "include_colab_link": true
    },
    "kernelspec": {
      "name": "python3",
      "display_name": "Python 3"
    },
    "language_info": {
      "name": "python"
    }
  },
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {
        "id": "view-in-github",
        "colab_type": "text"
      },
      "source": [
        "<a href=\"https://colab.research.google.com/github/sjkim-audio/Bass-separator/blob/main/src/visualization.py\" target=\"_parent\"><img src=\"https://colab.research.google.com/assets/colab-badge.svg\" alt=\"Open In Colab\"/></a>"
      ]
    },
    {
      "cell_type": "code",
      "execution_count": 1,
      "metadata": {
        "id": "pPi6VdkOYbrv"
      },
      "outputs": [],
      "source": [
        "import librosa\n",
        "import librosa.display\n",
        "import matplotlib.pyplot as plt\n",
        "import numpy as np\n",
        "\n",
        "# 오디오 데이터 시각화\n",
        "def plot_spectrogram(audio_path, title=\"Spectrogram\", sr=44100):\n",
        "\n",
        "    y, sr = librosa.load(audio_path, sr=sr)\n",
        "\n",
        "    plt.figure(figsize=(12, 4))\n",
        "\n",
        "    # STFT (주파수 변환)\n",
        "    D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)\n",
        "\n",
        "    librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log')\n",
        "    plt.colorbar(format='%+2.0f dB')\n",
        "    plt.title(title)\n",
        "    plt.tight_layout()\n",
        "    plt.show()\n",
        "\n",
        "# 두 오디오 데이터 시각화 비교\n",
        "def compare_tracks(mix_path, bass_path):\n",
        "\n",
        "    y_mix, sr = librosa.load(mix_path, sr=None)\n",
        "    y_bass, _ = librosa.load(bass_path, sr=sr)\n",
        "\n",
        "    plt.figure(figsize=(14, 6))\n",
        "\n",
        "    plt.subplot(2, 1, 1)\n",
        "    librosa.display.waveshow(y_mix, sr=sr, alpha=0.6, color='gray')\n",
        "    plt.title(\"Original Mixture\")\n",
        "\n",
        "    plt.subplot(2, 1, 2)\n",
        "    librosa.display.waveshow(y_bass, sr=sr, alpha=0.8, color='blue')\n",
        "    plt.title(\"Separated Bass\")\n",
        "\n",
        "    plt.tight_layout()\n",
        "    plt.show()"
      ]
    }
  ]
}