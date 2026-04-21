# Tool Contracts — LOT 선정 및 검증

이 reference는 mlcc-lot-validation 스킬이 의존하는 4개 tool의 계약을 설명한다.

## Contents

- find_ref_lot_candidate
- get_first_lot_detail
- check_optimal_design
- update_lot_reference

---

## find_ref_lot_candidate

목적: chip_prod_id 목록에서 11개 품질지표를 기반으로 우수한 Reference LOT 후보를 선별한다.

입력:

- `chip_prod_id_list`: List[str] — **(필수)** 인접기종 chip_prod_id 리스트
- `cutting_grade_filter`: List[str] — 허용할 커팅 불량률 등급. 기본값: `['S 등급', 'A 등급', 'B 등급']`
- `measure_grade_filter`: List[str] — 허용할 측정 불량률 등급. 기본값: `['S 등급', 'A 등급', 'B 등급']`
- `exclude_screen_codes`: List[str] — 제외할 screen_durable_spec_name 6번째 자리 코드. 기본값: `['F','L','G','K','E']`
- `exclude_screen_types`: List[str] — 제외할 screen_durable_spec_name 11~13자리 타입. 기본값: `['3DJ','VLC','RHM','EXT','MPM','SHI']`
- `require_reliability_pass`: bool — 신뢰성 시험 통과 필수 여부. 기본값: `True`
- `top_k`: int — 반환할 상위 LOT 수. 기본값: `20`

출력:

- 상위 LOT 목록 (lot_id, chip_prod_id, 품질지표 요약 포함)
- `status: fail`이면 조건에 맞는 LOT 없음

사용 규칙:

- 미지정 파라미터는 기본값이 적용된다.
- 사용자 자연어 요청 → 파라미터 변환 매핑은 `pattern-ref-lot-selection.md` 참고.
- 결과가 없으면 필터를 완화하여 재호출한다. 상세 대응법은 `pattern-ref-lot-selection.md` 참고.

---

## get_first_lot_detail

목적: ref lot으로 선정된 LOT의 설계정보를 DB에서 조회하여 세션 state에 저장한다. 이후 `check_optimal_design` 등 다른 tool이 이 state를 참조한다.

입력:

- `lot_id`: string

출력:

- `status`: "success" 또는 "error"
- `ref_lot_design_info`: lot의 주요 설계 컬럼 정보 (chip_prod_id, lot_id, cur_site_div, electrode_c_avg, app_type, active_powder_base, ldn_cv_value, cast_dsgn_thk 등)
- `hint`: 다음 단계 안내 메시지

사용 규칙:

- 새 `lot_id`가 들어오면 **가장 먼저** 호출한다. `check_optimal_design`보다 앞선다.
- 이 tool이 state에 lot 데이터를 저장해야 `check_optimal_design`이 정상 동작한다.
- `status: "error"`이면 해당 lot이 DB에 없는 것이므로 다른 lot_id를 요청한다.
- **chip_prod_id를 넣으면 에러.** 반드시 lot_id를 넣는다.
- 동일 lot_id로 이미 호출한 경우 중복 호출할 필요 없다.

---

## check_optimal_design

목적: 주어진 `lot_id`가 시뮬레이션 기준 reference로 사용 가능한지 확인한다. `get_first_lot_detail`이 선행되어야 한다.

입력:

- `lot_id`: string

출력:

- `status`: "success" (한 개 이상 버전 충족) 또는 "warning" (모든 버전에 부족인자 존재)
- `fully_satisfied_versions`: list — 부족인자가 없는 버전 리스트 (예: `["ver1", "ver3"]`). 이 버전들로 시뮬레이션 진행 가능.
- `partially_missing_versions`: dict — 부족인자가 있는 버전과 해당 부족인자
- `충족인자`: dict — 버전별 {인자명: 현재값}
- `부족인자`: dict — 버전별 부족인자 리스트

사용 규칙:

- `get_first_lot_detail` 이후에 호출한다. state에 lot 데이터가 없으면 에러를 반환한다.
- **`fully_satisfied_versions`가 하나라도 있으면 시뮬레이션 진행 가능**이다. 모든 버전이 충족될 때까지 기다릴 필요 없다.
- 충족된 버전으로 시뮬레이션을 진행하고, 나머지 버전의 부족인자는 참고 정보로 안내한다.
- 모든 버전에 부족인자가 있을 때만(`fully_satisfied_versions`가 빈 리스트) 사용자에게 선택지를 제시한다.
- `충족인자`의 값은 이후 params 기본값 제안에 활용할 수 있다.

---

## update_lot_reference

목적: `check_optimal_design`에서 확인된 부족인자에 사용자 지정 값을 반영한다.

입력:

- `lot_id`: string
- `factors`: dict — {인자명: 값} 형태. 예: `{"cast_dsgn_thk": 3.2, "cover_sheet_thk": 28}`

출력:

- `updated_factors`: 이번에 반영된 인자들
- `ref_values`: 업데이트 후 전체 인자 현황 (base + override 병합)
- `remaining_부족인자`: 아직 남아있는 부족인자 목록

사용 규칙:

- `check_optimal_design` 이후에만 호출한다.
- 사용자가 부족인자 값을 제공하면 이 tool로 반영한다.
- 이미 `fully_satisfied_versions`가 있으면 부족인자 보충 없이도 시뮬레이션을 진행할 수 있다. 보충은 추가 버전 활성화를 위한 것이다.
- 한 번에 모든 부족인자를 채울 필요는 없다. 여러 번 호출해도 된다.
