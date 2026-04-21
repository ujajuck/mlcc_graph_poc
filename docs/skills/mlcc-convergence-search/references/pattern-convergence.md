# 패턴: 수렴 탐색 (Convergence Search)

사용자가 타겟 수치와 신뢰성 기준을 동시에 제시하고, "알아서 두 조건 다 맞는 설계를 찾아줘" 류의 요청을 하면 이 패턴을 적용한다. 에이전트가 체계적으로 설계값을 조정하며 **최적설계 타겟 적중 + 신뢰성 통과**를 동시에 만족하는 설계점으로 수렴해 나간다.

## 자율 반복 패턴과의 차이

| | 자율 반복 (pattern-autonomous) | 수렴 탐색 (pattern-convergence) |
|---|---|---|
| 목표 | 단일 축 최적화 또는 단순 비교 | **다중 목표 동시 만족** (타겟 + 신뢰성) |
| 전략 | 자유 판단, 패턴 A~D 중 선택 | **4-Phase 체계적 수렴** |
| 파라미터 조정 | 임의 | **gap 기반 방향성 조정 룰** 적용 |
| 종료 조건 | 사용자 만족 | 수렴 기준 충족 (gap + 신뢰성 동시) |

## 사전 조건

- lot_id 검증 완료 (get_first_lot_detail → check_optimal_design → 부족인자 해결)
- 사용자로부터 다음을 확보:
  - **targets**: target_electrode_c_avg(uF), target_grinding_l_avg(um), target_grinding_w_avg(um), target_grinding_t_avg(um), target_dc_cap(uF)
  - **신뢰성 시험 조건**: halt_voltage (시험 전압 — 스펙전압 대비 배수 예: 1.5Vr 또는 절대전압 예: 6.3V), halt_temperature (시험 온도°C 예: 85)
  - **신뢰성 기준**: 최소 통과확률 (예: 80% 이상). 사용자가 명시하지 않으면 80%를 기본값으로 제안한다.
  - **허용 오차** (선택): target 대비 허용 gap (예: 용량 ±3%). 미지정 시 ±5%를 기본값으로 제안한다.

## Phase 1 — 감도 분석 (Sensitivity Scan)

### 목적

넓은 범위의 첫 DOE로 "어떤 파라미터가 어떤 출력에 가장 큰 영향을 주는지" 파악한다.

### 흐름

1. ref lot 기준 ±5%, 11포인트로 전체 params에 대해 `optimal_design` 실행
2. top 5 전체에 `reliability_simulation` 실행 (5회)
3. 결과를 분석하여 감도 매핑:

```
감도 분석 결과:

| 파라미터 | 용량 영향 | 연마T 영향 | 신뢰성 영향 | 핵심 축 |
|---|---|---|---|---|
| active_layer | ★★★ | ★ | ★ | 용량 |
| cast_dsgn_thk | ★★ | ★★ | ★ | 용량/연마T |
| cover_sheet_thk | ★ | ★★ | ★★★ | 신뢰성 |
| screen_mrgn_leng | ★ | ★ | ★★★ | 신뢰성 |
| screen_mrgn_widh | ★ | ★ | ★★ | 신뢰성 |
| total_cover_layer_num | ★ | ★★★ | ★★ | 연마T |
| ... | ... | ... | ... | ... |

→ 신뢰성 핵심 축: cover_sheet_thk, screen_mrgn_leng
→ 타겟 핵심 축: active_layer, cast_dsgn_thk
```

### 감도 판단 기준

top 5 후보 간 해당 파라미터 값의 변동과 출력(predicted, reliability) 변동의 상관을 본다:
- 파라미터 값이 다른 후보들 사이에서 출력 차이가 크면 → 영향 큼 (★★★)
- 파라미터 값이 달라도 출력 차이가 작으면 → 영향 작음 (★)

### 사용자 보고

감도 분석 결과를 요약해서 보여주고, 수렴 탐색 전략을 공유한 뒤 컨펌을 받는다.

## Phase 2 — 실현 가능 영역 탐색 (Feasibility Search)

### 목적

신뢰성 통과 기준을 만족하는 파라미터 범위("실현 가능 영역")를 먼저 확보한다.

### 흐름

1. Phase 1에서 파악한 **신뢰성 핵심 축** 1~2개를 선정
2. 해당 축을 스윕하면서 `reliability_simulation` 반복 호출 (3~5회)
3. 통과확률이 기준 이상인 값의 범위를 확인

```
cover_sheet_thk 스윕 결과 (나머지는 ref lot 기준):

| cover_sheet_thk | 통과확률 | 판정 |
|---|---|---|
| 24 | 0.68 | ❌ |
| 26 | 0.74 | ❌ |
| 28 | 0.82 | ✅ |
| 30 | 0.87 | ✅ |
| 32 | 0.91 | ✅ |

→ 실현 가능 영역: cover_sheet_thk ≥ 28
```

4. 확보된 실현 가능 영역을 다음 Phase의 params 범위로 제한한다

### 핵심 축이 2개인 경우

두 축의 조합으로 스윕한다. 예: cover_sheet_thk × screen_mrgn_leng 격자 (3×3 = 9회)

## Phase 3 — 타겟 수렴 (Target Convergence)

### 목적

실현 가능 영역 내에서 DOE를 반복 실행하며, target gap을 줄여나간다.

### 흐름

1. Phase 2에서 확보한 실현 가능 영역으로 params 범위를 제한
2. `optimal_design` 실행 → top 5 확인
3. top 1 후보의 predicted vs target gap을 분석
4. **파라미터 조정 룰 테이블**에 따라 조정 방향을 결정
5. 조정된 값으로 rerun (단일값 리스트)
6. gap이 허용 오차 이내이면 → Phase 4로 진행
7. gap이 아직 크면 → 4~6 반복 (최대 3회)

### 파라미터 조정 룰 테이블

이 테이블은 predicted와 target 사이의 gap을 보고, **어떤 파라미터를 어떤 방향으로 조정해야 하는지** 판단하는 기준이다.

| gap 상태 | 조정 파라미터 | 조정 방향 | 이유 |
|---|---|---|---|
| electrode_c_avg 부족 (용량↓) | active_layer | ↑ 증가 | 적층 수 증가 → 용량 증가 |
| electrode_c_avg 부족 (용량↓) | cast_dsgn_thk | ↓ 감소 | 시트 얇게 → 같은 부피에 적층 증가 → 용량 증가 |
| electrode_c_avg 초과 (용량↑) | active_layer | ↓ 감소 | 적층 수 감소 → 용량 감소 |
| grinding_t_avg 초과 (연마T↑) | total_cover_layer_num | ↓ 감소 | 커버층 줄이면 전체 두께 감소 |
| grinding_t_avg 초과 (연마T↑) | cover_sheet_thk | ↓ 감소 | 커버 두께 줄이면 전체 두께 감소 |
| grinding_t_avg 초과 (연마T↑) | gap_sheet_thk | ↓ 감소 | 갭시트 줄이면 전체 두께 감소 |
| grinding_t_avg 부족 (연마T↓) | total_cover_layer_num | ↑ 증가 | 커버층 늘리면 두께 증가 |
| grinding_l_avg / grinding_w_avg 편차 | screen_chip_size_leng / screen_chip_size_widh | 직접 조정 | 스크린 사이즈가 연마 사이즈에 직접 영향 |
| dc_cap 부족 | active_layer, ldn_avr_value | ↑ 증가 | DC 용량은 적층수와 레이다운에 비례 |
| 신뢰성 하락 | cover_sheet_thk, screen_mrgn_leng | ↑ 증가 | 마진/커버 여유 확보 → 신뢰성 개선 |

### 조정 원칙

- **한 번에 1~2개 파라미터만 조정**한다. 동시에 여러 개를 바꾸면 어떤 변화가 효과를 냈는지 판단할 수 없다.
- 조정 폭은 현재 gap의 크기에 비례한다. gap이 크면 ±3~5%, 작으면 ±1~2%.
- 신뢰성과 타겟이 상충하는 경우, **신뢰성을 먼저 확보**한 뒤 타겟을 조정한다.
- 3회 반복 후에도 수렴하지 않으면 사용자에게 중간 결과를 보고하고, 타겟 완화 또는 범위 변경을 협의한다.

### 수렴 판정 기준

모든 target의 gap이 허용 오차 이내 **AND** 신뢰성 통과확률이 기준 이상이면 수렴으로 판정한다.

```
수렴 판정:
- electrode_c_avg gap: +0.02uF (허용 ±0.5uF) ✅
- grinding_l_avg gap: -5um (허용 ±50um) ✅
- grinding_w_avg gap: +3um (허용 ±30um) ✅
- grinding_t_avg gap: +10um (허용 ±50um) ✅
- dc_cap gap: +0.03uF (허용 ±0.5uF) ✅
- 신뢰성 통과확률: 0.86 (기준 ≥0.80) ✅
→ 수렴 완료
```

## Phase 4 — 최종 검증 및 추천

### 흐름

1. 수렴된 설계점에 대해 `reliability_simulation` 최종 확인
2. `search_rag`로 공정검사표준 검증
3. 전체 탐색 과정 요약 + 최종 추천 제시

### 최종 보고 형식

```
수렴 탐색 완료 (총 N회 시뮬레이션)

[탐색 경과]
- Phase 1: 초기 DOE → 신뢰성 핵심 축 cover_sheet_thk, screen_mrgn_leng 파악
- Phase 2: cover_sheet_thk ≥ 28에서 신뢰성 통과 확인
- Phase 3: 2회 반복으로 타겟 수렴

[최종 설계]
| 파라미터 | 값 |
|---|---|
| active_layer | 160 EA |
| ldn_avr_value | 3.05 |
| cast_dsgn_thk | 4.9 um |
| screen_chip_size_leng | 1540 um |
| screen_mrgn_leng | 88 um |
| screen_chip_size_widh | 760 um |
| screen_mrgn_widh | 62 um |
| cover_sheet_thk | 30 um |
| total_cover_layer_num | 6 EA |
| gap_sheet_thk | 1.15 um |

[예측 성능 vs 타겟]
| 항목 | 타겟 | 예측 | gap | 판정 |
|---|---|---|---|---|
| electrode_c_avg | 10.0 uF | 10.02 uF | +0.02 | ✅ |
| grinding_l_avg | 1600 um | 1595 um | -5 | ✅ |
| grinding_w_avg | 800 um | 803 um | +3 | ✅ |
| grinding_t_avg | 850 um | 860 um | +10 | ✅ |
| dc_cap | 10.5 uF | 10.53 uF | +0.03 | ✅ |

[신뢰성] 통과확률: 0.8634 (기준 ≥ 0.80) ✅
[공정검사표준] 전 항목 부합 ✅

이 설계를 base로 추가 미세 조정하시겠습니까?
```

## 제약 사항

- 전체 탐색에서 tool 호출 총 횟수가 **20회를 초과**할 것으로 예상되면, Phase 시작 전 사용자에게 확인한다.
- Phase 3 반복이 **3회**를 넘으면 자동 수렴 시도를 중단하고 중간 결과를 보고한다.
- 탐색 도중 사용자가 타겟이나 기준을 변경하면, 변경된 조건으로 해당 Phase부터 재시작한다.
- 파라미터 조정 룰 테이블은 가이드이며, 실제 시뮬레이션 결과가 예상과 다르면 반대 방향 조정도 시도한다.
- 상충 상황(타겟 충족 ↔ 신뢰성 충족이 양립 불가)이 명확해지면 즉시 사용자에게 trade-off를 보고하고 우선순위를 협의한다.

## 사용자 요청 예시

| 사용자 요청 | 수렴 탐색 적용 |
|---|---|
| "타겟 맞추면서 신뢰성 80% 이상 나오는 설계 찾아줘" | 전체 Phase 1→2→3→4 |
| "용량 10uF, 연마T 850um 맞추고 신뢰성도 확보해줘" | Phase 1→2→3→4 |
| "알아서 최적설계랑 신뢰성 둘 다 만족하는거 찾아" | Phase 1→2→3→4 |
| "지금 후보에서 신뢰성이 떨어지는데, 타겟 유지하면서 개선해줘" | Phase 3부터 (기존 후보를 base로) |
