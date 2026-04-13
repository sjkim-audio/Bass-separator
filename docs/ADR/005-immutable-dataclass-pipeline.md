# [ADR-005] 불변 데이터 클래스(Immutable Dataclass) 기반 파이프라인 아키텍처 재설계

* **Status:** Accepted
* **Date:** 2026-03-01 (Retroactively Documented for Phase 4)
* **Related Documents:** [Transcription_devlog.md](../devlogs/Transcription_devlog.md)

## 1. Context (배경)

초기 전사(Transcription) 파이프라인은 단일 `BassTabGenerator` 클래스가 피치 파싱, 운지법 매핑, 양자화 등 주요 로직을 중앙에서 처리하는 형태였다. 또한, 파이프라인의 각 단계를 거칠 때마다 파이썬의 기본 가변 객체인 딕셔너리(`dict`) 리스트를 주고받으며 내부 값을 직접 수정(In-place Mutation)하는 방식을 취했다.

이러한 상태 관리(State Management) 구조는 파이프라인 고도화 과정에서 다음과 같은 부작용을 유발했다.
1. **데이터 소실 우려 (Data Loss):** 양자화 단계에서 16분음표 격자 인덱스(`grid_index`)를 딕셔너리의 키(Key)로 사용함에 따라, 슬라이드/해머링 등으로 인해 동일 시간 격자 내에 다중 노트가 겹칠 경우 선행 노트가 덮어씌워져(Overwrite) 유실될 위험이 존재했다.
2. **참조에 의한 부작용 (Call-by-Assignment Side Effects):** Phase 6의 기호 영역 보정(`_post_process_garbage_pitch`) 등 후처리 모듈이 임시로 수정한 값이 파이썬의 참조 할당 특성으로 인해 원본 이벤트 리스트에 영향을 미쳐 디버깅을 어렵게 만들었다.
3. **결합도 증가 및 스키마 부재:** 명시적인 데이터 스키마가 없는 `dict` 구조로 인해 IDE의 정적 분석 및 API 응답 계층(FastAPI Pydantic DTO)과의 연동이 매끄럽지 않았으며, 모듈 간 결합도가 높아 독립적인 단위 테스트(Unit Test) 구성에 어려움이 있었다.

## 2. Decision (결정)

가변 상태로 인한 부작용을 줄이고 데이터 흐름의 추적성을 높이기 위해, 파이프라인 전체를 관통하는 **불변 데이터 객체(Immutable Data Object) 및 단방향 데이터 흐름(Unidirectional Data Flow)** 구조를 전면 도입한다.

1. **`frozen=True` Dataclass 도입:** 데이터의 단일 진실 공급원(SSOT)으로서 `src/models/events.py`에 `NoteEvent` 데이터 클래스를 정의하고 상태 변경을 제한(Lock)한다.
2. **`update()` 메서드 패턴 (Immutable Replacement):** 파이프라인 진행 중 값이 할당되거나 변경되어야 할 경우(예: Viterbi의 `fret` 할당, Quantizer의 `grid_index` 할당), 기존 객체를 직접 수정하지 않고 파이썬의 `dataclasses.replace`를 활용하여 **변경된 값을 반영한 새로운 복제 객체를 반환**하도록 한다.
3. **List 누적 및 얕은 복사(Shallow Copy):** `dict` 키 기반의 데이터 관리 로직을 폐기하고, 모든 이벤트를 `List[NoteEvent]` 형태로 순차적으로 누적한다. 모듈 내부에서 리스트 조작이 필요할 때는 `events.copy()`로 얕은 복사를 수행한 뒤, 필요한 인덱스에 `update()`된 새 객체를 대체 삽입하여 원본 리스트의 무결성을 유지하려 시도한다.

## 3. Considered Options (검토된 대안들)

1. **딕셔너리 깊은 복사 (`copy.deepcopy`) 유지:** 모듈 간 데이터를 넘길 때나 값을 수정할 때 `deepcopy`를 사용하여 원본 훼손을 막는 방식. (기각)
2. **전역 상태 관리자 (Global State Manager):** 파이프라인 상태를 중앙에서 관리하는 전역 클래스(Singleton)를 생성하여 상태 변화를 추적하는 방식. (기각)
3. **불변 데이터 클래스 (Immutable Dataclass) 도입:** 상태 변이를 문법적으로 제한하고 갱신 시 새로운 객체를 반환하는 함수형 접근 방식. (최종 채택안)

## 4. Rationale (의사결정 근거)

### 4.1. 타입 안정성(Type Safety) 향상
`copy.deepcopy`를 사용하더라도 `dict` 구조를 유지하면 타입 힌팅(Type Hinting)의 이점을 온전히 누리기 어렵다. `NoteEvent` 불변 객체를 통한 명확한 스키마 정의는 파이프라인의 최종 산출물을 FastAPI의 `TranscriptionResponse` DTO(Pydantic) 직렬화 계층과 연동하는 과정을 보다 안정적으로 만들어 준다.

### 4.2. 모듈 간 의존성 감소
전역 상태 관리자를 도입하는 것은 객체 지향의 안티 패턴(God Object)으로 이어질 우려가 있다. 불변 객체를 활용한 단방향 파이프라인 체이닝(`Tracker -> Parser -> Fingering -> Quantizer`)은 각 모듈의 입출력을 명확히 하여 순수 함수(Pure Function)에 가깝게 동작하도록 유도한다. 이는 도메인 로직과 렌더링 로직(`renderers/`)의 분리를 용이하게 한다.

### 4.3. 데이터 충돌 해결의 위임 (Delegation of Collision Resolution)
양자화 단계에서 딕셔너리 키 매핑을 통해 중복 노트를 억제하던 방식은 데이터 소실 위험을 내포했다. 리스트 기반 누적으로 일단 모든 이벤트를 보존한 뒤, 시각적으로 겹치는 프렛 번호 처리(Collision Resolution) 등은 최종 출력 계층인 `TabRenderer`의 책임으로 위임(Delegation)하는 것이 아키텍처 관점에서 더 적절하다고 판단했다.

## 5. Consequences (결과)

* **Positive:**
  * 모듈 간 사이드 이펙트(Side-effect) 발생 가능성이 감소하여 파이프라인의 데이터 추적 및 디버깅이 이전보다 수월해졌다.
  * 양자화 충돌 시 선행 노트가 무단으로 덮어씌워지는 현상을 방지하여, 후속 렌더링 단계로 원본 이벤트 데이터를 최대한 보존하여 전달할 수 있게 되었다.
* **Negative & Limitations:**
  * 상태를 갱신할 때마다(`update()` 호출 시) 기존 객체는 가비지 컬렉터(GC) 대상이 되고 새로운 `NoteEvent` 객체가 할당되므로, 이전 구조 대비 객체 생성 오버헤드(Instantiation Overhead)가 증가한다.
  * **현재 판단:** 본 파이프라인의 전체 소요 시간 중 대부분은 딥러닝(CREPE, Demucs) 추론이 차지하고 있다. 파이썬 레벨의 데이터 클래스 재생성 오버헤드는 전체 Latency에 미치는 영향이 미미한 수준으로 관찰되어, 현재의 시스템 안정성을 우선하는 결정으로 수용한다. 단, 향후 극단적인 고속 처리가 요구될 경우 메모리 프로파일링을 통한 재검토가 필요할 수 있다.
