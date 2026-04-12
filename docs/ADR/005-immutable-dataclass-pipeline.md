# [ADR-005] 불변 데이터 클래스(Immutable Dataclass) 기반 파이프라인 아키텍처 재설계

* **Status:** Accepted
* **Date:** 2026-03-01 (Retroactively Documented for Phase 4)
* **Related Documents:** [Transcription_devlog.md](../devlogs/Transcription_devlog.md)

## 1. Context (배경)

초기 전사(Transcription) 파이프라인은 단일 `BassTabGenerator` 클래스가 피치 파싱, 운지법 매핑, 양자화 등 모든 로직을 중앙 통제하는 거대한 객체(God Object) 형태였다. 또한, 각 처리 단계를 거칠 때마다 파이썬의 기본 가변 객체인 딕셔너리(`dict`) 리스트를 주고받으며 내부 값을 직접 수정(In-place Mutation)하는 방식을 취했다.

이러한 상태 관리(State Management) 구조는 파이프라인이 고도화됨에 따라 다음과 같은 치명적인 결함을 유발했다.
1. **데이터 소실 (Data Loss):** 양자화 단계에서 16분음표 격자 인덱스(`grid_index`)를 딕셔너리의 키(Key)로 사용함에 따라, 슬라이드/해머링으로 인해 동일 시간 격자 내에 다중 노트가 겹칠 경우 선행 노트가 강제로 덮어씌워져(Overwrite) 증발하는 현상 발생.
2. **참조 오염 (Call-by-Assignment Side Effects):** Phase 6 기호 영역 보정(`_post_process_garbage_pitch`) 단계에서 후처리 모듈이 수정한 임시 값이 파이썬의 참조 할당 특성으로 인해 원본 이벤트 리스트까지 오염시켜 디버깅을 불가능하게 만듦.
3. **강한 결합 (Tight Coupling):** 데이터 스키마가 없는 `dict` 구조로 인해 IDE의 정적 분석 및 Pydantic 연동(FastAPI 응답 계층)이 불가하고, 모듈 간 결합도가 높아 독립적인 단위 테스트(Unit Test)가 불가능해짐.

## 2. Decision (결정)

가변 상태로 인한 부작용을 원천 차단하기 위해, 파이프라인 전체를 관통하는 **불변 데이터 객체(Immutable Data Object) 및 단방향 함수형 파이프라인(Functional Pipeline)** 구조를 전면 도입한다.

1. **`frozen=True` Dataclass 도입:** 단일 진실 공급원(SSOT)으로서 `src/models/events.py`에 `NoteEvent` 데이터 클래스를 정의하고 상태 변경을 락(Lock) 처리한다.
2. **`update()` 메서드 패턴 (Immutable Replacement):** 값이 할당되어야 할 경우(예: Viterbi의 `fret` 할당, Quantizer의 `grid_index` 할당), 기존 객체를 훼손하지 않고 파이썬의 `dataclasses.replace`를 활용하여 **변경된 값을 가진 새로운 복제 객체를 반환**하도록 강제한다.
3. **List 누적 및 얕은 복사(Shallow Copy):** `dict` 키 기반의 덮어쓰기 로직을 전면 폐기하고, 모든 이벤트를 `List[NoteEvent]` 형태로 누적 순회(Iterate)한다. 모듈 내부에서 리스트 변형이 필요할 때는 `events.copy()`로 얕은 복사를 수행한 뒤, 인덱스에 `update()`된 새 객체를 끼워 넣어 원본 데이터의 무결성을 보존한다.

## 3. Considered Options (검토된 대안들)

1. **딕셔너리 깊은 복사 (`copy.deepcopy`) 유지:** 모듈 간 데이터를 넘길 때나 값을 수정할 때 `deepcopy`를 사용하여 원본 훼손을 막는 방식. (기각)
2. **전역 상태 관리자 (Global State Manager):** 파이프라인 상태를 중앙에서 관리하는 거대한 싱글톤 클래스를 생성하여 상태를 추적하는 방식. (기각)
3. **불변 데이터 클래스 (Immutable Dataclass) 도입:** 상태 변이를 문법적으로 차단하고 매번 새로운 객체를 반환하는 함수형 아키텍처. (최종 채택안)

## 4. Rationale (의사결정 근거)

### 4.1. 타입 안정성(Type Safety)과 API 스키마 동기화
`copy.deepcopy`를 사용하더라도 `dict` 구조를 유지하면 타입 힌팅(Type Hinting) 부재 문제가 해결되지 않는다. `NoteEvent` 불변 객체의 명확한 타입 힌팅은 파이프라인의 최종 산출물을 FastAPI의 `TranscriptionResponse` DTO(Pydantic) 직렬화 계층과 매끄럽게 연동시키는 핵심 브릿지 역할을 한다.

### 4.2. 모듈 간 책임 분리(SoC)와 테스트 용이성
전역 상태 관리자를 도입하는 것은 객체 지향의 안티 패턴(God Object)을 심화시킬 뿐이다. 불변 객체를 활용한 단방향 체이닝(`Tracker -> Parser -> Fingering -> Quantizer`)은 각 모듈을 독립적인 순수 함수(Pure Function)로 격리한다. 이를 통해 도메인 로직과 출력 로직이 완전히 분리되어, 코어 파이프라인의 수정 없이도 `renderers/` 패키지의 추가/확장(MIDI, ASCII Tab, 향후 GuitarPro)이 가능해진다.

### 4.3. 시각적 충돌 해결의 지연 (Lazy Resolution)
양자화 단계에서 딕셔너리 키 매핑을 통해 중복 노트를 억제하던 기존 방식은 '데이터 소실'이라는 돌이킬 수 없는 피해를 낳았다. 리스트 기반 누적으로 원본을 100% 보존한 뒤, 시각적으로 겹치는 프렛 번호 처리(Collision Resolution)는 최종 출력 계층인 `TabRenderer`로 책임을 완벽히 위임(Delegation)하는 것이 아키텍처적으로 타당하다.

## 5. Consequences (결과)

* **Positive:**
  * 사이드 이펙트(Side-effect)가 제거되어 파서의 데이터 오염 버그가 완벽히 해결되었다.
  * 양자화 충돌 시 선행 노트가 무단으로 증발하는 현상이 사라져 채보 데이터의 무결성이 100% 복원되었다.
* **Negative:**
  * 상태를 바꿀 때마다(`update()` 호출 시) 기존 객체는 가비지 컬렉터(GC)로 버려지고 수많은 새로운 `NoteEvent` 객체가 메모리에 재할당되므로 객체 생성 오버헤드(Instantiation Overhead)가 발생한다.
  * **방어 논리:** 본 파이프라인 전체 소요 시간의 95%는 딥러닝(CREPE, Demucs) 텐서 연산이 차지한다. 파이썬 레벨의 데이터 클래스 재생성 오버헤드는 밀리초(ms) 단위 이하로 매우 미미하므로, 시스템 안정성을 확보하는 대가로 전격 수용한다.
