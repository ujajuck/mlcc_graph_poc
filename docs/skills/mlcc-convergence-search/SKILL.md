---
name: mlcc-convergence-search
description: MLCC 자율 반복 최적화 및 수렴 탐색 스킬. 사용자가 `알아서 돌려보고 제일 좋은거 찾아줘`, `여러 조건 비교해줘`, `신뢰성 좋은 설계 찾아줘`, `타겟 맞추면서 신뢰성도 확보해줘`, `둘 다 만족하는 설계 찾아줘` 같은 요청을 할 때 사용한다. optimal_design과 reliability_simulation을 자율적으로 반복 호출하여 단일 목표 최적화(자율 반복) 또는 타겟+신뢰성 동시 만족(수렴 탐색)을 수행한다.
---

# MLCC 자율 반복 최적화 및 수렴 탐색

lot_id가 검증된 상태에서 optimal_design과 reliability_simulation을 반복 조합하여 최적 설계를 탐색한다. 단일 목표 최적화(자율 반복 패턴 A~D)와 타겟+신뢰성 동시 만족(수렴 탐색 4-Phase) 두 가지 모드를 지원한다.

## 사전 조건

이 스킬은 `mlcc-lot-validation`에서 lot_id 검증이 완료된 상태를 전제로 한다.
- **lot_id 없이 이 스킬을 시작하면 안 된다.** 먼저 mlcc-lot-validation을 실행한다.
- 세션 상태에 lot_id가 없으면 사용자에게 lot_id를 요청하거나 mlcc-lot-validation부터 진행하도록 안내한다.

## 세션 상태 읽기/쓰기

> 필드 정의와 타입/단위는 `../session-state.md`를 참고한다.

**읽는 필드**:
- `lot_id` ← mlcc-lot-validation 출력
- `chip_prod_id` — 선택적
- `targets` — 이미 수집된 경우 재사용
- `params` / `top_candidates` — 이미 있으면 재사용

**쓰는 필드**:
- `targets` — 수렴 탐색 시 사용자로부터 수집
- `params`, `top_candidates` — 시뮬레이션 결과 기록
- `halt_voltage`, `halt_temperature` — 사용자 확인 후 기록, 세션 내 유지
- `final_design` — 사용자가 후보를 확정하면 기록 → mlcc-design-dispatch가 읽음

**상태 초기화 규칙**: 새 lot_id가 들어오면 targets, params, top_candidates를 초기화한다. halt 조건은 유지한다.

## 패턴 선택

| 요청 유형 | 패턴 |
|---|---|
| "알아서 신뢰성 좋은 설계 찾아줘" | **자율 반복 패턴** → `pattern-autonomous.md` |
| "여러 조건 바꿔보면서 비교해줘" | **자율 반복 패턴** → `pattern-autonomous.md` |
| "신뢰성 좋은 것 중에 최적설계 돌려줘" | **자율 반복 패턴** (체이닝) → `pattern-autonomous.md` |
| "타겟 맞추면서 신뢰성도 확보해줘" | **수렴 탐색 패턴** → `pattern-convergence.md` |
| "둘 다 만족하는 설계 찾아줘" | **수렴 탐색 패턴** → `pattern-convergence.md` |

**자율 반복**: 단일 목표 최적화 또는 단순 비교. 패턴 A~D 중 자유 선택.
**수렴 탐색**: 타겟 수치 + 신뢰성 기준 **동시** 만족 요구 시. 4-Phase 체계적 수렴.

## Tool 계약 요약

전체 계약은 `references/tool-contracts.md`에 있다.

- `optimal_design`의 params는 **list**. `reliability_simulation`의 params는 **scalar**. 절대 혼동하지 마라.
- `halt_voltage/halt_temperature`: **기본값(5)을 쓰지 마라.** 사용자에게 반드시 한 번 확인받아라.
- 여러 설계 조건 비교 시 `reliability_simulation`을 **여러 번** 호출한다.
- `search_rag`: 최종 추천 전 공정검사표준 검증에 사용한다.

## 실행 원칙

- tool 호출이 실패해도 즉시 포기하지 않는다. 파라미터 범위를 변경하거나 다른 접근을 시도한다.
- 한 번에 10회 이상 tool 호출이 필요한 탐색이면 사용자에게 범위를 먼저 확인한다.
- 탐색 전략은 시작 전 사용자에게 공유하고 컨펌을 받는다.
- **tool이 에러를 반환하면 성공한 것처럼 응답하지 마라.** 에러 원인을 파악하고 재실행하라.
- 세션 상태에 이미 기록된 값(lot_id, targets, halt 조건)은 다시 묻지 않는다.

## 보충 Reference 문서

- `references/tool-contracts.md`: optimal_design, reliability_simulation, search_rag 입출력 상세
- `references/pattern-autonomous.md`: 자율 반복 4가지 패턴(A~D), 탐색 전략 수립 및 보고 형식
- `references/pattern-convergence.md`: 수렴 탐색 4-Phase 방법론, 파라미터 조정 룰 테이블
- `references/examples-convergence.md`: 수렴 탐색 예시 (Examples 14-16)
- `references/examples-reliability.md`: 신뢰성 및 자율 반복 예시 (Examples 8-13)

## 실패 처리

- `optimal_design` 실행 실패: payload를 추측 수정하지 말고, 에러 메시지 기준으로 부족/잘못된 필드만 바로잡아 재시도한다.
- 수렴 탐색 Phase 3에서 3회 반복 후 미수렴: 중간 결과를 사용자에게 보고하고 타겟 완화 또는 범위 변경 협의.
- 타겟+신뢰성 상충이 명확해지면 즉시 사용자에게 trade-off를 보고하고 우선순위 협의.
- 시뮬레이션 결과가 기대에 못 미치면 파라미터 범위 변경 또는 다른 lot 전환을 제안한다.
