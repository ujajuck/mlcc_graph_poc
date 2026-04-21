# 예시: 신뢰성 시뮬레이션 / 자율 반복 / 복합 요청

신뢰성 시뮬레이션 단독 실행, 여러 조건 비교, 자율 반복 최적화 관련 예시.

---

## 신뢰성 시뮬레이션

### Example 8

`ref lot 기준값 그대로 신뢰성 시뮬레이션 돌려봐.`

기대 동작:

- **먼저** 시험 전압과 온도를 사용자에게 확인 (halt_voltage, halt_temperature). 전압은 스펙전압 대비 배수(예: 1.5Vr) 또는 절대 전압(예: 6.3V)으로 받고, 온도는 °C로 받는다.
- `check_optimal_design`의 `ref_values`에서 설계값 가져옴
- `reliability_simulation` 호출 (params는 **scalar**, list가 아님)
- 시험 조건과 함께 통과확률 제시

### Example 9

`3번 후보로 신뢰성 돌려봐.`

기대 동작:

- 최신 optimal_design top 5의 3번 후보 `design` dict에서 설계값 추출
- `reliability_simulation` 호출
- 통과확률 제시

### Example 10

`cover_sheet_thk를 28, 30, 32로 바꿔가면서 신뢰성 비교해줘. 나머지는 3번 후보 기준.`

기대 동작:

- 3번 후보의 설계값을 base로 사용
- cover_sheet_thk만 3가지로 바꿔서 `reliability_simulation` 3번 호출
- 비교 테이블 제시

---

## 자율 반복 / 복합 요청

### Example 11

`너가 알아서 설계값 다르게 넣으면서 신뢰성 여러번 돌려보고 제일 좋은값 도출되면 나한테 추천해줘.`

기대 동작:

1. 탐색 전략 수립 후 사용자에게 공유
   - "핵심 파라미터(cover_sheet_thk, screen_mrgn_leng)를 축으로 5~6가지 조합을 시도하겠습니다. 진행할까요?"
2. 사용자 OK 후 `reliability_simulation` 반복 호출
3. 중간 진행 상황 보고
4. 비교 테이블 + 최종 추천 (근거 포함)

### Example 12

`신뢰성이 좋은애들중에 최적설계 돌려보고 그중에 용량 제일 높게 나오는 설계를 골라줘.`

기대 동작:

1. 탐색 전략 공유
   - "먼저 여러 설계 조건으로 신뢰성을 확인하고, 통과확률이 높은 조건의 범위로 최적설계 DOE를 돌리겠습니다."
2. `reliability_simulation` 여러 번 → 통과확률 기준 필터
3. 통과 조건을 params 범위로 삼아 `optimal_design` 실행
4. top 5 중 용량 최대 후보 추천

### Example 13

`top 5 후보 전부 신뢰성 돌려보고 비교해줘.`

기대 동작:

- 최신 top 5 각각에 `reliability_simulation` 호출 (5번)
- 비교 테이블 제시:

```
| 후보 | cast_dsgn_thk | cover_sheet_thk | active_layer | 예측용량 | 신뢰성 통과확률 |
|---|---|---|---|---|---|
| 1 | 5.0 | 30 | 162 | 10.12uF | 0.87 |
| 2 | 5.2 | 28 | 158 | 10.05uF | 0.91 |
| 3 | 4.8 | 32 | 166 | 10.21uF | 0.82 |
| 4 | 5.1 | 30 | 160 | 9.94uF | 0.85 |
| 5 | 5.3 | 25 | 155 | 9.88uF | 0.78 |
```

---

## Full Response Example — 자율 반복 신뢰성 최적 탐색

User prompt:

`top 5 전부 신뢰성 돌려보고 제일 좋은거 추천해줘.`

---

**탐색 전략**

top 5 후보 각각에 `reliability_simulation`을 실행해 통과확률을 비교하겠습니다.

**[1/5]** 후보 1 (cast_dsgn_thk=5.0, cover_sheet_thk=30, active_layer=162) → 통과확률: 0.8723
**[2/5]** 후보 2 (cast_dsgn_thk=5.2, cover_sheet_thk=28, active_layer=158) → 통과확률: 0.9134
**[3/5]** 후보 3 (cast_dsgn_thk=4.8, cover_sheet_thk=32, active_layer=166) → 통과확률: 0.8201
**[4/5]** 후보 4 (cast_dsgn_thk=5.1, cover_sheet_thk=30, active_layer=160) → 통과확률: 0.8512
**[5/5]** 후보 5 (cast_dsgn_thk=5.3, cover_sheet_thk=25, active_layer=155) → 통과확률: 0.7834

**종합 비교:**

| 후보 | 예측용량 | 신뢰성 통과확률 | 공정표준 |
|---|---|---|---|
| 2 | 10.05uF | **0.9134** | ✅ |
| 1 | 10.12uF | 0.8723 | ✅ |
| 4 | 9.94uF | 0.8512 | ✅ |
| 3 | 10.21uF | 0.8201 | ✅ |
| 5 | 9.88uF | 0.7834 | ⚠️ cover_sheet_thk 하한 경계 |

**추천: 후보 2**
- 신뢰성 통과확률 91.3%로 가장 높음
- 용량도 target 대비 +0.05uF로 충분
- 공정검사표준 전 항목 부합

이 후보를 base로 추가 미세 조정하시겠습니까?
