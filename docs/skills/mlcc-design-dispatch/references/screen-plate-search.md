# 스크린 동판 검색 가이드

## 개요

DOE/신뢰성 시뮬레이션 결과의 screen 관련 설계값을 기준으로, 현재 공정에서 사용 가능한 스크린 동판을 검색한다.

## Tool: search_screen_plate

### 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| `screen_chip_size_leng` | float | O | - | 스크린 칩 사이즈 길이 (um) |
| `screen_chip_size_widh` | float | O | - | 스크린 칩 사이즈 너비 (um) |
| `screen_mrgn_leng` | float | X | None | 스크린 마진 길이 (um) |
| `screen_mrgn_widh` | float | X | None | 스크린 마진 너비 (um) |
| `tolerance` | float | X | 5.0 | 허용 오차 (um, ±범위) |

### 설계값에서 파라미터 추출

DOE 결과의 top candidate 또는 사용자가 확정한 설계값에서 screen 관련 필드를 추출한다:

```
설계값 예시:
{
  "screen_chip_size_leng": 3200,
  "screen_chip_size_widh": 2500,
  "screen_mrgn_leng": 50,
  "screen_mrgn_widh": 40,
  ...
}

→ search_screen_plate(
    screen_chip_size_leng=3200,
    screen_chip_size_widh=2500,
    screen_mrgn_leng=50,
    screen_mrgn_widh=40
  )
```

### 결과 해석

- `status: success` + `row_count > 0` → 매칭 동판 존재. 동판 정보를 테이블로 제시.
- `status: no_match` → 해당 치수의 동판 없음. 사용자에게 신규 제작 필요 안내.

### 결과 제시 형식

```
| 동판 ID | 길이(um) | 너비(um) | 마진L(um) | 마진W(um) | 상태 |
|---------|---------|---------|----------|----------|------|
| SP-2024-001 | 3200 | 2500 | 50 | 40 | 사용중 |
```

### 매칭 동판이 없을 때

1. 허용 오차를 넓혀서 재검색을 제안할 수 있다 (예: tolerance=10)
2. "해당 치수의 스크린 동판이 없습니다. 신규 제작이 필요할 수 있습니다." 안내
3. 사용자에게 그래도 투입을 진행할지 확인

### search_query_database로 추가 검색

기본 tool로 충분하지 않은 경우, `search_query_database`로 자유 SQL 쿼리를 실행할 수 있다:

```sql
-- 예: 특정 spec_name 패턴의 동판 검색
SELECT *
FROM public.screen_plate_master
WHERE screen_durable_spec_name ILIKE '%특정패턴%'
  AND plate_status = '사용중'
```

> **주의**: 실제 테이블명은 운영 환경에 따라 다를 수 있다.
