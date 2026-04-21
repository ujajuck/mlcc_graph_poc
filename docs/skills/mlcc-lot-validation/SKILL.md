---
name: mlcc-lot-validation
description: MLCC Reference LOT 선정 및 검증 스킬. 사용자가 `ref lot 찾아줘`, `S등급 LOT 골라줘`, `인접기종에서 reference 선정해줘`, `lot 검증해줘`, `부족인자 채워줘`, `AKB45A2 검증해줘` 같은 요청을 할 때 사용한다. chip_prod_id 목록에서 품질 기준에 맞는 LOT을 찾고, 해당 LOT의 설계정보를 로드하여 시뮬레이션 가능 여부를 검증하며, 부족인자가 있으면 사용자로부터 값을 받아 채운다.
---

# MLCC Reference LOT 선정 및 검증

인접기종 chip_prod_id 목록에서 품질 우수 Reference LOT를 선정하고, 선정된 LOT의 설계정보를 로드하여 시뮬레이션 가능 여부를 검증한다. 이 스킬의 출력(lot_id)이 `mlcc-optimal-design-doe`와 `mlcc-convergence-search`의 시작점이다.

## 세션 상태 읽기/쓰기

> 필드 정의와 타입/단위는 `../session-state.md`를 참고한다.

**읽는 필드** (이전 스킬에서 전달됨):
- `chip_prod_id_list` ← mlcc-rag-spec-selector 출력. `find_ref_lot_candidate` 입력으로 사용.

**쓰는 필드** (이 스킬이 갱신):
- `lot_id` — REF LOT 확정 후 기록
- `chip_prod_id` — 선정된 기종 기록

**다음 단계**: lot_id 검증 완료 후 mlcc-optimal-design-doe (최적설계/신뢰성 단독 실행) 또는 mlcc-convergence-search (자율 반복/수렴 탐색)로 이어진다.

## 실행 원칙

- tool 호출이 실패하거나 결과가 0건이어도 즉시 포기하지 않는다. 필터를 완화하거나, 다른 조건으로 재시도하거나, 사용자에게 대안을 제시한다.
- `get_first_lot_detail`에 **chip_prod_id를 넣으면 에러**. 반드시 lot_id를 넣는다.

## 필수 실행 순서

| 순서 | Tool | 선행 조건 | 출력 |
|------|------|-----------|------|
| ① | `find_ref_lot_candidate(chip_prod_id_list)` | chip_prod_id_list 있음 | **lot_id** |
| ② | `get_first_lot_detail(lot_id)` | ①에서 lot_id 확보됨 | ref lot 설계정보 로드 |
| ③ | `check_optimal_design(lot_id)` | ②번 완료 | fully_satisfied_versions, 부족인자 |
| ④ | `update_lot_reference(lot_id, factors)` | ③에서 부족인자 확인 + 사용자 값 제공 | 부족인자 보충 (선택) |

**규칙:**
- ①은 lot_id가 이미 직접 주어졌으면 생략 가능
- **②③은 절대 생략 불가**
- **`fully_satisfied_versions`가 한 개라도** 있으면 시뮬레이션 진행 가능. ④는 추가 버전 활성화를 위한 선택 단계.

## Tool 계약 요약

전체 계약은 `references/tool-contracts.md`에 있다.

- `find_ref_lot_candidate`: chip_prod_id_list 필수. 품질 필터(등급, 신뢰성, 스크린 코드) 선택 파라미터 지원. 필터 매핑은 `references/pattern-ref-lot-selection.md` 참고.
- `get_first_lot_detail`: lot_id 필수 (chip_prod_id 넣으면 에러).
- `check_optimal_design`: get_first_lot_detail 선행 필수. fully_satisfied_versions와 부족인자 반환.
- `update_lot_reference`: check_optimal_design 이후에만 호출. 부족인자 일부만 채워도 됨.

## 패턴 라우팅

| 요청 유형 | 패턴 |
|---|---|
| "인접기종에서 ref lot 찾아줘" / "S등급만 골라줘" | REF LOT 선정 패턴 → `references/pattern-ref-lot-selection.md` |
| "lot 검증해줘" / "이 lot 쓸 수 있어?" | 검증 패턴 → `references/pattern-validation.md` |
| "부족인자 채워줘" / "ldn_avr_value 3.0 넣어줘" | 부족인자 보충 (update_lot_reference) |
| lot_id가 이미 주어진 경우 | ①(find) 생략 → ②(detail) → ③(check) |

## 보충 Reference 문서

- `references/tool-contracts.md`: 4개 tool 입출력 상세
- `references/pattern-ref-lot-selection.md`: find_ref_lot_candidate 파라미터 매핑, 대화 예시, 결과 없을 때 대응
- `references/pattern-validation.md`: get_first_lot_detail → check_optimal_design 흐름, 버전별 판정, 응답 예시
- `references/examples-lot-validation.md`: LOT 선정/검증/부족인자 보충 예시 (Examples 1-5)

## 실패 처리

- `find_ref_lot_candidate` 결과 0건: 등급 필터 완화(S→S,A,B) 또는 신뢰성 조건 완화(`require_reliability_pass=False`) 제안. 상세는 `pattern-ref-lot-selection.md` 참고.
- `get_first_lot_detail` error: 해당 lot이 DB에 없음. 다른 lot_id 요청.
- `check_optimal_design`의 `fully_satisfied_versions`가 빈 리스트: 부족인자 목록 표시, 값 직접 입력 또는 다른 lot 교체 선택지 제시.
- `update_lot_reference` 후에도 remaining_부족인자 존재: 남은 인자 안내. 이미 충족된 버전이 있으면 부족인자 해결 없이도 시뮬레이션 진행 가능함을 안내.
