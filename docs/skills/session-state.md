# 세션 상태 스키마 (Session State Schema)

스킬 간 공유되는 모든 세션 상태 필드를 정의한다.  
각 SKILL.md의 "세션 상태" 섹션은 이 문서를 참조하며, 필드 정의/타입/단위를 인라인으로 중복 작성하지 않는다.

키 생성 함수: `mlcc_agent/state_keys.py`  
네임스페이스 접두사: `mlcc_design.*`

---

## 세션 식별자

| 필드 | 상태 키 | 타입 | 기록 스킬 |
|------|---------|------|----------|
| `chip_prod_id_list` | `mlcc_design.session.chip_prod_id_list` | `List[str]` | mlcc-rag-spec-selector |
| `active_lot_id` | `mlcc_design.session.active_lot_id` | `str` | mlcc-lot-validation |
| `active_chip_prod_id` | `mlcc_design.session.active_chip_prod_id` | `str` | mlcc-lot-validation |

---

## LOT 데이터 (lot_id 스코프)

| 필드 | 상태 키 | 타입 | 기록 tool |
|------|---------|------|----------|
| lot 상세 | `mlcc_design.lot.{lot_id}` | `dict` | `get_first_lot_detail` |
| 검증 결과 | `mlcc_design.validation.{lot_id}` | `dict` | `check_optimal_design` |

`mlcc_design.validation.{lot_id}` 구조:
```json
{
  "fully_satisfied_versions": ["ver1", "ver3"],
  "충족인자": {"ver1": {"cast_dsgn_thk": 4.8, "active_layer": 158}},
  "부족인자": {"ver2": ["ldn_avr_value", "cover_sheet_thk"], "ver4": ["gap_sheet_thk"]}
}
```

---

## DOE 설정 (lot_id 스코프)

| 필드 | 상태 키 | 타입 | 기록 스킬 |
|------|---------|------|----------|
| targets | `mlcc_design.targets.{lot_id}` | `dict[str, float]` | mlcc-optimal-design-doe |
| params | `mlcc_design.params.{lot_id}` | `dict[str, list]` | mlcc-optimal-design-doe |
| top_candidates | `mlcc_design.top_candidates.{lot_id}` | `List[dict]` | mlcc-optimal-design-doe |

**targets 5개 키**: `target_electrode_c_avg`(uF), `target_grinding_l_avg`(um), `target_grinding_w_avg`(um), `target_grinding_t_avg`(um), `target_dc_cap`(uF)

**params 10개 키**: `active_layer`, `ldn_avr_value`, `cast_dsgn_thk`, `screen_chip_size_leng`, `screen_mrgn_leng`, `screen_chip_size_widh`, `screen_mrgn_widh`, `cover_sheet_thk`, `total_cover_layer_num`, `gap_sheet_thk`

---

## 신뢰성 설정 (세션 전체 스코프)

| 필드 | 상태 키 | 타입 | 기록 스킬 |
|------|---------|------|----------|
| halt_conditions | `mlcc_design.halt_conditions` | `{halt_voltage: float, halt_temperature: float}` | mlcc-optimal-design-doe / mlcc-convergence-search |

> lot_id가 변경되어도 이 값은 유지된다. 세션 중 한 번만 사용자에게 확인하면 된다.

---

## 최종 설계 (lot_id 스코프)

| 필드 | 상태 키 | 타입 | 기록 스킬 |
|------|---------|------|----------|
| final_design | `mlcc_design.final_design.{lot_id}` | `dict` | mlcc-optimal-design-doe / mlcc-convergence-search |

`mlcc_design.final_design.{lot_id}` 필드: `chip_prod_id`, `lot_id`, `active_layer`, `cast_dsgn_thk`, `electrode_c_avg`, `ldn_avr_value`, `screen_chip_size_leng`, `screen_chip_size_widh`, `screen_mrgn_leng`, `screen_mrgn_widh`, `cover_sheet_thk`

---

## 상태 초기화 규칙

| 이벤트 | 초기화 대상 | 유지 대상 |
|--------|------------|----------|
| 새 lot_id 진입 | `targets.{이전}`, `params.{이전}`, `top_candidates.{이전}`, `final_design.{이전}` | `halt_conditions`, `session.*`, `lot.*`, `validation.*` |
| 사용자가 후보 재선택 | `final_design.{lot_id}` | 나머지 전체 |

---

## 상태 관측 패턴 (스킬 진입 시 체크리스트)

스킬이 활성화되면 아래 순서로 현재 상태를 확인하고 다음 행동을 결정한다.  
**이미 있는 값은 사용자에게 재확인하지 않고 재사용한다.**

```
1. mlcc_design.session.active_lot_id 있는가?
   └─ 없음 → mlcc-lot-validation 실행 필요

2. mlcc_design.validation.{lot_id}.fully_satisfied_versions 비어있지 않은가?
   └─ 비어있음 → mlcc-lot-validation 실행 필요 (부족인자 보충 또는 다른 lot)

3. mlcc_design.targets.{lot_id} 있는가?
   └─ 없음 → 사용자에게 targets 5개 수집 (빠진 것만)

4. mlcc_design.top_candidates.{lot_id} 있는가?
   └─ 있음 → 이미 실행된 DOE 결과 재사용 가능

5. mlcc_design.halt_conditions 있는가?
   └─ 있음 → 신뢰성 halt 조건 재확인 불필요

6. mlcc_design.final_design.{lot_id} 있는가?
   └─ 있음 → mlcc-design-dispatch 준비 완료
```
