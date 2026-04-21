# 적층투입지시 절차

## 개요

최종 설계값으로 적층 공정에 투입 지시를 실행한다. **실제 생산 라인에 영향을 주는 행위**이므로, 반드시 사용자 최종 확인을 거쳐야 한다.

## Tool: dispatch_stacking_order

### 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `chip_prod_id` | str | O | 대상 chip_prod_id |
| `lot_id` | str | O | 대상 lot_id |
| `design_values` | dict | O | 최종 설계값 (아래 필수 필드 참조) |
| `user_confirmed` | bool | O | 사용자 확인 여부 (기본 False) |

### design_values 필수 필드

```json
{
  "active_layer": 158,
  "cast_dsgn_thk": 4.8,
  "electrode_c_avg": 10.5,
  "ldn_avr_value": 3.2,
  "screen_chip_size_leng": 3200,
  "screen_chip_size_widh": 2500,
  "screen_mrgn_leng": 50,
  "screen_mrgn_widh": 40,
  "cover_sheet_thk": 15.0
}
```

추가 필드(gap_sheet 등)가 있으면 함께 포함한다.

## 투입 확인 프로세스 (2-step)

### Step 1: 확인 요청

`user_confirmed=False`로 호출한다. tool이 설계값 요약을 반환하고 확인을 요청한다.

```
→ dispatch_stacking_order(
    chip_prod_id="CL32A106KOY8NNE",
    lot_id="BK8ST35",
    design_values={...},
    user_confirmed=False
  )
← status: "awaiting_confirmation" + 설계값 요약
```

사용자에게 보여줄 확인 메시지 형식:

```
다음 설계값으로 적층투입지시를 실행합니다.

  chip_prod_id: CL32A106KOY8NNE
  lot_id: BK8ST35

  [핵심 설계값]
  - 적층수: 158
  - Cast 두께: 4.8 um
  - 전극C 평균: 10.5
  - 스크린 길이/너비: 3200/2500 um
  - 스크린 마진 L/W: 50/40 um
  - 커버시트 두께: 15.0 um

투입을 진행하시겠습니까?
```

### Step 2: 실제 투입

사용자가 "예" / "확인" / "진행해줘" 등으로 승인하면, `user_confirmed=True`로 재호출한다.

```
→ dispatch_stacking_order(
    chip_prod_id="CL32A106KOY8NNE",
    lot_id="BK8ST35",
    design_values={...},
    user_confirmed=True
  )
← status: "success" + dispatch_id
```

사용자가 "아니오" / "취소" / "수정" 등으로 거부하면 투입하지 않고, 수정할 부분을 확인한다.

## 투입 전 체크리스트

투입지시 호출 전에 아래 사항을 확인하는 것을 권장한다 (필수는 아님):

1. **스크린 동판 존재 확인** (1단계) — 해당 치수의 동판이 있는지
2. **실제 칩 정보 확인** (2단계) — 유사 조건의 생산 실적이 있는지
3. **설계값 완전성** — 필수 필드가 모두 채워져 있는지

## 오류 처리

| 상황 | 대응 |
|------|------|
| 필수 필드 누락 | 누락 필드 목록 안내, 값 요청 |
| API 호출 실패 | 오류 메시지 전달, 재시도 안내 |
| 사용자 거부 | 투입 취소, 수정 사항 확인 |
| 네트워크 타임아웃 | 잠시 후 재시도 안내 |
