# Reference LOT 선정 패턴

인접기종 chip_prod_id 목록에서 품질이 우수한 Reference LOT를 선정하는 패턴이다. DOE/신뢰성 시뮬레이션의 시작점이므로, `get_first_lot_detail` 호출 전에 수행한다.

## 워크플로우

1. 인접기종 chip_prod_id 목록 확보 (이전 단계에서 `search_query_database` 등으로 획득)
2. `find_ref_lot_candidate(chip_prod_id_list)` 호출 → 11개 품질지표 기반 상위 LOT 반환
3. 사용자에게 선정된 REF LOT 브리핑 (lot_id, 선정 근거)
4. 사용자 확인 후 → `get_first_lot_detail(lot_id)` 호출로 설계정보 로드

## find_ref_lot_candidate 파라미터

모든 파라미터는 선택적이며, 미지정 시 기본값이 적용된다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `chip_prod_id_list` | List[str] | **(필수)** | 인접기종 chip_prod_id 리스트 |
| `cutting_grade_filter` | List[str] | `['S 등급', 'A 등급', 'B 등급']` | 허용할 커팅 불량률 등급 |
| `measure_grade_filter` | List[str] | `['S 등급', 'A 등급', 'B 등급']` | 허용할 측정 불량률 등급 |
| `exclude_screen_codes` | List[str] | `['F','L','G','K','E']` | 제외할 screen_durable_spec_name 6번째 자리 코드 |
| `exclude_screen_types` | List[str] | `['3DJ','VLC','RHM','EXT','MPM','SHI']` | 제외할 screen_durable_spec_name 11~13자리 타입 |
| `require_reliability_pass` | bool | `True` | 신뢰성 시험(HALT/8585/BURN-IN/DF/ODB) 통과 필수 여부 |
| `top_k` | int | `20` | 반환할 상위 LOT 수 |

## 사용자 요청 → 파라미터 매핑 가이드

사용자의 자연어 요청을 파라미터로 변환하는 기준이다. 별도 언급이 없으면 기본값을 사용한다.

| 사용자 표현 | 파라미터 변환 |
|-------------|--------------|
| "S등급만", "불량률 최상위만" | `cutting_grade_filter=['S 등급']`, `measure_grade_filter=['S 등급']` |
| "S,A등급까지만", "B등급 제외" | `cutting_grade_filter=['S 등급', 'A 등급']`, `measure_grade_filter=['S 등급', 'A 등급']` |
| "신뢰성 NG 허용", "신뢰성 조건 완화" | `require_reliability_pass=False` |
| "후보 5개만", "top 5만" | `top_k=5` |
| "스크린 타입 제한 없이", "스크린 필터 풀어줘" | `exclude_screen_codes=[]`, `exclude_screen_types=[]` |
| "3DJ 타입도 포함" | 기본값에서 `'3DJ'`만 제거: `exclude_screen_types=['VLC','RHM','EXT','MPM','SHI']` |

## 결과가 없을 때

`find_ref_lot_candidate` 결과가 `status: fail`이면:

1. 먼저 사용자에게 결과 없음을 안내한다
2. 필터 완화를 제안한다:
   - 등급 범위 확대 (S등급만 → S,A,B등급)
   - 신뢰성 조건 완화 (`require_reliability_pass=False`)
   - 스크린 제외 조건 완화
3. 사용자 선택에 따라 파라미터를 조정하여 재호출한다

## 대화 예시

**기본 호출** (필터 미언급 시):
```
사용자: CL32A106KOY8NNE 인접기종에서 ref lot 찾아줘
→ find_ref_lot_candidate(chip_prod_id_list=[...]) (기본 필터 적용)
```

**필터 지정 호출**:
```
사용자: S등급 LOT만 골라줘, 신뢰성은 NG여도 괜찮아
→ find_ref_lot_candidate(
    chip_prod_id_list=[...],
    cutting_grade_filter=['S 등급'],
    measure_grade_filter=['S 등급'],
    require_reliability_pass=False
  )
```
