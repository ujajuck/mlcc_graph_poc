# 패턴: LOT 검증 + 부족인자 보충

이 패턴은 모든 시뮬레이션의 시작점이다. lot_id를 검증하고, 부족인자가 있으면 사용자로부터 값을 받아 채운다.

## 흐름

### 1. lot_id 확보

사용자가 lot_id를 제공하지 않았으면 먼저 요청한다.

### 2. get_first_lot_detail 실행 (설계정보 로드)

lot_id가 확보되면 가장 먼저 `get_first_lot_detail`을 호출하여 해당 lot의 설계정보를 DB에서 조회하고 세션 state에 저장한다.

```
get_first_lot_detail(lot_id="AKB45A2")
```

- `status: "success"` → ref lot 설계정보가 state에 저장됨. 다음 단계로 진행.
- `status: "error"` → DB에 해당 lot이 없음. 사용자에게 다른 lot_id를 요청한다.

### 3. check_optimal_design 실행

```
check_optimal_design(lot_id="AKB45A2")
```

반환 예시:
```json
{
  "status": "success",
  "lot_id": "AKB45A2",
  "fully_satisfied_versions": ["ver1", "ver3"],
  "partially_missing_versions": {
    "ver2": ["ldn_avr_value", "cover_sheet_thk"],
    "ver4": ["gap_sheet_thk", "screen_mrgn_widh"]
  },
  "충족인자": {"ver1": {"cast_dsgn_thk": 4.8, "active_layer": 158, ...}, ...},
  "부족인자": {"ver1": [], "ver2": ["ldn_avr_value", "cover_sheet_thk"], ...}
}
```

### 4. 결과 해석

ver1~ver4는 각각 다른 종류의 시뮬레이션이다. **한 개 이상의 버전이 부족인자 없이 완전하면(`fully_satisfied_versions`가 비어있지 않으면) 해당 버전으로 시뮬레이션을 진행할 수 있다.**

**`fully_satisfied_versions`가 있으면 (status: success)**:
- 충족된 버전으로 바로 시뮬레이션 진행 가능. 다음 스킬(mlcc-optimal-design-doe 또는 mlcc-convergence-search)로 넘어간다.
- 나머지 버전의 부족인자는 참고 정보로 사용자에게 안내한다.
- 사용자가 원하면 부족인자를 채워서 추가 버전도 활성화할 수 있다.

**모든 버전에 부족인자가 있으면 (status: warning)**:
- 사용자에게 두 가지 선택지를 제시한다: 값을 직접 제공하거나, 다른 lot_id로 교체.

응답 예시 (일부 버전 충족):

```
reference LOT AKB45A2 검증 결과:

✅ 시뮬레이션 진행 가능 버전: ver1, ver3
  - ver1 충족인자: cast_dsgn_thk=4.8um, active_layer=158EA, ...
  - ver3 충족인자: ...

⚠️ 추가 활성화 가능 버전 (부족인자 보충 필요):
  - ver2 부족: ldn_avr_value, cover_sheet_thk
  - ver4 부족: gap_sheet_thk, screen_mrgn_widh

ver1, ver3 기준으로 시뮬레이션을 진행할까요?
나머지 버전의 부족인자를 채우시면 해당 버전도 추가로 진행할 수 있습니다.
```

### 5. 부족인자 값 반영

사용자가 추가 버전 활성화를 원해서 값을 제공하면 `update_lot_reference`를 호출한다.

```
update_lot_reference(
  lot_id="AKB45A2",
  factors={"ldn_avr_value": 3.0, "cover_sheet_thk": 28, "gap_sheet_thk": 1.2, "screen_mrgn_widh": 55}
)
```

반환에서 `remaining_부족인자`가 줄어들면 추가 버전이 활성화된다.
이미 충족된 버전이 있으면 부족인자 보충을 기다리지 않고 바로 시뮬레이션을 진행할 수 있다.

### 6. 부분 입력 허용

사용자가 일부만 제공해도 된다. 예: "ldn_avr_value 3.0, cover_sheet_thk 28만 먼저 넣어줘"
→ 나머지(gap_sheet_thk, screen_mrgn_widh)는 다음 턴에 받으면 된다.

## 충족인자 값 활용

충족인자에 반환된 값은 이후 params 기본값 제안에 활용한다.
예: `check_optimal_design`이 `cast_dsgn_thk: 4.8`을 반환했으면, params 수집 시 "cast_dsgn_thk의 ref lot 값은 4.8um입니다. 이 값 기준으로 범위를 잡을까요?" 같은 제안이 가능하다.
