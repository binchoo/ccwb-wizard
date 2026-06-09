# 조직원 관리 운영 가이드 (Operator Runbook)

Claude Code with Bedrock(CCWB)을 운영하면서 조직원이 들어오고, 바뀌고, 나갈 때
운영자가 무엇을 해야 하는지 정리한 문서입니다.

각 상황은 "이런 일이 생기면 → 이렇게 한다" 형태로 구성되어 있습니다.

---

## 상황 1. 새 조직원이 들어왔다

> "신입이 입사했다. Claude Code를 쓰게 해주고 싶다."

운영자가 할 일은 **인증 경로에 따라 다릅니다.**

**기존 회사 IdP(Okta/Azure AD 등)를 쓰는 경우 (경로 1, 3)**
- 별도 조치 불필요. 그 사람이 회사 IdP 계정만 있으면 됩니다.
- 배포 패키지(installer)만 전달하면, 본인이 설치하고 회사 계정으로 로그인합니다.

**CCWB 자체 계정을 쓰는 경우 (경로 2)**
- Cognito User Pool에 사용자를 추가하거나, 본인이 가입(sign-up)하도록 안내합니다.
- 가입 승인 정책(자동/수동)에 따라 승인 처리합니다.

**공통**
- 배포 패키지 전달: 위자드의 "배포 및 테스트 → Distribute"에서 생성한 다운로드 URL을 공유합니다.
- 신규 사용자는 받은 패키지로 `install.sh` 실행 후 첫 로그인하면 끝입니다.

---

## 상황 2. 조직원의 팀/부서가 바뀌었다

> "A씨가 영업팀에서 개발팀으로 이동했다. 대시보드 집계도 새 팀으로 잡혀야 한다."

이게 가장 주의가 필요한 상황입니다. **변경이 자동으로 반영되지 않습니다.**

**왜?**
attribution(대시보드의 user/team 구분)은 로그인할 때 받은 정보로 한 번 고정됩니다.
조직 정보를 시스템(IdP/Cognito)에서 바꿔도, 그 사람 노트북에는 **이전 정보가 그대로 남아있습니다.**

**운영자가 해야 할 일:**

1. **먼저 시스템에서 조직 정보를 변경합니다.**
   - 회사 IdP를 쓰면 → IdP에서 그 사람의 그룹/부서를 변경
   - CCWB 자체 계정이면 → Cognito User Pool에서 해당 사용자 속성/그룹 변경

2. **그 사용자에게 재로그인을 요청합니다.** (아래 안내를 전달)

   > 조직 정보가 변경되었습니다. 아래 한 명령을 터미널에서 실행한 뒤,
   > 브라우저 로그인을 완료하고 Claude Code를 재시작해 주세요.
   >
   > ```bash
   > ~/claude-code-with-bedrock/credential-process --profile <프로필이름> --refresh-identity
   > ```
   >
   > 이 명령은 캐시(STS + id_token)를 비우고 새로 로그인하여 바뀐 팀/부서
   > 클레임을 다시 받아오고, `~/.claude/settings.json`의 매직 헤더를 갱신합니다.
   > 완료되면 새 attribution(user/team/dept)을 요약해 보여줍니다. AWS 자격증명은
   > 화면에 출력하지 않습니다.

   <details>
   <summary>구버전(이 플래그가 없는 패키지)을 쓰는 경우</summary>

   ```bash
   ~/claude-code-with-bedrock/credential-process --profile <프로필이름> --clear-cache
   ~/claude-code-with-bedrock/credential-process --profile <프로필이름>
   ```
   </details>

3. **재로그인 후 Claude Code 재시작**까지 완료되면, 다음 사용량부터 새 팀으로 집계됩니다.

> **참고**: 재로그인을 안 하면, 그 사람의 캐시된 로그인이 만료될 때까지
> (최대 수 일~수십 일) 이전 팀 정보로 계속 집계될 수 있습니다.
> 정확한 집계가 중요하면 반드시 재로그인을 요청하세요.

---

## 상황 3. 조직원이 퇴사했다 / 접근을 즉시 막아야 한다

> "B씨가 퇴사했다. 더 이상 Bedrock을 못 쓰게 해야 한다."

**가장 확실하고 빠른 방법은 시스템(IdP/Cognito) 측에서 차단하는 것입니다.**
노트북에 남은 캐시는 운영자가 직접 지울 수 없으므로, **발급원에서 끊어야** 합니다.

**운영자가 해야 할 일:**

1. **IdP/Cognito에서 사용자를 비활성화하거나 삭제합니다.**
   - 회사 IdP → 계정 비활성화
   - Cognito User Pool → 사용자 비활성화(Disable) 또는 삭제

2. **사용자의 토큰을 강제 폐기(revoke)합니다.** (남은 로그인 세션 무효화)
   - Cognito 사용 시: 해당 사용자의 토큰을 revoke 하거나, 사용자를 비활성화하면 갱신이 막힙니다.

3. (선택) **IAM 역할 신뢰 관계를 점검합니다.** 특정 사용자만이 아니라 전체를 막아야 하는
   비상 상황이면, 위자드로 배포한 인증 스택의 IAM 역할을 일시 비활성화할 수 있습니다.

> **중요**: 이미 발급된 임시 자격증명은 만료(최대 8~12시간) 전까지 유효합니다.
> 즉각적인 완전 차단이 필요하면, 발급원 차단(1~2단계)과 함께
> 만료 시간을 고려해 모니터링하세요.

---

## 상황 4. 누가 얼마나 쓰는지 확인하고 싶다

> "이번 달 팀별/사용자별 사용량을 보고 싶다."

- CloudWatch 대시보드(`<스택이름>-dashboard`)에서 사용자/팀/모델별 토큰 사용량을 확인합니다.
- 집계 기준은 상황 2에서 설명한 attribution(user/team) 정보입니다.
- 팀 이동이 잦은 조직이라면, 상황 2의 재로그인 안내를 주기적으로 병행하는 것이 정확도에 좋습니다.

---

## 상황 5. 사용량 한도를 관리하고 싶다

> "특정 사용자/팀이 너무 많이 쓴다. 한도를 걸고 싶다."

- 위자드의 "로깅 & 할당량" 단계에서 기본 한도(월/일)를 설정합니다.
- 세분화(사용자/그룹별 별도 한도)가 필요하면 Fine-grained Quotas를 활성화합니다.
- 한도 초과 시 동작(알림만 / 차단)을 정책으로 선택합니다.
  - 알림: SNS로 운영자에게 통지
  - 차단: 한도 초과 사용자는 다음 자격증명 발급이 막힘

---

## 핵심 요약

| 상황 | 운영자 액션 | 사용자 액션 필요? |
|------|-----------|-----------------|
| 새 조직원 | (자체 계정이면) 계정 생성 + 패키지 전달 | 설치 + 첫 로그인 |
| 팀/부서 변경 | 시스템에서 조직 정보 변경 + 재로그인 요청 | **`--refresh-identity` 실행 + Claude 재시작 필수** |
| 퇴사/차단 | IdP/Cognito에서 비활성화 + 토큰 폐기 | 없음 |
| 사용량 확인 | CloudWatch 대시보드 조회 | 없음 |
| 한도 관리 | 위자드에서 quota 설정 | 없음 |

> **가장 자주 놓치는 것**: 조직 정보(팀/부서)를 시스템에서 바꾼 뒤
> **사용자 재로그인을 요청하지 않으면**, 노트북에는 이전 정보가 남아
> 대시보드 집계가 틀어집니다. 변경 시 항상 재로그인을 안내하세요.

---

## 참고. `~/.claude/settings.json` env 레퍼런스

설치 시 `~/.claude/settings.json`의 `env` 블록에 들어가는 키들의 의미입니다.
JSON에는 주석을 달 수 없어 여기에 정리합니다.

| 키 | 값 | 설명 |
|----|-----|------|
| `AWS_PROFILE` | 프로파일명 | AWS SDK가 `~/.aws/config`의 `[profile <name>]`을 찾고, 거기 걸린 `credential_process`로 자격증명을 발급받게 함 |
| `AWS_REGION` | 예: us-east-1 | Bedrock 호출 리전 |
| `CLAUDE_CODE_USE_BEDROCK` | `1` | 모델 접근을 Amazon Bedrock 경로로 라우팅 |
| `CLAUDE_CODE_USE_MANTLE` | `0` | Mantle(Anthropic 게이트웨이 경유 대체 라우팅)을 명시적으로 비활성화. 본 배포는 Bedrock 경로만 쓰므로, 사용자/전역 환경에 `CLAUDE_CODE_USE_MANTLE=1`이 섞여 들어와 Bedrock 라우팅과 경합하는 것을 막기 위해 `0`으로 고정 |
| `ANTHROPIC_CUSTOM_HEADERS` | 매직 헤더 | credential-process가 인증 때마다 `X-Amzn-Bedrock-Request-Metadata: {...}`로 갱신. 설치 직후엔 `__ANTHROPIC_CUSTOM_HEADERS__` 플레이스홀더이며 첫 인증 시 실제 값으로 치환됨 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | 모델 ID | Sonnet 티어 기본 모델 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 모델 ID | Haiku 티어 기본 모델 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | 모델 ID | Opus 티어 기본 모델 |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | `0`/`1` | CC 텔레메트리 on/off |

> **참고**: 과거 템플릿에 있던 `ANTHROPIC_MODEL`은 `ANTHROPIC_DEFAULT_SONNET_MODEL`과
> 값이 중복(둘 다 sonnet)되어 제거했습니다. 티어별 키
> (`ANTHROPIC_DEFAULT_{SONNET,HAIKU,OPUS}_MODEL`)로 일관되게 관리합니다.
