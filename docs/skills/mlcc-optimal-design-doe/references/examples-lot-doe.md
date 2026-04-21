# 예시: LOT 검증 / 최적설계 / 재실행

LOT 검증, 부족인자 보충, 최적설계 DOE 실행, 재실행 관련 예시.

---

## 첫 실행 (최적설계)

### Example 1

`lot_id AKB45A2을 reference로 써서 최적설계 돌려줘.`

기대 동작:

- 먼저 `get_first_lot_detail`로 설계정보를 state에 로드
- `check_optimal_design` 실행
- 부족인자가 없으면 `targets.*`와 `params.*`를 수집
- `optimal_design` 실행 후 공정검사표준 검증 후 top 5 제시

### Example 2

`reference lot AKB45A2 기준으로 타겟용량 10uF, 타겟 연마T 800um, 연마L 1600um, 연마W 800um, DC용량 10.5uF 타겟 맞추는 설계 추천해줘.`

기대 동작:

- `get_first_lot_detail`로 설계정보 로드
- `check_optimal_design`으로 `lot_id` 검증
- 주어진 값은 `targets.*`에 채움
- 빠진 `params.*`만 질문

---

## 부족인자 보충

### Example 3

`이 lot으로 가능한지 먼저 봐줘. 안 되면 부족인자 보여줘.`

기대 동작:

- `get_first_lot_detail`로 설계정보 로드 후 `check_optimal_design` 실행
- `충족인자`(값 포함), `부족인자`를 분리해서 보여줌
- 부족인자가 있으면 값을 채울지 다른 lot을 쓸지 묻는다

### Example 4

`부족인자에 ldn_avr_value 3.0, cover_sheet_thk 28, gap_sheet_thk 1.2, screen_mrgn_widh 55 넣어줘.`

기대 동작:

- `update_lot_reference`로 값 반영
- `remaining_부족인자`가 비었으면 시뮬레이션 진행 가능 안내
- 남아있으면 나머지 인자 요청

### Example 5

`ldn_avr_value 3.0이랑 cover_sheet_thk 28만 먼저 넣어줘. 나머지는 좀 고민해볼게.`

기대 동작:

- `update_lot_reference`로 2개만 반영
- "gap_sheet_thk, screen_mrgn_widh가 아직 비어있습니다. 준비되면 알려주세요." 안내

---

## 재시뮬레이션

### Example 6

`3번째 설계값에서 cast_dsgn_thk만 5.2로 바꿔서 다시 시뮬레이션해줘.`

기대 동작:

- 최신 top 5의 3번 후보를 base로 사용
- `cast_dsgn_thk=5.2`만 override, 나머지는 그대로
- params를 각 항목 `[단일값]` 리스트로 구성
- `optimal_design` 재호출 후 결과 제시

### Example 7

`2번 후보는 그대로 두고 target_grinding_t_avg만 750으로 바꿔서 다시 보고싶어.`

기대 동작:

- `target_grinding_t_avg=750` (um)으로 수정
- params는 2번 후보 설계값 기반 단일값 리스트
- 재실행

---

## Full Response Example — 부족인자 보충 후 최적설계

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

모든 인자가 채워졌습니다. 시뮬레이션을 진행할 수 있습니다. 최적설계(DOE)와 신뢰성 시뮬레이션 중 어느 것부터 하시겠습니까?
