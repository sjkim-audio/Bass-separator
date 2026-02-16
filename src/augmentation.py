import numpy as np
import librosa
import soundfile as sf
import random
import os
from pedalboard import Pedalboard, Distortion, Compressor, Gain, HighpassFilter

class AudioAugmentor:
    """
    베이스/기타 소스 분리 파인튜닝을 위한 동기화된 오디오 증강 클래스
    Pedalboard를 활용한 고품질 아날로그 질감 증강 포함
    """
    def __init__(self, sr=44100):
        self.sr = sr

    def load_audio(self, file_path):
        try:
            y, sr = librosa.load(file_path, sr=self.sr, mono=False)
            if y.ndim == 1:
                y = np.vstack([y, y])
            return y
        except Exception as e:
            print(f"오디오 로드 실패 ({file_path}): {e}")
            return None

    def save_audio(self, y, output_path):
        try:
            sf.write(output_path, y.T, self.sr)
        except Exception as e:
            print(f"저장 실패: {e}")

    def apply_pedalboard_drive(self, y, drive_db=25.0):
        """
        pedalboard를 활용하여 아날로그 질감의 디스토션과 컴프레서를 적용합니다.
        """
        board = Pedalboard([
            # 타격감을 살리기 위한 컴프레서
            Compressor(threshold_db=-15, ratio=4),
            # 메인 드라이브 질감
            Distortion(drive_db=drive_db),
            # 디스토션으로 인해 과도하게 부스트된 초저역대 럼블 노이즈 제거
            HighpassFilter(cutoff_frequency_hz=40),
            # 피크 방지 및 레벨 매칭을 위한 게인 감소
            Gain(gain_db=-3.0)
        ])
        
        effected_audio = board(y, self.sr)
        return effected_audio

    def process_multitrack(self, bass_path, other_path, output_dir, version_name, is_driven_source=False):
        """
        Bass와 Other 트랙을 동시에 불러와 음악적 맥락을 유지하며 증강하고 혼합합니다.
        is_driven_source: 이미 드라이브가 걸린 소스일 경우 True로 설정하여 이중 디스토션을 방지
        """
        os.makedirs(output_dir, exist_ok=True)

        bass = self.load_audio(bass_path)
        other = self.load_audio(other_path)

        if bass is None or other is None:
            return

        bass_gain = random.uniform(0.7, 1.2)
        other_gain = random.uniform(0.8, 1.1)
        
        # 드라이브가 걸리지 않은 Clean DI 소스일 경우에만 pedalboard 이펙터 적용
        if not is_driven_source and random.random() < 0.4:
            random_drive = random.uniform(15.0, 30.0)
            bass = self.apply_pedalboard_drive(bass, drive_db=random_drive)
            
        bass_aug = bass * bass_gain
        other_aug = other * other_gain

        n_steps = random.choice([-2, -1, 0, 1, 2])
        rate = random.uniform(0.9, 1.1)

        if n_steps != 0:
            bass_aug = librosa.effects.pitch_shift(bass_aug, sr=self.sr, n_steps=n_steps)
            other_aug = librosa.effects.pitch_shift(other_aug, sr=self.sr, n_steps=n_steps)
            
        if rate != 1.0:
            bass_aug = librosa.effects.time_stretch(bass_aug, rate=rate)
            other_aug = librosa.effects.time_stretch(other_aug, rate=rate)

        min_len = min(bass_aug.shape[1], other_aug.shape[1])
        bass_final = bass_aug[:, :min_len]
        other_final = other_aug[:, :min_len]

        mix_final = bass_final + other_final

        version_dir = os.path.join(output_dir, version_name)
        os.makedirs(version_dir, exist_ok=True)
        
        self.save_audio(mix_final, os.path.join(version_dir, "mixture.wav"))
        self.save_audio(bass_final, os.path.join(version_dir, "bass.wav"))
        self.save_audio(other_final, os.path.join(version_dir, "other.wav"))
        
        print(f"[{version_name}] 증강 세트 생성 완료: Pitch({n_steps}), Tempo({rate:.2f})")
