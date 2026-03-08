# 🎸 Bass Transcription API Specification (v1)

본 API는 대용량 오디오 딥러닝 추론에 최적화된 **비동기 폴링(Asynchronous Polling)** 아키텍처를 사용합니다. 클라이언트는 파일을 업로드한 후 반환받은 `task_id`를 이용해 처리 완료 여부를 주기적으로 확인해야 합니다.

* **Base URL:** `/api/v1`
* **Workflow:** `POST /transcribe` (파일 업로드) -> `202 Accepted` 반환 -> `GET /status/{task_id}` (2~3초 주기 폴링) -> 완료 시 데이터 수신

---

## 1. 전사 작업 요청 (Upload & Start Task)

오디오 파일을 서버에 업로드하고 베이스 분리 및 타브 채보 파이프라인(Background Task)을 시작합니다.

* **URL:** `/transcribe`
* **Method:** `POST`
* **Content-Type:** `multipart/form-data`

### Request Parameters
| Name | Type | In | Required | Description |
| :--- | :--- | :--- | :---: | :--- |
| `file` | file | formData | **Yes** | 분석할 오디오 파일 (`.wav`, `.mp3` 등). **최대 10MB 제한.** |

### Responses

**✅ 202 Accepted (작업 수락됨)**
작업이 대기열(Queue)에 성공적으로 등록되었음을 의미합니다.
```json
{
  "status": "ACCEPTED",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Inference started in background."
}
```

**❌ 413 Payload Too Large**
파일 크기가 10MB를 초과했을 때 발생합니다.
```json
{
  "detail": "File too large (Max 10MB)"
}
```

---

## 2. 작업 상태 및 결과 조회 (Poll Task Status)

발급받은 `task_id`를 사용하여 작업 진행 상태를 확인하고, 완료 시 전체 악보 데이터를 수신합니다. (권장 폴링 주기: 3초)

* **URL:** `/status/{task_id}`
* **Method:** `GET`

### Request Parameters
| Name | Type | In | Required | Description |
| :--- | :--- | :--- | :---: | :--- |
| `task_id` | string | path | **Yes** | `/transcribe`에서 반환받은 UUID |

### Responses

**⏳ 200 OK (작업 진행 중)**
데이터 처리가 아직 끝나지 않은 상태입니다. 클라이언트는 계속 대기(Polling)해야 합니다.
```json
{
  "status": "PROCESSING",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**✅ 200 OK (작업 완료 및 데이터 반환)**
데이터 구조체(`TranscriptionResponse`)가 반환됩니다. 모든 부동소수점(float) 데이터는 네트워크 최적화를 위해 **소수점 3자리(밀리초 해상도)**로 강제 반올림되어 전송됩니다.

```json
{
  "status": "SUCCESS",
  "data": {
    "status": "SUCCESS",
    "bpm": 125.0,
    "ascii_tab": "🎸 Quantized Bass Tab (BPM: 125)\n\nG |--------------------------------|\nD |---0-------------------0---0----|\nA |--------------------------------|\nE |-----------------------------3--|\n",
    "metadata": {
      "task_id": "550e8400-e29b-41d4-a716-446655440000",
      "model_version": "demucs-htdemucs-v4.1_crepe-tiny",
      "processing_time_ms": 14520.35
    },
    "events": [
      {
        "start_time": 0.08,
        "duration": 0.0,
        "midi_note": 38,
        "string_idx": 2,
        "fret": 0,
        "confidence": 0.985
      },
      {
        "start_time": 1.74,
        "duration": 0.0,
        "midi_note": 31,
        "string_idx": 0,
        "fret": 3,
        "confidence": 0.872
      }
    ]
  }
}
```

---

## 3. 데이터 사전 (Data Dictionary)

응답 페이로드 내 `events` 배열을 구성하는 개별 노트(`BassNoteEvent`)의 스키마 명세입니다.

| Field | Type | Description |
| :--- | :--- | :--- |
| `start_time` | float | 물리적 오디오 기준 노트 발생 시간 (초 단위, ex: `1.74`) |
| `duration` | float | (예약됨) 노트의 지속 시간 (현재는 기본값 `0.0` 할당) |
| `midi_note` | int | 추출된 피치의 표준 MIDI 노트 번호 (ex: E1 = `28`) |
| `string_idx` | int | 운지할 베이스 현의 인덱스 (**`0` = 4번줄 E현**, `1` = 3번줄 A현, `2` = 2번줄 D현, `3` = 1번줄 G현) |
| `fret` | int | 운지할 프렛 번호 (`0` = 개방현, `1~24` = 프렛) |
| `confidence` | float | AI 모델(CREPE)의 피치 예측 신뢰도. `0.0` ~ `1.0` 사이의 값. (UI에서 불확실한 노트의 투명도를 낮추거나 고스트 노트로 표시할 때 사용) |

---
💡 **Frontend Implementation Tip (프론트엔드 연동 팁):**
단순히 `ascii_tab` 필드의 문자열을 `<pre>` 태그로 화면에 출력할 수도 있지만, 인터랙티브한 악보(노트 클릭, 하이라이팅, 재생바 동기화 등)를 구현하려면 `events` 배열의 `start_time`과 `string_idx`, `fret` 데이터를 기반으로 UI 컴포넌트를 직접 렌더링하는 것을 권장합니다.
