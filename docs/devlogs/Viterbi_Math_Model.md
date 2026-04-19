## Phase 3: Viterbi HMM 기반 베이스 기타 최적 운지법(Smart Fingering) 수학적 모델링

이 문서는 베이스 기타의 타브 악보 생성을 위해 도입된 은닉 마르코프 모델(HMM) 기반 Viterbi 디코딩 알고리즘의 핵심 수학적 원리와 비용 함수(Cost Function) 설계를 상세히 정의합니다.

### 1. 문제 정의 및 모델링 개념 (Problem Formulation)

베이스 기타는 하나의 음정(Pitch)을 여러 개의 위치(String, Fret)에서 연주할 수 있는 **다중 포지션(Multi-position) 악기**입니다. 따라서 단순히 추출된 음정(Observation)을 악보로 옮기는 것을 넘어, 연주자의 물리적 피로도와 이동 동선을 최소화하는 최적의 운지 경로를 찾아야 합니다.

이를 해결하기 위해 문제를 **은닉 마르코프 모델(Hidden Markov Model, HMM)**로 정의하고, **동적 계획법(Dynamic Programming)**의 일종인 **Viterbi 알고리즘**을 사용하여 전역 최적해(Global Optimum)를 탐색합니다.

* **관측 시퀀스 (Observations):** 시간 $t$에 따른 MIDI 노트의 배열 $O = (o_1, o_2, \dots, o_T)$
* **은닉 상태 (Hidden States):** 특정 노트 $o_t$를 연주할 수 있는 가능한 모든 운지 위치 집합 $C_t = \{x_{t,k}\}_{k=1}^{K_t}$. 여기서 상태 $x$는 줄 인덱스와 프렛 번호의 튜플 $x = (s, f)$입니다.
* **목적 함수 (Objective Function):** 전체 연주 시퀀스에서 발생하는 **전이 비용(Transition Cost)**의 총합을 최소화하는 상태 시퀀스 $X^* = (x_1^*, x_2^*, \dots, x_T^*)$를 찾는 것입니다. (방출 비용 Emission Cost는 유효한 프렛에 대해 0, 그 외는 무한대로 간주하여 생략)

$$X^* = \arg\min_{x_1 \dots x_T} \sum_{t=2}^{T} T(x_{t-1}, x_t, \Delta t)$$

여기서 $T(u, v, \Delta t)$는 상태 $u = (s_1, f_1)$에서 상태 $v = (s_2, f_2)$로 시간 $\Delta t$ 내에 이동할 때 발생하는 생체역학적 비용 함수입니다.

---

### 2. 생체역학적 비용 함수 설계 (Transition Cost Function)

현재 구현된 `ViterbiSmartFingering` 클래스의 비용 함수는 단순한 물리적 거리를 넘어, 베이스 연주의 특수성(개방현, 하이 프렛, 리듬 제약)을 수학적으로 수치화했습니다. 총 전이 비용은 다음 5가지 페널티의 합으로 계산됩니다.

$$T(u, v, \Delta t) = C_{string} + C_{height} + C_{open} + C_{fret} + C_{stay}$$

#### 2.1. 동적 시간 가중치 (Dynamic Time Multiplier)
모든 물리적 이동 페널티는 두 음표 사이의 시간 간격 $\Delta t$가 짧을수록 기하급수적으로 증가해야 합니다. 0으로 나누는 오류를 방지하기 위해 최소 0.05초(50ms)의 하한선을 둡니다.

$$M_{\Delta t} = \frac{1}{\max(\Delta t, 0.05)}$$

#### 2.2. 수직 이동 비용 (String Skipping Penalty: $C_{string}$)
줄을 건너뛰는 행위는 피킹과 핑거링 메커니즘을 방해합니다. 줄 인덱스($s_1, s_2 \in \{0, 1, 2, 3\}$)의 차이에 가중치 $W_s$를 곱합니다.

$$C_{string} = W_s \times |s_2 - s_1|$$

#### 2.3. 하이 프렛 자체 페널티 (Fret Height Penalty: $C_{height}$)
낮은 포지션(Low Fret)에서 연주하는 것이 안정성 확보에 유리합니다. 불필요하게 넥의 바디 쪽(High Fret)으로 내려가는 것을 방지하기 위해 도착 프렛 $f_2$에 비례하는 기본 비용을 부과합니다.

$$C_{height} = 0.5 \times f_2$$

#### 2.4. 수평 이동 및 개방현 비용 ($C_{open}, C_{fret}$)
가장 복잡한 로직으로, 개방현($f=0$)이 연루된 이동과 닫힌 현(Fretted) 간의 이동을 구분합니다.

**Case A: 닫힌 현 $\rightarrow$ 개방현 진입 ($f_1 \neq 0 \land f_2 = 0$)**
* 개방현은 손의 이동 제약을 풀어주지만, 톤의 이질감(Timbre Inconsistency)을 발생시킵니다. 이를 억제하기 위한 고정 페널티를 부과합니다.
$$C_{open} = P_{open}$$
$$C_{fret} = 0$$

**Case B: 개방현 $\rightarrow$ 닫힌 현 진입 ($f_1 = 0 \land f_2 \neq 0$)**
* **텔레포트 맹점 차단:** 개방현에서 출발한다고 해서 손이 순간이동할 수는 없습니다. 도착지 $f_2$가 지나치게 높은 프렛일 경우를 차단하기 위해, $f_2$에 비례하는 가상의 수평 거리를 산정합니다.
$$C_{open} = 0$$
$$C_{fret} = W_f \times f_2 \times 0.5 \times M_{\Delta t}$$

**Case C: 일반적인 수평 이동 ($f_1 \neq 0 \land f_2 \neq 0$)**
* 두 프렛 사이의 물리적 거리 $d_f = |f_2 - f_1|$를 계산합니다.
* 기본 거리 비용에 더해, 베이시스트의 한 뼘 커버 범위인 임계값 $\theta_{shift}$를 초과하는 도약에 대해서는 2차 함수 형태의 포지션 시프트 페널티($P_{shift}$)를 부여합니다.
$$C_{open} = 0$$
$$C_{fret} = \left( W_f \times d_f + P_{shift} \times \max(0, d_f - \theta_{shift})^2 \right) \times M_{\Delta t}$$

#### 2.5. 동음 유지 보너스 (Same Position Bonus: $C_{stay}$)
피치가 같은 연속된 음을 칠 때, 다른 운지 위치로 굳이 변경하여 연주하는 플래핑(Flapping) 현상을 억제합니다. 완전히 동일한 위치를 유지할 경우 음수 페널티(보너스)를 부여합니다.

$$C_{stay} = \begin{cases} -2.0 & \text{if } u = v \\ 0 & \text{otherwise} \end{cases}$$

---

### 3. Viterbi 디코딩 과정 (Forward-Backward Algorithm)

파이썬 코드의 `decode` 메서드는 다음 단계를 거쳐 최적해를 연산합니다.

1.  **State Space 초기화:** 각 시점 $t$마다 `get_fret_candidates`를 호출하여 유효한 운지 후보 $C_t$ 배열을 생성.
2.  **DP 테이블 할당:**
    * 누적 비용 테이블 $DP[t][i]$: 시점 $t$의 $i$번째 후보에 도달하기 위한 최소 누적 비용.
    * 역추적 테이블 $Backpointer[t][i]$: $DP[t][i]$가 최소가 되게 만든 시점 $t-1$의 최적 후보 인덱스.
3.  **Forward Pass (순방향 연산):**
    $$DP[t][i] = \min_{j} \left( DP[t-1][j] + T(x_{t-1, j}, x_{t, i}, \Delta t) \right)$$
    해당 연산을 $t=1$부터 $T$까지 반복하며 점화식을 채움.
4.  **Backward Pass (역추적):**
    * 마지막 시점 $T$에서 $DP[T]$가 가장 작은 인덱스를 선택.
    * $Backpointer$ 테이블을 역순으로 거슬러 올라가며 전역 최적 경로(Global Optimal Path)를 복원.
