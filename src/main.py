import os
import argparse
import asyncio
import warnings
import torch
import traceback

# 파이프라인 모듈 임포트
from core.demucs_runner import separate_and_generate_stems
from core.pipeline import run_transcription_pipeline

warnings.filterwarnings('ignore', category=UserWarning)

async def process_audio(input_path: str, skip_separation: bool):
    """비동기 Demucs 실행 및 채보 파이프라인을 통괄하는 메인 컨트롤러"""
    bass_path = input_path
    bassless_path = input_path

    if not skip_separation:
        print(f"🎸 [Phase 1] Separating bass track from: {input_path}")
        output_dir = "separated"
        bass_path, bassless_path = await separate_and_generate_stems(input_path, output_dir=output_dir)
    else:
        print(f"⚡ [Phase 1] Skipping separation. Assuming '{input_path}' is an isolated bass track.")
        bassless_path = None 

    # [수정] 반환값 언패킹 확장
    ascii_tab, bpm, _, _ = run_transcription_pipeline(bass_path, bassless_path)
    return ascii_tab, bpm

def main():
    parser = argparse.ArgumentParser(description="End-to-End Automatic Bass Transcription Pipeline")
    parser.add_argument("-i", "--input", type=str, required=True, help="Path to the mixed audio file (.wav, .mp3)")
    parser.add_argument("--skip_separation", action="store_true", help="If set, assumes input is already a bass track and skips Demucs")
    
    args = parser.parse_args()

    # VRAM 초기화
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        
    try:
        ascii_tab, bpm = asyncio.run(process_audio(args.input, args.skip_separation))
        print("\n" + "="*50)
        print(ascii_tab)
        print("="*50 + "\n")
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
