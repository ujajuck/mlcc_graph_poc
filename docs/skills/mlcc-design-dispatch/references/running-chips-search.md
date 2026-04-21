# 실제 칩 정보 검색 가이드

## 개요

최종 설계값과 유사한 조건으로 현재 공정에서 실제 생산 중인 칩들의 정보를 검색한다. 투입 전 생산 실적 확인 및 참고 용도이다.

## Tool: search_running_chips

### 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `chip_prod_id` | str | X | None | chip_prod_id 패턴 (ILIKE, '%' 와일드카드) |
| `active_layer` | int | X | None | 적층수 기준값 |
| `cast_dsgn_thk` | float | X | None | cast 설계 두께 (um) |
| `electrode_c_avg` | float | X | None | 전극 C 평균값 |
| `tolerance_pct` | float | X | 10.0 | 수치 매칭 허용 오차 (%) |

하나 이상의 파라미터를 지정해야 한다.

### 검색 전략

**chip_prod_id 기반 검색** — 특정 기종의 현재 생산 상황을 파악할 때:
```
search_running_chips(chip_prod_id="CL32A106%")
```

**설계 파라미터 기반 검색** — DOE 결과와 유사한 조건의 칩을 찾을 때:
```
search_running_chips(
    active_layer=158,
    cast_dsgn_thk=4.8,
    electrode_c_avg=10.5,
    tolerance_pct=10.0
)
```

**복합 검색** — chip_prod_id + 설계값 동시 조건:
```
search_running_chips(
    chip_prod_id="CL32%",
    active_layer=158,
    cast_dsgn_thk=4.8
)
```

### 결과 제시 형식

```
| chip_prod_id | lot_id | 라인 | 공정 | 적층수 | cast두께 | 전극C | 날짜 |
|-------------|--------|------|------|--------|---------|-------|------|
| CL32A106KOY8NNE | BK8ST35 | LINE-A3 | 적층 | 158 | 4.8 | 10.5 | 2025-03-20 |
```

### 결과가 없을 때

- "현재 해당 조건으로 흐르고 있는 칩이 없습니다."
- 허용 오차(tolerance_pct)를 넓혀서 재검색 제안 가능
- 칩 검색 결과 없음이 투입을 차단하지는 않음 — 사용자에게 안내 후 판단을 맡긴다
