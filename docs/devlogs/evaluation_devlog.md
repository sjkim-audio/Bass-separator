# [Devlog] 베이스 분리 및 채보 파이프라인 정량 평가 프레임워크 구축기

**문서 경로:** `docs/devlogs/evaluation_devlog.md`  
**작성 목적:** 주관적 청감에 의존하던 알고리즘 튜닝을 탈피하고, 향후 MLOps 전이 학습(Transfer Learning) 및 알고리즘 고도화의 기준점이 될 **음원 분리(Source Separation) 및 타브 채보(Transcription)** E2E 파이프라인 정량적 평가 프레임워크의 설계 철학과 핵심 트러블슈팅 내역을 기록한다.


---

## 1. 평가 프레임워크 설계 철학 및 핵심 지표

본 프레임워크는 오디오 음원 분리(Separation)와 미디 채보(Transcription)라는 두 가지 복합적인 파이프라인의 성능을 각각 격리하여 측정하고, 최종적으로 결합된 상태의 성능을 객관적으로 정량화하기 위해 설계되었다.

### 1.1. 평가 지표 세트 (Evaluation Metrics)

**A. 음원 분리 지표 (Separation Metrics - `museval` 적용)**
*   **SDR (Signal-to-Distortion Ratio):** 분리된 베이스 트랙의 전반적인 품질.
*   **SIR (Signal-to-Interference Ratio):** 드럼이나 기타 등 타 악기의 간섭(Bleeding) 억제력.
*   **SAR (Signal-to-Artifacts Ratio):** Demucs 알고리즘 처리에 의해 발생한 인공적 노이즈 정도.

**B. 채보 지표 (Transcription Metrics - `mir_eval` 적용)**
*   **핵심 KPI:** `Onset_Pitch_F1` (어택 시점과 음정이 동시에 일치하는 비율).
*   **화성 진단 지표 (Diagnostic Metrics):** `Chroma_F1` (옥타브 에러를 배제한 순수 피치 클래스 일치율), `Octave_Error_Rate` (Chroma F1과 Onset_Pitch F1의 차이). 모델이 물리적 옥타브를 틀린 것인지, 아예 엉뚱한 음(화성)을 친 것인지 원인을 독립적으로 추적하기 위해 신설.
*   **시스템 건전성 지표 (Health Metrics):** `Strict_F1` (오프셋 포함 지표). 베이스 기타의 감쇠(Decay) 특성상 오프셋이 모호하여 핵심 KPI로는 부적합하나, 파서(Parser)의 디바운싱 및 무음 카운터가 지속 시간(Duration)을 비정상적으로 자르지 않는지 감시하는 용도로 보존.
*   **베이스 특화 오차 허용 (Tolerance):** `100ms (onset_tolerance=0.1)`. 베이스 기타 특유의 느린 어택(Slow Transient)과 저역대 파장 특성을 반영하여 학계 표준(50ms)보다 완화된 기준을 적용.

### 1.2. 평가 모드 및 A/B 테스팅 전략

*   **Isolated vs. E2E 평가:**
    *   `Isolated Mode`: 정답 베이스 오디오(`bass_gt.wav`)를 직접 입력하여 순수 DSP/채보 알고리즘의 성능만 격리 측정.
    *   `E2E Mode`: 믹스 오디오(`mix.wav`)를 입력하여 Demucs의 분리 손실이 최종 채보 F1-Score에 미치는 영향을 종합 측정.
*   **Raw vs. Quantized 교차 검증:** 평가 루프 내에서 양자화기 통과 전(물리적 시간 보존)과 후(16분음표 격자 강제 스냅)의 F1-Score를 동시 산출하여, Grid Snap 알고리즘이 실제 연주의 Micro-timing을 훼손하는지 혹은 리듬을 교정하는지 그 효용성을 증명.

---

## 2. 데이터Ops 및 평가 노트북 워크플로우 (Colab 환경)

### Phase 0: 데이터 전처리 (`01_data_prep/01_prepare_slakh2100.ipynb`)
*   **데이터셋:** Slakh2100-redux (MIDI 중복 누수 방지를 위한 클린 버전).
*   **음향 무결성 보존:** 단순 오디오 합산 시 발생하는 클리핑을 방지하기 위해 공식 `metadata.yaml`의 `overall_gain`을 수학적으로 적용한 `bassless_mr.wav` 생성.
*   **I/O 최적화:** 무거운 `librosa` 리샘플링을 배제하고 `soundfile` 기반의 온더플라이(On-the-fly) FLAC to WAV 디코딩을 채택하여 수천 곡의 전처리 시간을 획기적으로 단축.

### Phase 0.5: 데이터 추출 파이프라인 고도화 및 모수 확정
*   **OS 독립성 확보:** `prepare_slakh_local.py` 스크립트에서 로컬 `ffmpeg.exe` 하드코딩을 제거하고 `shutil.which`를 도입하여 OS 독립성을 확보함. 정규표현식(`re`)을 통해 경로 파편화를 방어함.
*   **I/O 병목 우회:** Windows 환경 특유의 파일 접근 권한 충돌(Defender 락킹 등)로 인한 샌드박스 삭제 실패를 방어하기 위해, `os.chmod`를 활용한 강제 쓰기 모드 전환 및 재시도(Retry) 로직(`robust_rmtree`)을 구축함.
*   **최종 벤치마크 모수 동결 (130 트랙):** 총 151개의 원본 테스트 셋 중, 다중 베이스(Multi-bass), 렌더링 실패, 베이스 부재 트랙을 자동 필터링하여 **가장 완벽한 1:1 평가가 가능한 130곡의 클린 데이터셋(Clean Dataset)을 최종 확정**함. 향후 모든 모델 평가는 이 130곡을 분모로 산출됨.

### Phase 1: 기준점 측정 (`04_evaluation/01_baseline_performance_test.ipynb`)
*   **역할:** `slakh_eval` 데이터셋 대상 비동기(`nest_asyncio`) 배치 평가 수행 및 CSV 결과 도출.

### Phase 2: 자동 최적화 (`04_evaluation/02_Hyperparameter_Optimization.ipynb`)
*   **역할:** `Optuna`를 활용해 검증 셋(Validation) 기준 최고 F1-Score를 내는 파라미터(Onset Tolerance, Viterbi Penalty 등)의 자동 탐색.
*   **통제 변인:** 과적합(Overfitting) 방지를 위해 소수 곡 튜닝을 금지하고, 최소 50곡 이상의 무작위 검증 셋을 강제 할당.

### Phase 3: 정성 분석 (`04_evaluation/03_Error_Analysis_and_Visualization.ipynb`)
*   **역할:** 수치 뒤에 가려진 에러의 원인 시각화. GT(Ground Truth)와 예측 악보를 피아노 롤 평면 위에 중첩(Overlap)하여 옥타브 에러, 가짜 노트(Ghost Note) 발생 구간을 추적.

### Phase 4: CLI 벤치마크 평가 가동 (`run_batch_eval.py`)
*   **역할:** 노트북(Notebook) 환경의 프로토타이핑을 넘어, 터미널 환경에서 대규모 배치 평가를 가동하는 프로덕션 레벨 스크립트. OOM 방어 및 위상 지연(Latency Shift) 자동 보정 로직이 탑재되어 있음.
*   **실행 규격:**
    ```bash
    python -m src.evaluation.run_batch_eval \
        --test_dir ./slakh_processed/test \
        --isolated False \
        --onset_tolerance 0.1 \
        --exp_id Phase8_Baseline
    ```

---

## 3. 핵심 트러블슈팅 및 아키텍처 결정 사항 (ADR 요약)

평가 프레임워크 구축 과정에서 발생한 주요 문제점과 수학적/엔지니어링적 해결 방안의 요약입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **GT Polyphony Penalty** | 정답 악보의 화음/더블스탑이 단선율 모델(CREPE) 평가 시 억울한 미검출(FN) 감점 유발. | 겹치는 서스테인을 보존하며 분할 절단하는 **최종 입력음 우선(Last-Note Priority)** 평탄화 로직 구축. |
| **Demucs Latency Shift** | 분리 모델 CNN 패딩 연산으로 인한 수십 ms의 고정 위상 지연이 E2E Onset 점수를 깎아내림. | 평가 진입 전 상호상관도(Cross-correlation) 연산으로 정답과 추정 오디오의 **위상 지연 수학적 동기화**. |
| **False Baseline** | 양자화 후 데이터를 Raw 평가에 재사용하여 순수 피치 트래커 성능이 왜곡됨. | 코어 파이프라인의 반환 시그니처를 확장하여 Raw 데이터(`fingered_events`)를 분리 주입. |
| **Duration Bug Masking** | 0초 이하의 지속시간 발생 시 예외 처리로 50ms를 덮어씌워 파이프라인의 꼬리 절단 버그가 은폐됨. | 엣지 케이스 발생 시 강제 보정하되 `logging.warning`을 명시하여 개발자 관측성(Observability) 확보. |
| **OOM & System Crash** | 151곡 배치 평가 시 누적되는 VRAM 파편화 및 동기적 호출에 의한 이벤트 루프 마비. | 샌드박스 초기화, 강제 GC 호출 및 `loop.run_in_executor` 스레드풀 위임을 통한 인프라 안정화. |
| **Data Evaporation** | 장시간 평가 중 크래시 발생 시 메모리에 적재된 벤치마크 데이터가 모두 증발함. | 트랙 완료 시마다 JSON에 덮어쓰는 **상태 영속성 보장 (Incremental Save)** 로직 도입. |
| **Cross-Contamination** | 단일 트랙 분리 실패 시 이전 곡의 임시 베이스 오디오가 섞여 들어가는 교차 오염 발생. | 트랙 단위 평가 종료 시 `outputs/eval_temp` 디렉토리를 물리적으로 통삭제하는 샌드박싱 확립. |
| **Octave Double Penalty** | 모델의 옥타브 에러가 50센트 공차에 의해 FN + FP로 이중 감점되어 화성 추적력이 과소평가됨. | 부동소수점 다이렉트 모듈로 연산(`% 12`)을 통해 순수 피치 일치율을 뽑아내는 **Chroma F1 지표 신설**. |
| **Empty Array Crash** | 무음(Empty GT/Prediction) 트랙 진입 시 `mir_eval` 크래시 및 다운스트림 `KeyError` 발생. | `empty_schema`를 강제 반환하여 배치 파이프라인의 **평가 스키마 무결성(Schema Integrity)** 보장. |
| **1D Array Slicing Crash** | 모노(1D) 오디오 배열에 스테레오(2D) 전용 슬라이싱(`[:, lag:]`)을 시도하여 차원 충돌 및 파이프라인 붕괴 발생. | `np.atleast_1d().squeeze()`를 통해 입력 배열을 1D 규격으로 강제 평탄화(Flattening)하고 슬라이싱 로직 교체. |
| **Separation API Deprecation** | `museval` 패키지 업데이트로 인한 `eval_bss_v4` API 소실로 음원 분리(SDR) 채점 불가. | `mir_eval.separation`으로 평가 엔진을 마이그레이션하고, 2D 텐서 주입 및 `NaN` 예외 반환 방어 로직 구축. |

<details>
<summary><b>각 항목별 상세 원인 및 설계 논리</b></summary>

### 3.1. GT MIDI 강제 단선율화 (Monophonic Flattening) 
*   **이슈:** Slakh2100의 GT 악보는 다성부(Polyphony, 더블 스탑 및 레가토)를 포함하나, 파이프라인의 CREPE 모델은 단선율 전용 아키텍처임.
*   **결과:** 모델이 주선율을 완벽히 추적해도 겹친 노트로 인해 부당한 '미검출(False Negative)' 페널티가 발생.
*   **해결:** `evaluation.py`의 `load_midi_to_mir_eval`에 **최종 입력음 우선(Last-Note Priority)** 로직 적용. 겹치는 노트 발생 시 선행 노트를 강제 절단하거나 하위 피치를 삭제하여 GT를 단선율로 평탄화. 알고리즘의 순수 피치 추적 능력을 왜곡 없이 측정 가능해짐.

### 3.2. E2E 평가 시 위상 지연(Latency Shift) 보정 
*   **이슈:** Demucs 모델의 STFT/Conv 연산 구조 패딩으로 인해 출력된 `bass_est.wav`에 원본 대비 수십 ms의 위상 지연 발생.
*   **결과:** 100ms의 타이트한 오차 범위 내에서 시스템 딜레이가 채보 점수를 억울하게 깎아내림.
*   **해결:** 상호상관도(Cross-correlation) 기반의 `align_audio` 함수를 분리 모델 평가(`run_separation_evaluation`)에 삽입하여 시간차를 수학적으로 보정.

### 3.3. Raw vs Quantized 평가 데이터 오염(Data Contamination) 교정
*   **이슈:** 초기 평가 로직에서 양자화기(`RhythmicQuantizer`)를 통과한 데이터를 `test_quantized=False` 옵션만 주어 Raw 평가에 재사용함. 양자화기 내부의 '노트 병합(Merging)' 로직이 이미 적용된 상태로 평가되어, 순수 피치 트래커의 성능이 과대/과소평가되는 가짜 베이스라인(False Baseline) 현상 발견.
*   **해결:** 코어 파이프라인(`src/core/pipeline.py`)의 반환 시그니처를 수정하여 양자화 전 단계의 데이터(`fingered_events`)를 외부로 노출시키고, 평가 모듈이 이를 분리 주입하도록 E2E 데이터 흐름을 교정함.

### 3.4. 파이프라인 결함 은폐(Masking) 방지 로직 구축
*   **이슈:** `TranscriptionEvaluator` 내부에서 노트를 파싱할 때 지속 시간(Duration)이 0 이하일 경우 예외 처리로 50ms를 할당하는 로직이 존재함. 이로 인해 상위 모듈(Parser, Quantizer)에서 꼬리 절단(Truncation) 오류가 발생해도 콘솔에 에러가 노출되지 않고 정상 수치로 채점되는 관측성 결여 문제 발견.
*   **해결:** `duration <= 0` 인 엣지 케이스 발생 시 `logging.warning`을 강제로 출력하도록 수정하여, 잠재적인 파이프라인 버그(시간 역전 등)를 개발자가 즉시 인지하고 추적할 수 있는 안전장치 확립.

### 3.5. 정답 MIDI 평탄화 시 서스테인(Sustain) 증발 버그 교정
*   **이슈:** `load_midi_to_mir_eval` 함수에서 다성부 MIDI를 단선율로 평탄화할 때, 새로운 노트가 기존 노트와 겹치면 이전 노트의 끝부분을 무조건 절단 및 삭제함. 이로 인해 짧은 장식음이 긴 서스테인 중간에 끼어들 경우 남은 롱톤이 영구적으로 소실되어 정답 데이터(GT)의 리듬 무결성이 훼손됨.
*   **해결:** 1차원 시간축 기반의 구간 마스킹(Interval Masking) 기법을 도입. 새 노트가 삽입될 때 기존 노트와 겹치는 구간만 정밀하게 도려내어 앞뒤로 분할(Split)함으로써, 연주자의 원래 서스테인 뉘앙스를 온전히 보존하는 강건한(Robust) 평탄화 로직 구축.

### 3.6. E2E 평가 시 Demucs 위상 지연(Latency) 보정 로직 도입
*   **이슈:** E2E 채보 평가(`trans` 모드)에서 믹스 음원을 Demucs로 분리할 경우, CNN 모델 내부의 연산 패딩으로 인해 수십 ms의 위상 지연(Phase Shift)이 발생함. 이 지연이 보정되지 않은 채 파이프라인에 입력되어, 피치 트래커가 음표를 정확히 추출했음에도 불구하고 정답(GT) 대비 Onset 타임스탬프가 고정적으로 밀려 Onset F1-Score가 부당하게 하락하는 치명적 오차 원인 발견.
*   **해결:** CLI 스크립트(`run_eval.py`)에 E2E 평가 전용 정답 오디오 참조 인자(`--ref_audio`)를 확장함. 평가 프레임워크(`run_transcription_evaluation`) 내부에서 채보 알고리즘 시작 직전에, 분리된 베이스 오디오와 정답 오디오 간의 상호상관도(Cross-correlation)를 계산해 위상 지연을 동기화(Alignment)하는 전처리 단계를 삽입하여 E2E 평가의 공정성을 확보함.

### 3.7. 대규모 배치 평가(151 트랙) 안정성 및 데이터 무결성 강화
*   **이슈 1 (시스템 크래시 및 VRAM 파편화):** 
    *   `evaluator.py` 내 방어 로직 중 `NameError(logging)`에 의한 돌발 종료 위험.
    *   비동기 함수 내부에 극단적 CPU-bound 파이프라인이 동기적으로 호출되어 Async Event Loop가 완전히 마비되는 병목 발생.
    *   반복적인 배치 루프 특성상 파이썬 가비지 컬렉션 지연으로 인해 VRAM 파편화가 누적되어 30~40트랙 부근에서 필연적인 OOM(Out of Memory) 크래시 발생.
*   **이슈 2 (데이터 교차 오염 및 증발 위험):**
    *   `mix.wav` E2E 평가 시 임시 폴더(`outputs/eval_temp`)를 덮어쓰는 구조로 인해, 특정 트랙에서 Demucs가 조용히 실패(Silent Failure)할 경우 이전 트랙에서 분리해 둔 베이스 오디오를 현재 트랙의 결과물로 오인하는 치명적인 교차 오염(Cross-contamination) 발생.
    *   151곡 평가가 모두 끝난 종료 시점에 단 한 번 `json.dump`를 수행하도록 설계되어, 런타임 중간에 크래시 발생 시 4~5시간 분량의 벤치마크 데이터가 허공으로 증발할 위험성 존재.
*   **해결 및 아키텍처 교정:**
    *   **Event Loop 마비 및 OOM 방어:** `evaluator.py` 내 동기 파이프라인 호출을 `loop.run_in_executor`를 통해 외부 스레드풀로 오프로딩함. 또한 `run_batch_eval.py`의 단위 루프 `finally` 블록에 `torch.cuda.ipc_collect()`와 `gc.collect()`를 강제 삽입하여 트랙 1개 처리 완료마다 CPU/GPU 메모리 누수를 원천 차단함.
    *   **상태 영속성 보장 (Incremental Save):** 루프 내에서 트랙 하나가 종료될 때마다 즉시 중간 결과를 JSON에 덮어쓰는 누적 저장 로직을 도입하여 데이터 증발을 방어함.
    *   **디스크 I/O 샌드박싱:** `finally` 블록에 `shutil.rmtree("outputs/eval_temp", ignore_errors=True)`를 추가하여 평가가 끝난 임시 디렉토리를 물리적으로 통삭제함으로써 이전 트랙의 잔여 파일 개입을 차단함.

### 3.8. Slakh2100 데이터셋 무결성 검증 및 전처리 필터링
*   **렌더링 누락 방어:** `inst_class: Bass`로 할당되어 있더라도 실제 오디오 엔진에서 렌더링에 실패한 스템(`audio_rendered: false`)을 참조하여 FFmpeg 변환이 크래시되는 현상을 원천 차단함.
*   **다중 베이스(Multi-Bass) 트랙 배제:** 앙상블 구성 상 베이스가 2대 이상 포함된 트랙의 경우, 믹스 오디오에는 모든 베이스가 합쳐져 있으나 단일 GT 파일로는 이를 포괄할 수 없어 필연적으로 False Positive 페널티가 발생함. 객관적인 1:1 F1-Score 측정을 위해 `len(bass_stems) > 1`인 트랙은 벤치마크 모수에서 명시적으로 제외(Skip)함.

### 3.9. 옥타브 에러 이중 감점(Double Penalization) 모순 해결 및 Chroma 지표 도입
*   **이슈:** 베이스 연주의 고질적인 옥타브 점프 에러(예: 슬랩 배음 오인) 발생 시, `mir_eval`의 기본 50센트 공차는 이를 "정답 노트를 놓침(False Negative) + 엉뚱한 노트를 침(False Positive)"으로 간주하여 F1-Score를 두 배로 깎아버림. 이로 인해 모델의 순수한 화성(Harmonic) 추적 능력이 심각하게 과소평가되는 분석의 맹점이 발견됨.
*   **해결:** 이분 매칭 알고리즘을 훼손하지 않으면서 옥타브 에러를 걷어내기 위해, 평가 진입 전 부동소수점 다이렉트 모듈로 연산(`(pitch % 12) + 48`)을 적용함. 정수 반올림(`np.round()`)을 배제하여 오디오 원본의 미세 피치 편차(Micro-tuning)는 100% 보존하되, 모든 음정을 단일 옥타브 대역으로 압축하는 전처리 로직을 구축함. 이를 통해 산출된 `Chroma_F1`과 `Octave_Error_Rate`를 통해, 채보 실패의 원인이 '배음 노이즈'인지 '트래커의 근본적 한계'인지 숫자로 증명할 수 있게 됨.

### 3.10. 평가 스키마 무결성(Schema Integrity) 강제화
*   **이슈:** 곡의 특정 구간에 정답 악보가 아예 비어있거나(Empty GT), 모델이 베이스 음표를 단 하나도 추출하지 못했을 경우(Empty Prediction) `mir_eval`의 연산이 붕괴함. 이 과정에서 누락된 반환 키워드로 인해 대규모 배치 평가 하위 파이프라인(`save_experiment_results`)에서 `KeyError`가 발생하며 전체 프로세스가 다운될 위험이 존재함.
*   **해결:** 모든 평가 반환값을 포괄하는 통합된 빈 스키마(`empty_schema`) 템플릿을 정의함. 엣지 케이스 진입 시, 해당 곡이 "정답도 없고 추출도 안 한 완벽한 무음"이라면 1.0(만점)을, "정답은 있는데 추출을 못한 경우"라면 0.0을 채운 스키마를 강제로 반환하도록 설계하여 다운스트림 로직의 안전성을 원천 보장함.

### 3.11. Audio Alignment 차원 충돌 해결 (DSP 데이터 규격 표준화)
*   **이슈:** E2E 배치 평가 중 Demucs 지연시간 보정 로직(`align_audio`)에서 `IndexError: too many indices for array`가 발생하며 전체 파이프라인이 중단됨.
*   **원인:** 연산량 최적화 및 평가 통일성을 위해 오디오 로드 단계를 Mono(1D 배열)로 통일했으나, 과거 작성된 위상 정렬 로직은 Stereo(2D 배열 `[channels, samples]`) 구조의 슬라이싱 문법(`est[:, lag:]`)을 그대로 유지하고 있어 차원(Dimension) 불일치가 발생함.
*   **해결:** `np.atleast_1d().squeeze()`를 적용해 배열의 차원을 완벽한 1D 규격으로 평탄화(Flattening)하고, 1D 전용 인덱싱으로 위상 정렬 슬라이싱 로직을 전면 재작성함. 향후 파이프라인의 모든 DSP 연산은 1D Mono 배열을 기준으로 수행함을 아키텍처 원칙으로 확립함.

### 3.12. 분리 성능 채점 라이브러리 마이그레이션 (`museval` ➔ `mir_eval`)
*   **이슈:** 음원 분리 채점 모듈 진입 시 `module 'museval' has no attribute 'eval_bss_v4'` 에러가 발생하여 SDR, SIR, SAR 수치 산출이 전면 중단됨.
*   **원인:** 기존 의존성이던 `museval` 라이브러리의 버전 업데이트 및 API Deprecation으로 인해 내부 함수 호출 시스템이 붕괴됨.
*   **해결:** BSS(Blind Source Separation) 지표 평가 엔진을, 동일한 수학적 결과를 보장하며 생태계 표준에 가까운 `mir_eval.separation.bss_eval_sources` API로 전면 교체함.
    *   **차원 브릿지(Dimension Bridge) 주입:** `mir_eval` 엔진이 요구하는 `[sources, samples]` 2D 텐서 규격을 맞추기 위해, 내부적으로 1D Mono 오디오에 `np.newaxis`를 활용하여 차원을 강제 주입하는 인터페이스 로직을 추가함.
    *   **방어적 프로그래밍 (Defensive Fallback):** 특정 트랙이 완벽한 무음(Silence)으로 분리되는 등 엣지 케이스에서 수학적 예외(Zero division 등)가 발생하더라도 평가 루프 전체가 죽지 않도록 `Try-Except` 블록을 구성하고, 실패 시 `NaN` 통계치를 반환하여 데이터 프레임 붕괴를 방어함.

---
</details>

## 4. 시스템 한계점 및 향후 과제 (Limitations & Future Work)

1.  **폴리포니(Polyphony) 정보의 영구적 소실:** 단선율 평탄화 적용으로 알고리즘 측정의 왜곡은 막았으나, 연주자의 의도적인 화음 연주 및 서스테인 뉘앙스는 평가 단계에서 측정할 수 없다. 이는 향후 다성부 피치 트래커(Polyphonic Pitch Tracker) 도입 전까지 유지되는 아키텍처 한계다.
2.  **합성 데이터의 강건성(Robustness) 검증 불가:** 정량 평가는 가상 악기(VSTi)로 렌더링된 Slakh 데이터에 한정된다. 실제 베이스 연주 특유의 물리적 노이즈(프렛 버즈, 슬랩 어택, 앰프 노이즈) 대응력은 확인할 수 없다.
3.  **Next Step:** 본 프레임워크에서 도출된 E2E F1-Score를 '베이스라인'으로 동결한다. 향후 실제 DI 소스와 노이즈를 결합한 데이터 증강(Data Augmentation) 기법으로 Demucs 파인튜닝을 수행하고, F1-Score의 상승폭을 증명해야 한다.
