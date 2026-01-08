# Experiment Log (실험 일지)

This is a record of an experiment to improve the separation of electric guitar and bass. 
All audio files are stored on external storage (e.g., Google Drive) and can be listened to via the link.
일렉트릭 기타와 베이스 분리 성능 향상을 위한 실험 기록입니다.
모든 오디오 파일은 외부 저장소(Google Drive 등)에 저장되어 있으며, 링크를 통해 청취 가능합니다

## Summary (요약표)
| Exp ID | 날짜 | 곡명(소스 유형) | 사용 모델  | 비고 |
| :---: | :---: | :--- | :---: | :--- |
| **001** | 25.01.09 | 기타 베이스 분리 예제 1 (Raw) | htdemucs_6s | 베이스 성공적, 기타 잡음 |

---

## Details

###  Exp 001: 무지성 원테이크 (Raw Recording)
* **목표:** 기타와 베이스만 있는 트랙에서 둘을 온전히 분리할 수 있는지 검증
* **사용 음원:** 오디오 인터페이스 직렬로 직접 녹음한 일렉트릭 기타 2트랙, 일렉트릭 베이스 1트랙의 데모 (3분 30초 가량) 
* **링크:**
    *  [원본 및 분리 파일 폴더 보기 (Google Drive)] **업데이트 예정**
* **설정 (Settings):**
    * Model: `htdemucs_6s`
    * Shifts: 1 (Default)
* **결과 분석:**
    * 기타만 존재하는 구간에서 기타 소리를 베이스로 착각함
    * 분리된 기타트랙의 선명도가 준수한데 비해 베이스 트랙은 볼륨의 울렁거림이 심함
* **개선점/다음 계획:**
    * 모델 성능 향상 시도
    * 더 짧은 샘플을 직접 녹음해 실험해볼 예정
    * 기타 1트랙, 베이스 1트랙으로 이루어진 음원 제작 후 실험
