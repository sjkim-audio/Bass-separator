import os
import argparse
import subprocess
import warnings
import librosa
import torch

# 파이프라인 모듈 임포트
from transcription.tracker import get_f0_crepe_robust
from transcription.parser import PitchParser
from transcription.fingering import ViterbiSmartFingering
from transcription.quantization import RhythmicQuantizer
from renderers.tab_renderer import TabRenderer

warnings.filterwarnings('ignore', category=UserWarning)

def separate_bass_track(input_path: str, output_dir: str = "separated") -> str:
    """
    [Phase 1] Demucs를 활용하여 믹스 오디오에서 베이스 트랙 분리.
    Python API 래퍼 구현 대신, VRAM 누수 방지와 안전한 프로세스 격리를 위해 subprocess를 사용.
    """
    print(f"🎸 [Phase 1] Separating bass track from: {input_path}")
    os.makedirs(output_dir, exist_ok=True)
    
    # htdemucs 모델 사용, bass 트랙만 추출하여 연산량 최적화
    command = [
        "demucs", "-n", "htdemucs", 
        "--two-stems", "bass", 
        "--out", output_dir, 
        input_path
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        raise RuntimeError("❌ Demucs 분리 과정에서 오류가 발생했습니다. FFmpeg 및 Demucs 설치를 확인하세요.")

    # 추출된 파일 경로 조립 (demucs 기본 출력 구조: output_dir/htdemucs/파일명/bass.wav)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    bass_audio_path = os.path.join(output_dir, "htdemucs", base_name, "bass.wav")
    
    if not os.path.exists(bass_audio_path):
        raise FileNotFoundError(f"❌ 분리된 파일을 찾을 수 없습니다: {bass_audio_path}")
        
    print(f"✅ Bass track successfully separated: {bass_audio_path}")
    return bass_audio_path

def run_transcription_pipeline(bass_audio_path: str):
    """
    [Phase 2~4] 분리된 베이스 오디오를 기반 타브 악보를 생성.
    """
    
    sr, hop_length = 16000, 160
    
    print(f"📂 Loading audio for transcription...")
    y, sr = librosa.load(bass_audio_path, sr=sr, mono=True)
    
    print("🚀 [Phase 2] Running CREPE Pitch Tracking...")
    f0 = get_f0_crepe_robust(audio=y, sr=sr, hop_length=hop_length, model_capacity='tiny')

    print("🧩 [Phase 3] Parsing F0 & Optimizing Fingering (Viterbi)...")
    parser = PitchParser(sr=sr, hop_length=hop_length)
    raw_events = parser.parse_f0_to_events(f0_array=f0)
    
    viterbi = ViterbiSmartFingering()
    fingered_events = viterbi.decode(raw_events, parser.get_fret_candidates)
    
    print("⏱️ [Phase 4] Quantizing rhythms...")
    quantizer = RhythmicQuantizer(sr=sr, hop_length=hop_length)
    bpm = quantizer.estimate_bpm_and_grid(y)
    quantized_events = quantizer.quantize_events(fingered_events)

    print("\n" + "="*50)
    TabRenderer.render_quantized_tab(quantized_events, bpm)
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="End-to-End Automatic Bass Transcription Pipeline")
    parser.add_argument("-i", "--input", type=str, required=True, help="Path to the mixed audio file (.wav, .mp3)")
    parser.add_argument("--skip_separation", action="store_true", help="If set, assumes input is already a bass track and skips Demucs")
    
    args = parser.parse_args()

    # VRAM 초기화
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    try:
        # 1. Separation (조건부 실행)
        if args.skip_separation:
            print("⏭️ Skipping separation phase. Assuming input is an isolated bass track.")
            target_audio = args.input
        else:
            target_audio = separate_bass_track(args.input)
        
        # 2. Transcription
        run_transcription_pipeline(target_audio)
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")

if __name__ == "__main__":
    main()
