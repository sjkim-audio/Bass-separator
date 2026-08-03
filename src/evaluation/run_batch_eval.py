# src/evaluation/run_batch_eval.py

import os
import argparse
import asyncio
import numpy as np
import json
import gc
import torch
import shutil
import librosa
import soundfile as sf
from pathlib import Path
from tqdm.auto import tqdm

from src.evaluation.evaluator import run_transcription_evaluation, evaluate_separation, align_audio
from src.core.demucs_runner import separate_and_generate_stems

async def run_batch(test_dir: str, task: str, onset_tolerance: float, exp_id: str):
    base_path = Path(test_dir)
    track_dirs = [d for d in base_path.iterdir() if d.is_dir() and d.name.startswith("Track")]
    
    print(f"🔍 총 {len(track_dirs)}곡 벤치마크 시작 (Task: {task})")
    
    results = []
    
    # Transcription 성능 집계
    f1_scores_raw, f1_scores_quantized = [], []
    precision_quantized, recall_quantized = [], []
    chroma_f1_scores, octave_errors = [], []
    
    # Separation 성능 집계
    sdr_scores, sir_scores, sar_scores = [], [], []
    
    out_json = f"results/{exp_id}_batch_results.json"
    os.makedirs("results", exist_ok=True)
    temp_out_dir = "outputs/eval_temp"
    
    for track_dir in tqdm(track_dirs, desc="Evaluating Tracks"):
        ref_midi = str(track_dir / "bass_gt.mid")
        mix_audio = str(track_dir / "mix.wav")
        ref_audio = str(track_dir / "bass_gt.wav")
        
        if not os.path.exists(ref_midi) or not os.path.exists(ref_audio):
            continue
            
        try:
            metrics_payload = {}
            
            # -------------------------------------------------------------
            # [Task 1] 순수 채보 성능 측정 (Demucs 및 분리 채점 생략)
            # -------------------------------------------------------------
            if task == "isolated":
                metrics_payload = await run_transcription_evaluation(
                    ref_midi_path=ref_midi, 
                    audio_path=ref_audio, # 정답 오디오 직접 주입
                    is_isolated=True, 
                    onset_tolerance=onset_tolerance
                )
            
            # -------------------------------------------------------------
            # [Task 2] E2E 실사용 채보 성능 측정 (Demucs 가동, 분리 채점은 생략하여 속도 극대화)
            # -------------------------------------------------------------
            elif task == "e2e":
                metrics_payload = await run_transcription_evaluation(
                    ref_midi_path=ref_midi, 
                    audio_path=mix_audio, 
                    is_isolated=False, 
                    onset_tolerance=onset_tolerance,
                    ref_audio_path=ref_audio 
                    # evaluator.py 내부에서 museval 채점이 실패해도 에러를 무시하고 
                    # transcription은 진행하도록 이미 예외처리 되어있으므로そのまま 호출
                )
            
            # -------------------------------------------------------------
            # [Task 3] 순수 분리 성능 측정 (CREPE 채보 연산 완전 생략)
            # -------------------------------------------------------------
            elif task == "sep":
                bass_path, _ = await separate_and_generate_stems(mix_audio, output_dir=temp_out_dir)
                # Latency Alignment
                ref_wav, sr = librosa.load(ref_audio, sr=None, mono=True)
                est_wav, _ = librosa.load(bass_path, sr=sr, mono=True)
                _, aligned_est = align_audio(ref_wav, est_wav, sr)
                
                aligned_bass_path = os.path.join(temp_out_dir, "bass_aligned.wav")
                sf.write(aligned_bass_path, aligned_est, sr)
                
                sep_raw = evaluate_separation(ref_audio, aligned_bass_path, align=False)
                
                metrics_payload = {
                    "separation": {
                        "SDR": float(np.nanmedian(sep_raw["SDR"])),
                        "SIR": float(np.nanmedian(sep_raw["SIR"])),
                        "SAR": float(np.nanmedian(sep_raw["SAR"]))
                    }
                }
            
            # -------------------------------------------------------------
            # 메트릭 파싱 및 메모리 누적
            # -------------------------------------------------------------
            if task in ["isolated", "e2e"] and 'quantized' in metrics_payload:
                raw_m = metrics_payload['raw']
                quant_m = metrics_payload['quantized']
                
                f1_scores_raw.append(raw_m.get('Onset_Pitch_F1', 0.0))
                f1_scores_quantized.append(quant_m.get('Onset_Pitch_F1', 0.0))
                precision_quantized.append(quant_m.get('Onset_Pitch_Precision', 0.0))
                recall_quantized.append(quant_m.get('Onset_Pitch_Recall', 0.0))
                chroma_f1_scores.append(quant_m.get('Chroma_F1', 0.0))
                octave_errors.append(quant_m.get('Octave_Error_Rate', 0.0))
            
            if task in ["e2e", "sep"] and 'separation' in metrics_payload and 'SDR' in metrics_payload['separation']:
                sep_m = metrics_payload['separation']
                sdr_scores.append(sep_m['SDR'])
                sir_scores.append(sep_m['SIR'])
                sar_scores.append(sep_m['SAR'])
                
            results.append({"track": track_dir.name, "metrics": metrics_payload})
            
            # 상태 영속성 보장 (실시간 저장)
            with open(out_json, "w", encoding="utf-8") as f:
                json.dump({"details": results}, f, indent=4)
                
        except Exception as e:
            print(f"⚠️ [{track_dir.name}] 평가 중 에러 발생: {e}")
            continue
            
        finally:
            shutil.rmtree(temp_out_dir, ignore_errors=True)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

    if not results:
        print("❌ 유효한 평가 결과가 없습니다.")
        return

    summary = {"total_tracks_evaluated": len(results), "task": task}
    
    if task in ["isolated", "e2e"] and f1_scores_quantized:
        summary.update({
            "quantized_Onset_Pitch_F1_mean": float(np.mean(f1_scores_quantized)),
            "quantized_Onset_Pitch_Precision_mean": float(np.mean(precision_quantized)),
            "quantized_Onset_Pitch_Recall_mean": float(np.mean(recall_quantized)),
            "raw_Onset_Pitch_F1_mean": float(np.mean(f1_scores_raw)),
            "Chroma_F1_mean": float(np.mean(chroma_f1_scores)),
            "Octave_Error_Rate_mean": float(np.mean(octave_errors))
        })
        
    if task in ["e2e", "sep"] and sdr_scores:
        summary.update({
            "SDR_mean": float(np.mean(sdr_scores)),
            "SIR_mean": float(np.mean(sir_scores)),
            "SAR_mean": float(np.mean(sar_scores))
        })
    
    print("\n" + "="*50)
    print(f"🎯 벤치마크 최종 결과 요약 ({task.upper()})")
    print("="*50)
    for k, v in summary.items():
        if isinstance(v, float):
            unit = "dB" if "SDR" in k or "SIR" in k or "SAR" in k else "%"
            val = v if unit == "dB" else v * 100
            print(f"✅ {k:<40}: {val:.2f} {unit}")
        else:
            print(f"✅ {k:<40}: {v}")
    print("="*50)
    
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "details": results}, f, indent=4)

def main():
    parser = argparse.ArgumentParser(description="베이스 파이프라인 모듈별 분할 평가 CLI")
    parser.add_argument("--test_dir", type=str, required=True, help="Slakh 테스트 데이터셋 루트 경로")
    parser.add_argument("--task", type=str, choices=["isolated", "e2e", "sep"], required=True, 
                        help="평가 모드 (isolated: 채보만, e2e: 분리+채보, sep: 분리 모델만)")
    parser.add_argument("--onset_tolerance", type=float, default=0.1, help="Onset 허용 공차 (s)")
    parser.add_argument("--exp_id", type=str, default="Phase8_Baseline", help="실험 식별 ID")
    
    args = parser.parse_args()
    
    asyncio.run(run_batch(
        test_dir=args.test_dir,
        task=args.task,
        onset_tolerance=args.onset_tolerance,
        exp_id=args.exp_id
    ))

if __name__ == "__main__":
    main()
