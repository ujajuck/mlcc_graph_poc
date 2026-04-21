# Tool Contracts — 최적설계 / 신뢰성 시뮬레이션

이 reference는 mlcc-convergence-search 스킬이 의존하는 3개 tool의 계약을 설명한다.

## Contents

- optimal_design
- reliability_simulation
- search_rag (공정검사표준 검증용)
- 공통 해석 규칙

---

## optimal_design

목적: reference LOT과 사용자 target, DOE 입력값으로 최적 설계 후보를 계산한다.

입력:

- `lot_id`: string
- `target_electrode_c_avg`: float — 타겟용량 (uF)
- `target_grinding_l_avg`: float — 타겟 연마L사이즈 (um)
- `target_grinding_w_avg`: float — 타겟 연마W사이즈 (um)
- `target_grinding_t_avg`: float — 타겟 연마T사이즈 (um)
- `target_dc_cap`: float — 타겟DC용량 (uF)
- `active_layer`: list[int] — 액티브 층수 (EA)
- `ldn_avr_value`: list[float] — 레이다운 평균
- `cast_dsgn_thk`: list[float] — Sheet T 두께 (um)
- `screen_chip_size_leng`: list[float] — 스크린 길이 (um)
- `screen_mrgn_leng`: list[float] — 스크린 마진 길이 (um)
- `screen_chip_size_widh`: list[float] — 스크린 너비 (um)
- `screen_mrgn_widh`: list[float] — 스크린 마진 너비 (um)
- `cover_sheet_thk`: list[float] — 커버 두께 (um)
- `total_cover_layer_num`: list[int] — 상+하 커버층수 (EA)
- `gap_sheet_thk`: list[float] — 갭시트 두께 (um)

### params 값 형식

**초기 실행 (DOE 탐색)**: 각 params 필드에 ref lot 값 중심 ±범위의 다중 포인트 리스트를 채운다.

예시 — ref lot의 cast_dsgn_thk = 5.0, 사용자가 ±5% 11포인트 요청:
- `cast_dsgn_thk`: `[4.75, 4.80, 4.85, 4.90, 4.95, 5.00, 5.05, 5.10, 5.15, 5.20, 5.25]`

**재실행 (특정 후보 기반)**: 선택 후보의 설계값을 각각 단일 값 리스트 `[value]`로 구성한다.

출력:

- `top_candidates`: 최적 설계 후보 5개. 각 후보에 `rank`, `design`, `predicted`, `gap` 포함.

---

## reliability_simulation

목적: 단일 설계 포인트에 대한 장기신뢰성(HALT) 통과확률을 계산한다.

입력:

- `lot_id`: string
- `active_layer`: int — 액티브 층수 (EA), **scalar, list가 아님**
- `ldn_avr_value`: float — 레이다운 평균
- `cast_dsgn_thk`: float — Sheet T 두께 (um)
- `screen_chip_size_leng`: float — 스크린 길이 (um)
- `screen_mrgn_leng`: float — 스크린 마진 길이 (um)
- `screen_chip_size_widh`: float — 스크린 너비 (um)
- `screen_mrgn_widh`: float — 스크린 마진 너비 (um)
- `cover_sheet_thk`: float — 커버 두께 (um)
- `total_cover_layer_num`: int — 상+하 커버층수 (EA)
- `halt_voltage`: float (optional, default 5) — 장기신뢰성 시험 전압. 스펙전압 대비 배수(예: 1.5Vr)로 받거나 절대전압(V)으로 받는다.
- `halt_temperature`: float (optional, default 5) — 장기신뢰성 시험 온도(°C).

출력:

- `design`: 입력된 설계값
- `reliability_pass_rate`: float (신뢰성 통과확률 %)

사용 규칙:

- optimal_design과 달리 **params가 scalar**다. list로 넣지 않는다.
- 여러 설계 조건을 비교하려면 이 tool을 **여러 번 호출**한다.
- **halt_voltage, halt_temperature는 사용자에게 반드시 한 번 확인받아야 한다.** 기본값(5)을 그대로 쓰지 말고, 사용자가 신뢰성 시뮬레이션을 요청하면 시험 전압과 온도를 먼저 물어본다.
- lot_id 검증(check_optimal_design)이 선행되어야 한다.

---

## search_rag (공정검사표준 검증용)

목적: 시뮬레이션 결과의 각 설계값이 공정검사표준 범위 안에 있는지 확인한다.

입력:

- `query`: 검증하려는 설계 항목 키워드. 예: `"공정검사표준 cast_dsgn_thk 범위"`, `"검사표준 screen_mrgn_leng 상한 하한"`
- `top_k`: 기본 3~5

출력:

- 관련 공정검사표준 청크 (표준 항목명, 상한/하한, 단위, 적용 조건 등)

사용 규칙:

- `optimal_design` 또는 `reliability_simulation` 결과가 나온 직후, 결과를 사용자에게 보여주기 **전에** 검증한다.
- 범위를 벗어나면 `⚠️ 공정검사표준 초과`로 표시한다.
- 표준 정보를 못 찾으면 `❓ 공정검사표준 미확인`으로 표시하고 넘어간다.

---

## 공통 해석 규칙

- 실제 field 이름은 tool schema를 우선한다.
- nested schema보다 flat schema를 우선 해석한다.
- `targets.*`, `params.*`는 개념적 그룹명이다.
