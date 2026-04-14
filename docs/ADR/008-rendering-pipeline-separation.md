# [ADR-008] 단선율 타브 악보(Quantized)와 물리적 MIDI(Unquantized)의 렌더링 분리

* **Status:** Accepted
* **Date:** 2026-03-01 (Retroactively Documented for Phase 5)
* **Related Documents:** [Transcription_devlog.md](../devlogs/Transcription_devlog.md)

## 1. Context (배경)

Phase 4에서 리듬 양자화기(Rhythmic Quantizer)가 도입됨에 따라, 추출된 모든 노트는 16분음표 격자(`grid_index`)에 맞게 시작점(Onset)과 종료점(Offset)이 스냅(Snap)되었다. 또한 가독성을 위해 겹치는 노트들을 잘라내어 완벽한 단선율(Monophonic) 악보 데이터를 구축했다.

하지만 이 단일 양자화 파이프라인을 시각적 악보(ASCII Tab)와 청각적 재생(MIDI Export) 양쪽에 동일하게 적용하자 다음과 같은 문제가 발생했다.
1. **기계적인 MIDI 렌더링:** 16분음표 격자에 강제로 맞춰진 MIDI 파일은 연주자 특유의 미세한 레이드백(Laid-back) 그루브나 셔플(Shuffle) 리듬의 느낌을 완전히 상실하여, 이른바 '컴퓨터가 친 듯한' 딱딱한 소리를 냈다.
2. **서스테인(Sustain) 왜곡:** 양자화기가 오버랩 충돌을 피하기 위해 음의 길이를 임의로 연장하거나 자르는 과정에서, 실제 베이시스트가 의도적으로 현을 뮤트(Mute)하여 만들어낸 짧고 타격감 있는 쉼표(Rest) 느낌이 MIDI 재생 시 왜곡되었다.

## 2. Decision (결정)

도메인 모델 계층(Core Pipeline)은 양자화 전후의 모든 데이터를 불변 객체(`NoteEvent`)에 보존하여 넘기며, **최종 출력 및 렌더링 계층(Presentation Layer)을 시각용과 청각용 두 갈래로 완전히 분리**한다.

1. **시각적 렌더링 (`TabRenderer`):**
   * 타브 악보 렌더링 시에는 양자화된 격자 데이터(`grid_index`, `quantized_duration`)만을 철저히 따른다.
   * 이를 통해 텍스트나 UI 상에서 노트가 겹치거나 마디(Measure) 구분이 무너지는 가독성 파괴를 원천 차단한다.
2. **청각/데이터 렌더링 (`MidiRenderer`):**
   * MIDI 파일(또는 DAW 연동 데이터) 추출 시에는 기계적인 스냅(Snap)을 의도적으로 배제한다.
   * `PitchParser`가 디바운싱(Debouncing) 프레임으로부터 역산한 원본 물리적 발생 시간(`time`)과 지속 시간(`duration`)을 최우선으로 신뢰하여 실제 연주의 그루브와 `note_off` 타이밍을 그대로 보존한다.
3. **Velocity 맵핑:**
   * MIDI 렌더링 시, AI 모델(CREPE)이 산출한 피치 예측 신뢰도(`confidence`)를 타건 강도(`velocity`, 64~127 범위)로 스케일링하여 매핑한다.

## 3. Considered Options (검토된 대안들)

1. **단일 양자화 파이프라인 유지:** 타브 악보와 MIDI 모두 16분음표로 스냅된 데이터를 사용하는 방식. 구현과 유지보수는 가장 쉬우나, 추출된 MIDI의 음악적 가치가 크게 훼손되어 기각했다.
2. **Micro-Timing 양자화 도입:** 16분음표 대신 64분음표나 밀리초 단위의 미세 격자(Micro-grid)를 사용하여 그루브를 살리면서도 악보화하는 방식. 시각적 타브 악보의 길이를 무한정 팽창시켜 화면 가독성을 심각하게 해치므로 기각했다.
3. **도메인 내 렌더링 분리 (Dual Rendering Pipeline):** 데이터를 원본과 양자화 버전 양쪽으로 보존한 뒤, 렌더러가 자신의 목적(시각 vs 청각)에 맞는 속성을 선택하여 사용하는 방식. (최종 채택안)

## 4. Rationale (의사결정 근거)

### 4.1. 음악적 뉘앙스(Micro-timing) 보존
베이스 연주에서 그루브(Groove)는 완벽한 정박(Grid)이 아니라 수십 밀리초(ms) 앞뒤로 밀고 당기는 미세한 타이밍(Micro-timing)에서 나온다. 악보는 연주를 위한 '추상화된 기호'일 뿐이므로 강제 양자화가 필수적이지만, MIDI 파일은 실제 음향 합성을 위한 '제어 데이터'이므로 물리적 원본 시간을 보존하는 것이 카피 및 편곡 작업(DAW 연동)에 훨씬 높은 가치를 제공한다.

### 4.2. Confidence 기반 Velocity 스케일링의 실용성
피치 추적 모델의 `confidence` 데이터를 MIDI의 `velocity`로 맵핑하는 것은 매우 실용적인 UX 설계이다. DAW 환경에서 사용자는 이 Velocity 데이터를 기준으로 불확실하게 인식된 노이즈 노트나 고스트 노트를 시각적으로 쉽게 식별하고 일괄 필터링(Midi Logic)할 수 있는 확장성을 확보하게 된다.

## 5. Consequences (결과)

* **Positive:**
  * 하나의 파이프라인 연산으로 '가독성 높은 악보'와 '원곡의 그루브가 살아있는 MIDI 데이터'라는 상충하는 두 가지 목표를 동시에 달성했다.
  * 프론트엔드 UI(Streamlit)에서 불확실한 노트의 투명도를 낮추거나 색상을 다르게 표기할 수 있는 데이터 기반이 마련되었다.
* **Negative & Limitations:**
  * 시각적 타브 악보(Quantized)를 보면서 원본 물리적 시간이 보존된 MIDI(Unquantized)를 동시에 재생할 경우, 눈에 보이는 박자와 귀로 들리는 박자 사이에 미세한 불일치(Desync)가 느껴질 수 있다.
  * **Mitigation:** 이는 모든 채보/사보 프로그램이 겪는 본질적인 현상이며, 사용자가 악보 편집기에서 직접 '재생용 스윙/셔플 적용' 옵션을 제어할 수 있도록 후속 기능(Phase 9)으로 제공하는 것이 바람직하다.
