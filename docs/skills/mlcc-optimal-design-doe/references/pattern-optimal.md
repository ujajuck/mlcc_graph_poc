# 패턴: 최적설계 DOE

이 패턴은 검증 패턴 이후에 진행한다. targets와 params를 수집하고, DOE 시뮬레이션을 실행해 top 5 후보를 제시한다.

## 흐름

### 1. Target 수집

빠진 targets만 묻는다. 5개:

- target_electrode_c_avg — 타겟용량 (uF)
- target_grinding_l_avg — 타겟 연마L사이즈 (um)
- target_grinding_w_avg — 타겟 연마W사이즈 (um)
- target_grinding_t_avg — 타겟 연마T사이즈 (um)
- target_dc_cap — 타겟DC용량 (uF)

사용자가 delta로 말하면 기준값이 명확할 때만 절대값으로 변환한다.

### 2. Params 수집

실행 유형에 따라 다르다.

**초기 실행 (DOE 탐색)**:

사용자에게 각 params 항목의 범위(예: ref 대비 ±5%)와 포인트 수(예: 11포인트)를 수집한 뒤, ref lot 값을 중심으로 등간격 절대값 리스트를 생성한다.

수집 항목 (10개):
- active_layer — 액티브 층수 (EA)
- ldn_avr_value — 레이다운 평균
- cast_dsgn_thk — Sheet T 두께 (um)
- screen_chip_size_leng — 스크린 길이 (um)
- screen_mrgn_leng — 스크린 마진 길이 (um)
- screen_chip_size_widh — 스크린 너비 (um)
- screen_mrgn_widh — 스크린 마진 너비 (um)
- cover_sheet_thk — 커버 두께 (um)
- total_cover_layer_num — 상+하 커버층수 (EA)
- gap_sheet_thk — 갭시트 두께 (um)

사용자가 범위를 지정하지 않으면 기본값을 제안한다: `ref 대비 ±3%, 11포인트`. 확인받은 뒤 리스트를 생성한다.

ref lot 값은 `check_optimal_design`의 `충족인자` 또는 `ref_values`에서 가져온다.

예시:
```
ref lot의 cast_dsgn_thk = 5.0 um, 사용자가 ±5% 11포인트 요청:
cast_dsgn_thk: [4.75, 4.80, 4.85, 4.90, 4.95, 5.00, 5.05, 5.10, 5.15, 5.20, 5.25]
```

**재실행 (특정 후보 기반)**:

선택 후보의 설계값을 가져와 각 항목을 `[단일값]` 리스트로 구성한다. 사용자가 변경 지시한 항목만 해당 값으로 교체한다.

### 3. Payload 조립 및 실행

```python
optimal_design(
    lot_id="AKB45A2",
    target_electrode_c_avg=10.0,
    target_grinding_l_avg=1600,
    target_grinding_w_avg=800,
    target_grinding_t_avg=850,
    target_dc_cap=10.5,
    active_layer=[150, 152, ..., 170],
    ldn_avr_value=[2.80, 2.85, ..., 3.20],
    cast_dsgn_thk=[4.75, 4.80, ..., 5.25],
    screen_chip_size_leng=[1500, 1520, ..., 1600],
    screen_mrgn_leng=[75, 78, ..., 95],
    screen_chip_size_widh=[700, 720, ..., 800],
    screen_mrgn_widh=[50, 53, ..., 70],
    cover_sheet_thk=[26, 27, ..., 34],
    total_cover_layer_num=[4, 5, ..., 8],
    gap_sheet_thk=[1.0, 1.1, ..., 1.5],
)
```

### 4. 공정검사표준 검증

결과를 사용자에게 보여주기 **전에** `search_rag`로 공정검사표준을 검색한다.

- 각 설계 항목(cast_dsgn_thk, screen_chip_size_leng, screen_mrgn_leng, screen_chip_size_widh, screen_mrgn_widh, cover_sheet_thk, active_layer, total_cover_layer_num, gap_sheet_thk 등)에 대해 표준 범위를 확인
- 범위 벗어나면 ⚠️, 확인 못하면 ❓ 표시

### 5. Top 5 결과 제시

각 후보마다:
- 후보 번호
- 핵심 설계값
- 예측 성능
- target과의 차이
- 공정검사표준 부합 여부
- 추천 이유 또는 trade-off

### 6. Rerun (재실행)

사용자가 `3번 후보에서 cast_dsgn_thk만 5.2로 바꿔서 다시` 같은 요청을 하면:

1. 최신 top 5에서 해당 후보를 찾는다
2. 해당 후보의 전체 설계값을 base로 복사한다
3. 사용자가 바꾸라고 한 field만 override한다
4. params를 각각 **단일 값 리스트** `[value]`로 구성한다
5. `optimal_design`을 다시 호출한다
6. 공정검사표준 검증 후 결과 제시

주의:
- 최신 top 5 결과가 문맥에 없으면 어떤 후보를 말하는지 먼저 확인한다
- targets도 변경할 수 있다. 예: "target_grinding_t_avg만 750으로 바꿔서 다시"

## 입력 수집 규칙

- 이미 확보된 값은 다시 묻지 않는다
- 사용자가 "그건 그대로"라고 하면 직전 값을 유지한다
- 일부 값만 수정하면 나머지는 유지한다
