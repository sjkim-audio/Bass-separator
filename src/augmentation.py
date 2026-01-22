import numpy as np
import librosa
import soundfile as sf
import random
import os

class AudioAugmentor:
    """
    오디오 데이터 증강을 위한 전문 클래스
    베이스/기타 소스 분리 성능 향상을 위해 
    Pitch, Time, Gain, Distortion 효과를 제공합니다.
    """

    def __init__(self, sr=44100):
        self.sr = sr

    def load_audio(self, file_path):
        """오디오 로드 (예외 처리 포함)"""
        try:
            y, sr = librosa.load(file_path, sr=self.sr)
            return y
        except Exception as e:
            print(f"❌ 오디오 로드 실패 ({file_path}): {e}")
            return None

    def save_audio(self, y, output_path):
        """오디오 저장"""
        try:
            sf.write(output_path, y, self.sr)
            print(f"💾 저장 완료: {output_path}")
        except Exception as e:
            print(f"❌ 저장 실패: {e}")

    # ------------------------------------------------
    # 1. Pitch Shift (조옮김)
    # ------------------------------------------------
    def pitch_shift(self, y, n_steps):
        """
        n_steps: 반음 단위 이동 (예: 2 = 1음 올림, -1 = 반음 내림)
        """
        return librosa.effects.pitch_shift(y, sr=self.sr, n_steps=n_steps)

    # ------------------------------------------------
    # 2. Time Stretch (템포 조절)
    # ------------------------------------------------
    def time_stretch(self, y, rate):
        """
        rate: 속도 비율 (예: 0.8 = 느리게, 1.2 = 빠르게)
        """
        return librosa.effects.time_stretch(y, rate=rate)

    # ------------------------------------------------
    # 3. Random Gain (볼륨 조절) - 믹싱 밸런스 훈련용
    # ------------------------------------------------
    def apply_random_gain(self, y, min_gain=0.7, max_gain=1.3):
        """
        볼륨을 랜덤하게 70% ~ 130% 사이로 조절
        """
        gain = random.uniform(min_gain, max_gain)
        return y * gain

    # ------------------------------------------------
    # 4. Hard Clipping (Distortion 효과) - 락/메탈 베이스용
    # ------------------------------------------------
    def apply_distortion(self, y, threshold=0.8):
        """
        파형을 강제로 잘라내어(Clipping) 드라이브 톤을 흉내냄
        threshold가 낮을수록 소리가 더 많이 찌그러짐 (0.0 ~ 1.0)
        """
        # 1. Gain을 키워서 파형을 천장에 닿게 함
        y_boosted = y * (1.0 / threshold)
        # 2. 천장을 넘는 부분을 잘라냄 (Hard Clip)
        y_clipped = np.clip(y_boosted, -1.0, 1.0)
        # 3. 볼륨 보정 (다시 원래 레벨 비슷하게)
        return y_clipped * threshold

    # ------------------------------------------------
    # [종합] 파일 하나를 3가지 버전으로 증강하는 함수
    # ------------------------------------------------
    def generate_augmented_files(self, input_path, output_folder):
        """
        하나의 파일을 입력받아, Pitch, Speed, Distortion 버전을 생성하여 저장
        """
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        filename = os.path.splitext(os.path.basename(input_path))[0]
        y = self.load_audio(input_path)

        if y is None: return

        # Case 1: 피치 올림 (+2 semitones)
        y_pitch = self.pitch_shift(y, n_steps=2)
        self.save_audio(y_pitch, os.path.join(output_folder, f"{filename}_pitch_up.wav"))

        # Case 2: 속도 느리게 (0.9x)
        y_slow = self.time_stretch(y, rate=0.9)
        self.save_audio(y_slow, os.path.join(output_folder, f"{filename}_slow.wav"))

        # Case 3: 디스토션 (Drive Tone) 
        y_dist = self.apply_distortion(y, threshold=0.6)
        self.save_audio(y_dist, os.path.join(output_folder, f"{filename}_dist.wav"))
        
        print(f"✨ {filename} 증강 완료 (3개 파일 생성됨)")
