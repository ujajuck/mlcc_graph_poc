# 예시: Reference LOT 선정 / 검증 / 부족인자 보충

LOT 선정, 검증, 부족인자 보충 관련 예시.

---

## REF LOT 선정

### Example 1

`CL32A106KOY8NNE 인접기종에서 ref lot 찾아줘.`

기대 동작:

- 기본 필터(S,A,B등급, 신뢰성 통과 필수)로 `find_ref_lot_candidate` 호출
- 반환된 상위 LOT 목록 브리핑 (lot_id, 선정 근거)
- 사용자 확인 후 → `get_first_lot_detail` → `check_optimal_design`

### Example 2

`S등급 LOT만 골라줘, 신뢰성은 NG여도 괜찮아.`

기대 동작:

- `cutting_grade_filter=['S 등급']`, `measure_grade_filter=['S 등급']`, `require_reliability_pass=False`로 호출
- 결과가 없으면 필터 완화 제안

---

## LOT 검증

### Example 3

`lot_id AKB45A2을 reference로 써서 최적설계 돌려줘.`

기대 동작:

- 먼저 `get_first_lot_detail`로 설계정보를 state에 로드
- `check_optimal_design` 실행
- 부족인자가 없으면 다음 스킬(mlcc-optimal-design-doe)로 이어짐 안내
- 부족인자가 있으면 목록 표시 및 대응 선택지 제시

### Example 4

`이 lot으로 가능한지 먼저 봐줘. 안 되면 부족인자 보여줘.`

기대 동작:

- `get_first_lot_detail`로 설계정보 로드 후 `check_optimal_design` 실행
- `충족인자`(값 포함), `부족인자`를 분리해서 보여줌
- 부족인자가 있으면 값을 채울지 다른 lot을 쓸지 묻는다

---

## 부족인자 보충

### Example 5

`부족인자에 ldn_avr_value 3.0, cover_sheet_thk 28, gap_sheet_thk 1.2, screen_mrgn_widh 55 넣어줘.`

기대 동작:

- `update_lot_reference`로 값 반영
- `remaining_부족인자`가 비었으면 시뮬레이션 진행 가능 안내
- 남아있으면 나머지 인자 요청

### Example 6

`ldn_avr_value 3.0이랑 cover_sheet_thk 28만 먼저 넣어줘. 나머지는 좀 고민해볼게.`

기대 동작:

- `update_lot_reference`로 2개만 반영
- "gap_sheet_thk, screen_mrgn_widh가 아직 비어있습니다. 준비되면 알려주세요." 안내

---

## Full Response Example — 검증 + 부족인자 보충

User prompt:

`lot_id AKB45A2 검증하고, 부족인자 있으면 내가 값 넣을게.`

---

**Step 1: 설계정보 로드**

`get_first_lot_detail(lot_id="AKB45A2")` → status: success. ref lot 설계정보가 state에 저장되었습니다.

**Step 2: Reference 검증**

`check_optimal_design(lot_id="AKB45A2")` 실행 결과:

✅ 충족인자:
| 인자 | 값 |
|---|---|
| cast_dsgn_thk (Sheet T 두께) | 4.8 um |
| active_layer (액티브 층수) | 158 EA |
| screen_mrgn_leng (스크린 마진 길이) | 80 um |
| screen_chip_size_leng (스크린 길이) | 1550 um |

❌ 부족인자: ldn_avr_value, cover_sheet_thk, gap_sheet_thk, screen_mrgn_widh

부족인자에 원하시는 값을 알려주시면 반영하겠습니다. 또는 다른 lot_id로 교체할 수도 있습니다.

---

User: `ldn_avr_value 3.0, cover_sheet_thk 28, gap_sheet_thk 1.2, screen_mrgn_widh 55`

---

**Step 3: 부족인자 반영**

`update_lot_reference(lot_id="AKB45A2", factors={...})` 실행 결과:

| 인자 | 값 | 상태 |
|---|---|---|
| cast_dsgn_thk (Sheet T 두께) | 4.8 um | 기존 |
| active_layer (액티브 층수) | 158 EA | 기존 |
| screen_mrgn_leng (스크린 마진 길이) | 80 um | 기존 |
| screen_chip_size_leng (스크린 길이) | 1550 um | 기존 |
| ldn_avr_value (레이다운 평균) | 3.0 | ✅ 반영 |
| cover_sheet_thk (커버 두께) | 28 um | ✅ 반영 |
| gap_sheet_thk (갭시트 두께) | 1.2 um | ✅ 반영 |
| screen_mrgn_widh (스크린 마진 너비) | 55 um | ✅ 반영 |

모든 인자가 채워졌습니다. 시뮬레이션을 진행할 수 있습니다.
최적설계(DOE)나 신뢰성 시뮬레이션을 원하시면 mlcc-optimal-design-doe 또는 mlcc-convergence-search로 이어갑니다.
