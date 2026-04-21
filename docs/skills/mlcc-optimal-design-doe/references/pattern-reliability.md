# 패턴: 신뢰성 시뮬레이션

이 패턴은 검증 패턴 이후에 진행한다. 단일 설계 포인트에 대한 신뢰성 통과확률을 구한다.

## optimal_design과의 핵심 차이

| | optimal_design | reliability_simulation |
|---|---|---|
| params 형태 | **list** (DOE 탐색) | **scalar** (단일 설계) |
| 출력 | top 5 후보 | 통과확률 1개 |
| 목적 | 넓은 탐색 → 최적 조합 | 특정 설계의 신뢰성 검증 |

같은 설계값이라도 optimal_design에 넣을 때는 `cast_dsgn_thk: [5.0]` (단일 원소 리스트), reliability_simulation에 넣을 때는 `cast_dsgn_thk: 5.0` (scalar)이다.

## 흐름

### 0. 신뢰성 시험 조건 확보 (halt_voltage, halt_temperature)

신뢰성 시뮬레이션을 처음 실행하기 전에 **반드시 사용자에게 시험 전압과 온도를 확인**한다.

- **halt_voltage**: 장기신뢰성(HALT) 시험 전압.
  - 스펙전압 대비 배수로 받을 수 있다 (예: "1.5Vr" → 해당 기종의 정격전압 × 1.5 = 실제 전압).
  - 또는 절대 전압으로 받을 수 있다 (예: "6.3V" → 6.3).
  - 숫자만 tool에 전달한다 (단위 생략).
- **halt_temperature**: 장기신뢰성 시험 온도(°C). 예: "85도" → 85.

질문 예시:
```
신뢰성 시뮬레이션에 필요한 시험 조건을 알려주세요:
- 시험 전압: 스펙전압 대비 배수(예: 1.5Vr) 또는 절대 전압(예: 6.3V)
- 시험 온도: 예) 85°C, 105°C
```

사용자가 한 번 지정하면 이후 동일 세션에서는 다시 묻지 않고 유지한다.

### 1. 설계값 확보

설계값을 확보하는 경로는 세 가지:

**경로 A — 사용자가 직접 입력**:
사용자가 모든 설계값을 직접 제공한다.
```
"active_layer 158, ldn_avr_value 3.0, cast_dsgn_thk 5.0, screen_chip_size_leng 1550, screen_mrgn_leng 85, screen_chip_size_widh 750, screen_mrgn_widh 60, cover_sheet_thk 30, total_cover_layer_num 6, gap_sheet_thk 1.2로 신뢰성 돌려줘"
```

**경로 B — 기존 optimal_design 후보에서 가져옴**:
최적설계 결과의 특정 후보를 그대로 사용한다.
```
"3번 후보로 신뢰성 시뮬레이션 돌려봐"
```
→ 3번 후보의 `design` dict에서 설계값을 가져와 scalar로 입력한다.

**경로 C — ref lot 기본값 사용**:
`check_optimal_design`의 `ref_values`를 그대로 사용한다.
```
"ref lot 기준값 그대로 신뢰성 돌려봐"
```

### 2. reliability_simulation 호출

```python
reliability_simulation(
    lot_id="AKB45A2",
    active_layer=158,
    ldn_avr_value=3.0,
    cast_dsgn_thk=5.0,
    screen_chip_size_leng=1550,
    screen_mrgn_leng=85,
    screen_chip_size_widh=750,
    screen_mrgn_widh=60,
    cover_sheet_thk=30,
    total_cover_layer_num=6,
    halt_voltage=6.3,        # 사용자 지정 시험 전압 (V)
    halt_temperature=85,      # 사용자 지정 시험 온도 (°C)
)
```

### 3. 결과 제시

```
신뢰성 시뮬레이션 결과:

[시험 조건]
- 시험 전압: 6.3V
- 시험 온도: 85°C

| 설계값 | 값 |
|---|---|
| active_layer (액티브 층수) | 158 EA |
| ldn_avr_value (레이다운 평균) | 3.0 |
| cast_dsgn_thk (Sheet T 두께) | 5.0 um |
| screen_chip_size_leng (스크린 길이) | 1550 um |
| screen_mrgn_leng (스크린 마진 길이) | 85 um |
| screen_chip_size_widh (스크린 너비) | 750 um |
| screen_mrgn_widh (스크린 마진 너비) | 60 um |
| cover_sheet_thk (커버 두께) | 30 um |
| total_cover_layer_num (상+하 커버층수) | 6 EA |

→ 신뢰성 통과확률: 87.23%
```

### 4. 비교를 위한 반복 호출

사용자가 여러 조건을 비교하고 싶으면 이 tool을 여러 번 호출한다.

예: "cover_sheet_thk를 28, 30, 32로 바꿔가면서 신뢰성 비교해줘"

→ 3번 호출 후 비교 테이블 제시:

```
| cover_sheet_thk | 나머지 동일 | 통과확률 |
|---|---|---|
| 28 um | ... | 0.8245 |
| 30 um | ... | 0.8723 |
| 32 um | ... | 0.9012 |
```

이런 비교 요청은 자율 반복 패턴과 결합할 수 있다.

## 공정검사표준 검증

신뢰성 시뮬레이션 결과에도 공정검사표준 검증을 수행한다. optimal_design과 동일한 방식으로 `search_rag`를 호출하고, 범위 초과 시 경고를 표시한다.
