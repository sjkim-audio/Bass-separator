# [Devlog] 베이스 분리 및 채보 파이프라인 정량 평가 프레임워크 구축

---

<details open>
<summary><b>📅 [2026-07-21] Phase 8: 1차 E2E 파이프라인 벤치마크 결과 및 병목 분석 (Baseline)</b></summary>

<br>

**테스트 환경:** 130곡 다성부 믹스 오디오 (Slakh2100) / End-to-End 파이프라인 (Demucs + CREPE + Viterbi)

### 1. 정량 평가 지표 요약

| 평가 지표 (Metrics) | 수치 (Mean) | 상태 | 해석 요약 |
| :--- | :--- | :--- | :--- |
| **Onset-Pitch F1** | 1.19 % | 🚨 **CRITICAL** | 최종 악보 정확도 완전 붕괴. 예측 악보와 정답이 사실상 불일치함. |
| **Chroma F1** | 62.10 % | ℹ️ **INFO** | 화성(음고 클래스)과 멜로디의 흐름은 약 62% 확률로 정확히 추적 중임. |
| **Octave Error Rate** | 60.91 % | 🎯 **ISSUE** | `Chroma F1`과 `Onset-Pitch F1`의 극단적 괴리. 심각한 옥타브 시프트 발생. |
| **SDR (Separation)** | 5.23 dB | ✅ **PASS** | 믹스 환경에서 베이스 트랙 분리는 유의미한 수준으로 수행됨. |
| **SIR (Separation)** | inf dB | ℹ️ **INFO** | 단일 타겟(Single-source) 평가 구조상 타 악기 레퍼런스가 주입되지 않아 발생하는 수학적으로 정상적인 무한대 산출. |

<br>

<details>
<summary><b>🔍 핵심 분석 및 예상 원인 (Analysis & Hypotheses)</b></summary>

*   **옥타브 시프트(Octave Shift) 병목 확정:** 
    최종 성능(`1.19%`)이 무너진 핵심 원인은 음원 분리(Demucs)의 노이즈가 아닌, 채보 알고리즘 자체의 주파수 매핑 단계에 있음. 모델이 베이스 라인의 존재와 화성은 파악했으나, 물리적 주파수를 1옥타브 이상 잘못 해석하고 있음.
*   **가설 1 (Parser 로직 결함):** `hz_to_midi` 변환식 내부의 주파수 스케일링(2배수 산술 등) 누락 혹은 베이스 지판(Fret) 매핑 오프셋의 수학적 오류.
*   **가설 2 (음향학적 착시):** 단선율 피치 트래커(CREPE)가 베이스 기타 특유의 강력한 배음(Harmonics) 에너지를 기음(Fundamental)으로 오판하는 현상.
*   **상관관계 증명:** 분리 품질(SDR)이 15dB에 달하는 깨끗한 샘플에서도 F1 점수가 0에 수렴함. 파이프라인의 개선 우선순위가 '음원 분리 고도화'가 아닌 '채보 파서(Parser) 디버깅'에 있음을 시각적/통계적으로 입증함.
</details>

<details>
<summary><b>⚠️ 한계점 및 논리적 맹점 (Limitations & Flaws)</b></summary>

*   **성능의 절대적 상한선(Ceiling):** 옥타브 시프트 버그를 파서 레벨에서 100% 수학적으로 교정하더라도, 현재 아키텍처가 도달할 수 있는 E2E F1 Score의 최대 이론치는 `Chroma F1`인 **62.10%**를 돌파할 수 없음. 
*   나머지 38%의 손실은 박자(Onset) 이탈, 비화성음 매핑 실패, 혹은 순수 타겟음 미검출(False Negative)로 인한 것으로 신경망(CREPE) 본연의 성능 한계 및 분리 모델의 미세한 트랜지언트(Transient) 훼손이 복합적으로 작용한 결과임.
</details>

<details>
<summary><b>🛠️ 향후 과제 (Next Steps)</b></summary>

1.  **피치 파서(Parser) 로직 정밀 디버깅:** `src/transcription/parser.py` (또는 해당 모듈) 내부 주파수-MIDI 변환식 및 프렛 후보군 도출 알고리즘 최우선 검수.
2.  **Isolated Mode 교차 검증 (A/B Test):** Demucs를 배제하고 정답 오디오(`bass_gt.wav`)를 투입하는 단독 채보 벤치마크 가동. 옥타브 에러가 분리 모델의 위상 왜곡과 무관한 '채보 알고리즘 고유의 결함'임을 통계적으로 최종 격리 및 확정.
</details>

</details>
