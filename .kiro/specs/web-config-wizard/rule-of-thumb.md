# Rule of Thumb — web-config-wizard

> 본 문서는 운영자 첨부 아키텍처 다이어그램(2026-05-25)에서 도출한 운영 원칙이다. 코드/문서 작업 시 이 원칙을 먼저 본다. 변경하려면 운영자에게 가볍게라도 한 마디 ping.
>
> 정본 이미지: `diagrams/architecture-original.png` (운영자가 직접 보존).

## 큰 그림

다이어그램이 표현하는 6개 영역만 본 spec이 다룬다. 그 외는 다른 spec.

```
Workforce  : 사용자 머신 (Claude Code + credential-process + settings.json + ~/.aws/config)
Auth       : 외부 OIDC IdP → IAM Direct Federation
Quota      : API Gateway → Lambda → DynamoDB
Monitoring : Bedrock invocation logging → CW Logs / S3
Deployment : zip → S3 + (Pre-signed URL | Self-service Landing Page)
Admin      : 위자드 (web)
```

## 1. IdP는 기존 5종만

Okta, Auth0, Cognito User Pool, Generic OIDC, Azure AD. 끝. 새 IdP(예: Salesforce)는 본 spec 범위 밖이며, 추가하려면 운영자 승인 필요.

> 다이어그램의 "External OIDC Providers" 박스는 예시 로고일 뿐, 카탈로그가 아니다.

## 2. Federation은 IAM Direct만

Federation 백본은 단 하나, **AWS IAM Direct (`AssumeRoleWithWebIdentity`)**. 그 앞단의 OIDC IdP 백엔드는 다양한데, 이게 §1의 5종이다. Cognito User Pool은 IdP 백엔드 옵션 중 하나일 뿐 (별도 federation path가 아니다).

코드상 의미:
- `config.federation_type` 같은 분기 필드는 **두지 않는다**. 단일 경로니 분기가 무의미.
- credential-process의 `AssumeRoleWithWebIdentity` 호출은 보존.
- (참고) AWS SSO / IAM Identity Center도 OIDC IdP 후보가 될 수 있다는 사실만 인지. 본 spec에는 미반영.

## 3. Bedrock Logging은 bit flag

destination을 비트로 표현:

| 값 | CW Logs | S3 | 비고 |
|---|---|---|---|
| `01` (`s3`) | × | ○ | Athena historical analysis만 필요할 때 |
| `10` (`cwlogs`) | ○ | × | 기본. Metric filter + Quota Lambda가 사용 |
| `11` (`both`) | ○ | ○ | 양쪽 다 |

`00`은 무효 (logging이 비활성이면 quota도 사용자 attribution도 깨짐).

CFN 파라미터 `BedrockLoggingDestination`의 기존 `cloudwatch`/`s3`/`both` 값 그대로 매핑. 위자드 UI에서는 두 체크박스(CW Logs / S3)로 노출하고, 둘 다 끄면 차단.

## 4. Mantle API 미지원

Claude Code의 Mantle/Responses API endpoint는 본 프로젝트 지원범위 밖이다. settings.json에 `CLAUDE_CODE_USE_MANTLE=0`을 항상 명시 주입한다. 운영자에게 옵션으로 노출하지 않는다.

이유: Mantle은 Bedrock model invocation logging을 발생시키지 않아 quota/attribution이 깨진다.

## 5. Distribution은 두 갈래

| 선택지 | CFN |
|--------|-----|
| Pre-signed URL | `presigned-s3-distribution.yaml` |
| Self-service Landing Page | `landing-page-distribution.yaml` |

위자드는 둘 중 하나(또는 disabled) 선택을 받는다. 둘을 동시 사용하지는 않는다.

## 6. CLI 명령 보존 안 함

다이어그램의 `> ccwb package` `> ccwb distribute` 콘솔 표시는 표현상 흔적이고 보존 대상이 아니다. **모든 운영자 인터페이스는 web 위자드**. zip 빌드/배포도 위자드의 마지막 단계로 통합하거나 별도 spec에서 다룬다.

기존 `source/claude_code_with_bedrock/` CLI 코드는 통째 폐기.

## 7. settings.json env 키 동결

다음 키 외에는 추가하지 않는다:

| 키 | 값 출처 |
|----|--------|
| `AWS_REGION` | Config.source_region |
| `AWS_PROFILE` | "ClaudeCode" 고정 |
| `ANTHROPIC_MODEL` | Config.model_id (또는 inference profile별 ARN) |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | 운영자 토글, 기본 `0` |
| `ANTHROPIC_CUSTOM_HEADERS` | install 시점 credential-process가 생성한 매직 헤더 (placeholder 치환) |
| `CLAUDE_CODE_USE_MANTLE` | "0" 고정 (§4) |

OTEL 류 키는 절대 안 들어간다.

## 8. accessToken 캐시는 OS keyring

credential-process가 OIDC 인증 결과를 캐시한다. 위치는 OS keyring 우선, keyring 미지원 환경에서는 `~/.ccwb/cache/<profile>/tokens.json` fallback.

## 9. 새 옵션 추가 절차

본 문서 §1~§8 범위를 벗어나는 옵션을 추가하려면:

1. 운영자에게 가볍게 ping (한 줄로 충분)
2. 본 문서 + scenarios.md를 동시 PR로 갱신
3. 코드 변경은 그 후

## 10. 충돌 났을 때

`이미지 > rule-of-thumb.md > scenarios.md > requirements/design/tasks.md` 순으로 우선. 위 셋과 코드가 어긋나면 코드를 고친다.
