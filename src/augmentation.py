import numpy as np
import librosa
import soundfile as sf
import random
import os

class AudioAugmentor:
    """
    베이스/기타 소스 분리 파인튜닝을 위한 동기화된 오디오 증강 클래스
    """
    def __init__(self, sr=44100):
        self.sr = sr

    def load_audio(self, file_path):
        # mono=False로 설정하여 스테레오 채널 유지 [2, n_samples]
        try:
            y, sr = librosa.load(file_path, sr=self.sr, mono=False)
            # 만약 모노 파일이라면 강제로 스테레오로 복사
            if y.ndim == 1:
                y = np.vstack([y, y])
            return y
        except Exception as e:
            print(f"오디오 로드 실패 ({file_path}): {e}")
            return None

    def save_audio(self, y, output_path):
        try:
            # soundfile은 [n_samples, channels] 형태를 요구하므로 전치(Transpose) 필요
            sf.write(output_path, y.T, self.sr)
        except Exception as e:
            print(f"저장 실패: {e}")

    def apply_distortion(self, y, threshold=0.8):
        if threshold < 0.5:
            threshold = 0.5
        y_boosted = y * (1.0 / threshold)
        y_clipped = np.clip(y_boosted, -1.0, 1.0)
        return y_clipped * threshold

    def process_multitrack(self, bass_path, other_path, output_dir, version_name):
        """
        Bass와 Other 트랙을 동시에 불러와 음악적 맥락을 유지하며 증강하고 혼합합니다.
        """
        os.makedirs(output_dir, exist_ok=True)

        bass = self.load_audio(bass_path)
        other = self.load_audio(other_path)

        if bass is None or other is None:
            return

        # 1. 독립적 증강 (Stem-specific): 베이스의 톤과 트랙별 믹싱 볼륨 랜덤화
        bass_gain = random.uniform(0.7, 1.2)
        other_gain = random.uniform(0.8, 1.1)
        
        # 베이스에만 30% 확률로 디스토션 적용 (Hard Case 훈련)
        if random.random() < 0.3:
            bass = self.apply_distortion(bass, threshold=random.uniform(0.6, 0.9))
            
        bass_aug = bass * bass_gain
        other_aug = other * other_gain

        # 2. 전역적 증강 (Global): 두 트랙에 완벽히 동일한 Pitch/Time 적용
        # 피치는 -2 ~ +2 반음 사이 정수, 템포는 0.9 ~ 1.1 사이
        n_steps = random.choice([-2, -1, 0, 1, 2])
        rate = random.uniform(0.9, 1.1)

        if n_steps != 0:
            bass_aug = librosa.effects.pitch_shift(bass_aug, sr=self.sr, n_steps=n_steps)
            other_aug = librosa.effects.pitch_shift(other_aug, sr=self.sr, n_steps=n_steps)
            
        if rate != 1.0:
            bass_aug = librosa.effects.time_stretch(bass_aug, rate=rate)
            other_aug = librosa.effects.time_stretch(other_aug, rate=rate)

        # 3. 데이터 길이 맞춤 (Time Stretch 시 미세한 샘플 차이 보정)
        min_len = min(bass_aug.shape[1], other_aug.shape[1])
        bass_final = bass_aug[:, :min_len]
        other_final = other_aug[:, :min_len]

        # 4. 혼합 (Mixture 생성) - 수학적 합산 보장
        mix_final = bass_final + other_final

        # 5. 파인튜닝 규격에 맞게 저장
        version_dir = os.path.join(output_dir, version_name)
        os.makedirs(version_dir, exist_ok=True)
        
        self.save_audio(mix_final, os.path.join(version_dir, "mixture.wav"))
        self.save_audio(bass_final, os.path.join(version_dir, "bass.wav"))
        self.save_audio(other_final, os.path.join(version_dir, "other.wav"))
        
        print(f"[{version_name}] 증강 세트 생성 완료: Pitch({n_steps}), Tempo({rate:.2f})")
