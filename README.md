# Guitar & Bass Separator

**Guitar & Bass Separator**는 딥러닝 모델(Demucs)을 활용하여 오디오 트랙에서 **일렉트릭 기타(Electric Guitar)**와 **베이스(Bass)** 신호를 정밀하게 식별하고 분리하는 프로젝트입니다.

## 🎯 프로젝트 목표 (Project Goal)

일렉트릭 기타와 베이스는 주파수 대역(Low-Mid)이 겹치고 믹싱 과정에서 사운드가 얽혀있어, 일반적인 EQ 필터링만으로는 깔끔한 분리가 어렵습니다. 이 프로젝트는 최신 AI 모델을 통해 이 문제를 해결하고자 합니다.

1.  **고성능 분리 구현:** `htdemucs_6s` 모델을 활용해 6개 트랙(Drums, Bass, Guitar, Piano, Vocals, Others) 중 기타와 베이스를 명확히 격리합니다.
2.  **다양한 데이터 실험:**
    * **Commercial Source:** 이미 믹싱/마스터링이 완료된 유명 밴드 음원에서의 분리 성능 테스트
    * **Raw Source:** 오디오 인터페이스로 직접 녹음한 가공되지 않은 소스 테스트
3.  **접근성 확보:** 고성능 GPU가 없는 환경에서도 Google Colab을 통해 즉시 실행 가능한 환경을 제공합니다.
