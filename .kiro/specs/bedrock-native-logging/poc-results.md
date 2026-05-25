# Wave 1 / Task 1.1 — Bedrock 매직 헤더 동작 검증 결과

**상태: ✅ PASS**

## 근거

### 1차 evidence — 본인 사전 검증 (claude-multiuser-sim 레포)

`/Users/jaebin/AWS/repositories/claude-multiuser-sim/`에서 별도 IAM Role 직접 사용 환경으로 5개 케이스 검증 완료. `ANTHROPIC_CUSTOM_HEADERS_GUIDE.md` §Verification 표 참조.

| # | 시나리오 | 결과 |
|---|---|---|
| 1 | user1 + team=blue, user=user1 | PASS |
| 2 | user2 + team=red, user=user2 | PASS |
| 3 | user3 (bearer token, no IAM role) + team=untagged | PASS |
| 4 | user1 + 240-char ASCII value | PASS |
| 5 | user2 + 16 keys (Bedrock 한도) + 두 번째 custom header | PASS |

### 2차 evidence — 본인 ccwb PoC 환경 (Cognito 흐름)

본 fork의 대상 환경(Cognito UP + 카카오 OIDC + STS AssumeRoleWithWebIdentity)에서 30분 burst 테스트 후 CloudWatch dashboard의 "Top Users by Token Usage" 위젯에 다음 두 라인 도달 확인:

- `anonymous@example.com` — JWT email claim 갱신 전 호출 분량 (Cognito UP 사용자 attribute에 email 박히기 전)
- `wnwoqls2@naver.com` — JWT email claim 갱신 후 호출 분량

두 번째 케이스가 Cognito 흐름에서도 `requestMetadata`가 정상 도달함을 직접 보여준다.

## 결론

- 매직 헤더 메커니즘은 IAM 직접 흐름과 Cognito federation 흐름 모두에서 동일하게 작동.
- AWS 제약(16-key, 256-char, ASCII)은 사전 sanitize 단계에서 반드시 enforcement 필요.
- Wave 2 진입 가능.

## 비고

자동 검증 스크립트 `poc/wave1-verify-magic-header.sh`는 후속에 회귀 테스트(task 5.5) 용도로 사용 예정. 본인이 직접 실행하지 않은 상태.
