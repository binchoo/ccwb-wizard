# Scenarios — web-config-wizard

> **상위 문서**: `rule-of-thumb.md` (운영 원칙).
> **위계**: 도메인 모델의 진실의 원천 (Source of Truth)
> **위계 스킵 사유**: 위자드 단계, 도메인 strategy 클래스, materialize() 매핑이 모두 본 문서를 1차 출처로 한다. requirements/design/tasks는 본 문서를 인용한다.

본 문서는 사용자에게 노출되는 모든 선택지(scenarios)와 그 선택이 만들어내는 산출물(CFN parameters, settings.json env, ~/.aws/config 섹션)의 매핑을 한 곳에 모은 카탈로그다. UI/CLI/agent가 모두 이 한 파일을 참조하므로 변경 시 PR에서 명확히 추적된다.

## 위계 결정

| 결정 | 채택안 | 근거 |
|------|-------|------|
| 진실의 원천 형식 | 본 문서(.md) — 사람이 읽고, 도메인 코드가 import하는 매핑 데이터는 별도 Python 모듈 | 사람의 검토 가능성과 코드 import 가능성을 모두 만족 |
| 데이터 형식 | 사람이 읽는 표 + Python literal export | YAML은 union type 표현이 빈약하고 dataclass와의 distance가 큼 |
| 변경 추적 | 본 문서 변경 = scenario 카탈로그 변경 → PR 리뷰 필수 | 위자드 페이지/CFN 파라미터 매핑이 동시에 영향받음 |


## Top-level Config Schema

운영자가 한 번 작성하는 Config의 평탄한(flat) 스키마다. 위자드 각 페이지가 이 객체의 부분을 채운다.

```python
@dataclass
class Config:
    profile_name: str                     # 식별자, [a-zA-Z0-9-]{1,64}
    schema_version: str = "3.0"

    # Page 3 — AWS Infrastructure
    aws_region: str                       # 인프라 배포 region
    stack_base_name: str                  # 모든 스택의 prefix

    # Page 2 — Identity Provider (one of 5 strategies)
    provider: IdentityProvider            # 다형성, 아래 표 참조

    # Page 4 — Bedrock
    model_id: str                         # 예: us.anthropic.claude-sonnet-4-5-20250929-v1:0
    cross_region_profile: Literal["us", "europe", "apac", "global"]
    source_region: str                    # 모델/프로파일 조합으로 가용 region 제한
    inference_profiles: dict[str, str]    # tier → ARN, 예: {"opus": "arn:..."}

    # Page 5 — Bedrock Logging + Quota
    bedrock_logging: BedrockLogging       # destination + retention
    quota: Quota | None                   # None이면 비활성

    # Page 6 — Distribution
    distribution: Distribution | None     # None이면 비활성

    # Page 7 — Additional Features
    enable_codebuild_windows: bool
    enable_cowork_3p: bool

    # Page 8 — Tags
    tags: dict[str, str]
```

본 문서는 위 dataclass 자체를 정의하지 않는다 — `web/backend/domain/config.py`가 정의한다. 본 문서는 각 필드의 가능한 값(scenarios)을 인간 가독 형식으로 카탈로그한다.


## 1. Identity Providers (5종)

각 provider는 도메인의 `IdentityProvider` 추상 클래스를 구현하는 strategy다.

### 1.1 공통 인터페이스

| 메서드 | 반환 | 설명 |
|--------|------|------|
| `cfn_template_path()` | `Path` | 이 strategy가 사용할 CFN 템플릿 |
| `cfn_parameters()` | `dict[str, str]` | CFN ParameterKey → ParameterValue |
| `settings_env()` | `dict[str, str]` | settings.json env 블록에 추가될 키-값 |
| `aws_config_section()` | `str` | ~/.aws/config의 [profile ClaudeCode] 섹션 본문 |
| `wizard_inputs()` | `list[FormField]` | UI가 렌더할 입력 필드 메타데이터 |

### 1.2 Provider별 카탈로그

| Provider | CFN 템플릿 | 운영자 입력 | derived 또는 자동 |
|---------|-----------|-----------|----------------|
| **okta** | bedrock-auth-okta.yaml | `domain`, `client_id` | — |
| **azure** | bedrock-auth-azure.yaml | `tenant_id`, `client_id`, `auth_mode` | mode별 추가 분기 (1.3) |
| **cognito-pool** | bedrock-auth-cognito-pool.yaml | `user_pool_id`, `client_id`, `user_pool_domain` | GovCloud 도메인 자동 보정 |
| **auth0** | bedrock-auth-auth0.yaml | `domain`, `client_id` | — |
| **generic** | bedrock-auth-generic.yaml | `issuer_url`, `client_id` | `thumbprint` (TLS 자동 추출), `auth/token/jwks` (well-known discovery) |

### 1.3 Azure Auth Mode 서브분기

Azure provider만 운영자 머신 keyring/cert 의존을 가진다. CFN은 `bedrock-auth-azure.yaml` 동일.

| auth_mode | 운영자 입력 | 클라이언트 측 산출물 | CFN 영향 |
|-----------|-----------|------------------|---------|
| `public` | (없음) | settings.json만 | 없음 |
| `secret` | `client_secret` | OS keyring에 저장(`<profile>-client-secret`) | 없음 |
| `certificate` | `cert_pem_path`, `key_pem_path` | settings.json에 경로 기록 | 없음 |

> `client_secret`은 config.json/스키마 어디에도 저장하지 않는다. 웹 위자드 backend는 사용자 입력을 받아 즉시 OS keyring에 PUT하고 메모리에서 폐기한다.

### 1.4 Generic OIDC discovery 흐름

`generic` provider는 표준 well-known 엔드포인트(`<issuer>/.well-known/openid-configuration`)에서 `authorization_endpoint`, `token_endpoint`, `jwks_uri`를 자동 추출한다. 운영자에겐 확인/override 기회만 제공.

TLS thumbprint는 `jwks_uri`의 호스트로 TLS handshake → leaf certificate SHA-1을 계산해서 채운다. 실패 시 운영자가 직접 입력.


## 2. Federation: IAM Direct 단일 경로

본 spec의 federation 백본은 단 하나, **AWS IAM Direct (`AssumeRoleWithWebIdentity`)**다.
앞단의 OIDC IdP 백엔드가 §1의 5종 중 무엇인지에 따라 CFN 템플릿과 입력이 달라진다.

분기 필드(`federation_type` 류)는 두지 않는다 — 단일 경로이므로 무의미.

| CFN 영향 | 설명 |
|---------|------|
| 모든 IdP의 auth 스택 | `IAM::OIDCProvider` + `IAM::Role` (federated) 출력 |
| Cognito Identity Pool | 미사용 (다이어그램에서 federation 박스의 백본은 IAM이며, Cognito는 IdP 백엔드 옵션 중 하나) |
| max_session_duration | 43200 (12h) |

> 참고: AWS SSO / IAM Identity Center도 OIDC IdP 백엔드 후보가 될 수 있으나 본 spec 범위에는 포함하지 않는다.

## 3. Bedrock Models (모델 매트릭스)

모델 매트릭스는 외부 데이터로 별도 모듈(`web/shared/bedrock_models.py`)에 정의된다. 본 문서는 매트릭스의 형태만 명시한다.

```python
CLAUDE_MODELS = {
    "sonnet-4-5": {
        "name": "Claude Sonnet 4.5",
        "profiles": {
            "us":     {"model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                       "source_regions": ["us-east-1", "us-east-2", "us-west-2"],
                       "destination_regions": [...],
                       "description": "..."},
            "europe": {...},
            "apac":   {...},
            "global": {...},
        },
    },
    "opus-4": {...},
    "haiku-3-5": {...},
}
```

위자드 Page 4가 본 매트릭스를 읽어 모델 → profile → source_region 캐스케이드 선택을 표시한다.

선택 결과:

| Config 필드 | 채워지는 값 | 사용처 |
|-----------|-----------|------|
| `model_id` | profile 내 `model_id` | settings.json env `ANTHROPIC_MODEL` |
| `cross_region_profile` | "us"/"europe"/"apac"/"global" | 운영자 디버깅용 메타데이터 |
| `source_region` | `source_regions`에서 운영자가 고른 것 | settings.json env `AWS_REGION`, ~/.aws/config region |
| (derived) allowed_bedrock_regions | profile 내 `destination_regions` | auth 스택의 `AllowedBedrockRegions` 파라미터 |

### Application Inference Profiles (선택)

운영자가 직접 만든 inference profile ARN을 tier별로 주입 가능. 빈 값이면 무시.

```python
inference_profiles: dict[str, str] = {
    "opus":   "arn:aws:bedrock:...:application-inference-profile/...",
    "sonnet": "arn:aws:bedrock:...:application-inference-profile/...",
    "haiku":  "arn:aws:bedrock:...:application-inference-profile/...",
}
```

settings.json env에 `ANTHROPIC_*_MODEL_ARN` 형태로 주입. 빈 항목은 생략.


## 4. Bedrock Logging (필수)

CFN: `bedrock-logging.yaml` (이미 존재).

destination은 **bit flag** 패턴으로 두 sink의 조합을 표현한다.

| bits | 값 | CW Logs | S3 | 비고 |
|---|---|---|---|---|
| `01` | `s3` | × | ○ | Athena historical analysis만 필요할 때 |
| `10` | `cwlogs` | ○ | × | 기본. Metric filter + Quota Lambda 사용 |
| `11` | `both` | ○ | ○ | 양쪽 다 |

`00`은 무효 (sink 없으면 quota/attribution 깨짐). 위자드는 차단.

CFN 파라미터는 기존 `bedrock-logging.yaml`의 `BedrockLoggingDestination`이 받는 문자열 enum (`cloudwatch`/`s3`/`both`)을 그대로 사용. UI 표현(체크박스 두 개)과 매핑:

| CW Logs 체크 | S3 체크 | CFN 값 |
|-----|-----|-----|
| ✓ | × | `cloudwatch` |
| × | ✓ | `s3` |
| ✓ | ✓ | `both` |
| × | × | (차단) |

| 필드 | 입력값 | CFN 파라미터 | 비고 |
|------|-------|-------------|------|
| `destination` | bit flag (위 표) | `BedrockLoggingDestination` | 기본 `cloudwatch` (10) |
| `retention_days` | 1–3653, 정수 | `DataRetentionDays` | 기본 90 |
| (derived) profile_name | Config.profile_name | `ProfileName` | — |
| (derived) metric_namespace | "ClaudeCodeBedrock" | `MetricNamespace` | 고정값 |

운영자에게는 destination과 retention만 노출. metric_namespace는 dashboard와 logging이 같은 값을 써야 하므로 코드 상수로 고정.

## 5. Quota Monitoring (선택)

활성화 시에만 CFN: `quota-monitoring.yaml` 배포.

| 필드 | 입력값 | CFN 파라미터 | 비고 |
|------|-------|-------------|------|
| `monthly_token_limit` | 1M–1B | `MonthlyTokenLimit` | 사용자 입력 |
| `warning_80_pct` | derived (monthly × 0.8) | `WarningThreshold80` | 자동 |
| `warning_90_pct` | derived (monthly × 0.9) | `WarningThreshold90` | 자동 |
| `daily_token_limit` | 0–100M, 0이면 disable | `DailyTokenLimit` | 기본 monthly/30 × (1+burst%) |
| `burst_buffer_percent` | 5–25 | (derived 계산용, CFN 미전달) | 기본 10 |
| `daily_enforcement` | `alert` / `block` | `DailyEnforcementMode` | 기본 alert |
| `monthly_enforcement` | `alert` / `block` | `MonthlyEnforcementMode` | 기본 block |
| `enable_finegrained_quotas` | bool | `EnableFinegrainedQuotas` | 기본 false |
| (derived) oidc_issuer_url | provider별 issuer URL | `OidcIssuerUrl` | provider strategy가 결정 |
| (derived) oidc_client_id | provider별 client_id | `OidcClientId` | provider strategy가 결정 |

```python
@dataclass
class Quota:
    monthly_token_limit: int
    daily_token_limit: int  # 0 = disabled
    burst_buffer_percent: int = 10
    daily_enforcement: Literal["alert", "block"] = "alert"
    monthly_enforcement: Literal["alert", "block"] = "block"
    enable_finegrained_quotas: bool = False
```


## 6. Distribution (선택, 2종 중 1택)

### 6.1 PresignedS3

CFN: `presigned-s3-distribution.yaml`.

| 필드 | 입력값 | 비고 |
|------|-------|------|
| (없음) | — | 토글만, 활성화 시 자동 배포 |

운영자 입장에서 가장 단순한 옵션. zip 업로드 후 presigned URL을 출력하면 끝.

### 6.2 LandingPage

CFN: `landing-page-distribution.yaml`.

| 필드 | 입력값 | CFN 파라미터 | 비고 |
|------|-------|-------------|------|
| `vpc_id` | 운영자 선택 (백엔드가 EC2 DescribeVpcs로 목록 제공) | `VpcId` | 필수 |
| `public_subnets` | 최소 2 AZ | `PublicSubnetIds` | ALB용 |
| `private_subnets` | 최소 2 AZ | `PrivateSubnetIds` | Lambda용 |
| `idp_provider` | `okta`/`azure`/`auth0`/`cognito` | `IdPProvider` | 위자드 Page 2 결과와 별개. 웹 인증용 IdP |
| (provider별) IdP 설정 | 각 provider별 도메인/client_id/client_secret | `Okta*`/`Azure*`/`Auth0*`/`Cognito*` | secret은 Secrets Manager에 PUT 후 ARN만 CFN에 |
| `custom_domain` | FQDN | `CustomDomainName` | **필수**. ACM 인증서 사전 존재 |
| `hosted_zone_id` | Route53 zone | `HostedZoneId` | (선택) DNS 자동 구성 |

```python
@dataclass
class LandingPage:
    vpc_id: str
    public_subnets: list[str]
    private_subnets: list[str]
    idp_provider: Literal["okta", "azure", "auth0", "cognito"]
    idp_config: dict[str, str]            # provider별 키-값
    custom_domain: str
    hosted_zone_id: str | None = None

@dataclass
class PresignedS3:
    pass

Distribution = LandingPage | PresignedS3
```

#### Cognito IdP 자동 감지

`idp_provider="cognito"`일 때 backend가 `cognito-user-pool-setup` 스택을 검색하여 `UserPoolId`, `UserPoolDomain`, `DistributionWebClientId`, `DistributionWebClientSecretArn`을 자동 채운다. 운영자는 확인만.

## 7. Additional Features (토글)

| 필드 | 입력값 | CFN 영향 | 비고 |
|------|-------|---------|------|
| `enable_codebuild_windows` | bool | `codebuild-windows.yaml` 배포 여부 | Windows 바이너리 빌드용 |
| `enable_cowork_3p` | bool | 없음 | 패키징 시 Cowork MDM 설정 생성 여부 |

CodeBuild 활성화 시 추가 입력 없음. Cowork 3P는 클라이언트 측만 영향 (settings.json 다른 경로 추가).

## 8. Resource Tags

```python
tags: dict[str, str]   # 키 ≤ 128자, 값 ≤ 256자, "aws:" prefix 금지
```

모든 CFN 스택의 `Tags`로 일괄 전파.


## 9. Stack 명명 규칙

`stack_base_name`을 prefix로 사용해 모든 CFN 스택의 이름을 derive한다.

| 논리 스택 | CFN 스택 이름 | 조건 |
|---------|--------------|------|
| auth | `{base}-auth` | 항상 |
| bedrock-logging | `{base}-bedrock-logging` | 항상 |
| dashboard | `{base}-dashboard` | 항상 |
| quota | `{base}-quota` | quota_monitoring_enabled |
| distribution | `{base}-distribution` | distribution != None |
| codebuild | `{base}-codebuild` | enable_codebuild_windows |
| s3bucket | `{base}-s3` | 항상 (배포 산출물 보관) |

OTEL 스택(`{base}-monitoring`, `{base}-networking`, `{base}-analytics`)은 더 이상 생성/관리하지 않는다.

## 10. Materialize: Config → 산출물

`materialize(config) → DeploymentArtifacts`는 본 카탈로그의 모든 매핑을 한 곳에서 적용한다.

```python
@dataclass
class StackPlan:
    stack_name: str
    template_path: Path
    parameters: dict[str, str]
    capabilities: list[str]              # ["CAPABILITY_IAM", ...]

@dataclass
class DeploymentArtifacts:
    stacks: list[StackPlan]              # 의존성 순서로 정렬됨
    settings_json_template: dict         # __PLACEHOLDER__ 포함
    aws_config_template: str             # ~/.aws/config 본문
    keyring_writes: list[KeyringWrite]   # 운영자 머신에 PUT할 secret (azure secret 등)

def materialize(config: Config) -> DeploymentArtifacts: ...
```

UI/CLI/agent 모두 이 함수를 호출한다. 사용자가 보는 "Review" 페이지는 `DeploymentArtifacts`를 그대로 직렬화해 보여준다.

## 11. 변경 절차

1. 본 문서를 먼저 수정한다.
2. 영향받는 모듈을 찾는다 (보통 4곳: `domain/providers/*.py`, `domain/materialize.py`, `frontend/pages/*.tsx`, `tests/`).
3. 변경을 PR에 묶고 리뷰어가 본 문서의 diff부터 본다.

본 문서가 갱신되지 않은 채 코드만 바뀌면 위자드와 매핑이 어긋난다 — 이를 막기 위해 CI에 단위 테스트로 "본 문서 표 → Python literal" 동등성을 검증하는 항목을 둔다(상세는 design.md).
