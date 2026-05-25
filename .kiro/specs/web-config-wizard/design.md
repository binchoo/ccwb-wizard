# Design — web-config-wizard

> **상위 문서**: `rule-of-thumb.md`, `requirements.md`, `scenarios.md`

## Overview

본 fork의 위자드를 다음 3-tier 구조로 갈아엎는다.

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Vite + React + TS)                                    │
│  Pages = 위자드 단계. 각 페이지는 strategy의 wizard_inputs()를   │
│  렌더하기만 함. 자체 분기 로직 없음.                             │
└──────────────────────────────────────────────────────────────────┘
                          ▲
                          │ HTTP (localhost:port)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI on 127.0.0.1)                                  │
│  - Config CRUD (~/.ccwb/profiles/*.json + draft)                 │
│  - AWS lookup (region/VPC/subnet/HostedZone/Cognito stack)       │
│  - OS keyring write                                              │
│  - Deploy/Package/Distribute trigger (선택, Phase 2)             │
└──────────────────────────────────────────────────────────────────┘
                          ▲
                          │ import
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  Domain (pure Python, 의존성 최소)                                │
│  - Config dataclass + schema_version                             │
│  - IdentityProvider / Distribution strategy classes              │
│  - bedrock_models.py (모델 매트릭스)                              │
│  - materialize(config) → DeploymentArtifacts                     │
│                                                                   │
│  Federation은 IAM Direct 단일 경로 — strategy 없음.              │
│  AI agent와 CLI도 이 모듈을 직접 import해 사용.                  │
└──────────────────────────────────────────────────────────────────┘
                          │
                          │ 변경 없음
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  Preserved (변경 금지)                                            │
│  - deployment/infrastructure/*.yaml                              │
│  - source/credential_provider/*.py                               │
│  - install.sh / install.bat (산출물 형식 동일)                   │
└──────────────────────────────────────────────────────────────────┘
```

핵심 결정:

| 결정 | 채택 | 근거 |
|------|------|------|
| 진실의 원천 | Config 텍스트 파일 (JSON) | UI/CLI/agent가 동등하게 read/write 가능 |
| Frontend | Vite + React + TS + yarn | 운영자 요청. 무거운 dep 없이 빠른 부팅 |
| Backend | FastAPI (Python) | boto3/keyring 의존성 자연스러움. CFN 템플릿이 어차피 Python 도메인에서 처리됨 |
| 분기 응집 | strategy 패턴 (IdP/Distribution) | scenarios.md의 카탈로그 ↔ 코드 1:1 매핑. Federation은 단일 경로라 strategy 없음 |
| 진행상태 저장 | backend draft 파일 (`<name>.draft.json`) + frontend localStorage 캐시 | UI close 후에도 같은 단계에서 재개. 다른 머신 이동은 지원 안 함 |
| 위자드 진입점 | `ccwb` 단일 명령 → FastAPI 실행 + 브라우저 자동 오픈 | 운영자 친화 |


## Architecture

### 디렉토리 구조

```
/web/
├── backend/                          # FastAPI app
│   ├── pyproject.toml
│   ├── ccwb_wizard/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app + uvicorn 진입점
│   │   ├── api/
│   │   │   ├── wizard.py             # POST /api/profile, GET /api/profile/{name}, ...
│   │   │   ├── aws_lookup.py         # GET /api/aws/regions, /vpcs, /subnets, /zones
│   │   │   ├── secret.py             # POST /api/secret/keyring (azure secret)
│   │   │   └── scenarios.py          # GET /api/scenarios (frontend가 사용할 카탈로그)
│   │   └── settings.py               # uvicorn host/port 설정
│   └── tests/
│
├── frontend/                         # Vite + React + TS
│   ├── package.json
│   ├── yarn.lock
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── pages/                    # 페이지 = 위자드 단계
│       │   ├── 0-Profile.tsx
│       │   ├── 1-Environment.tsx
│       │   ├── 2-Provider.tsx        # ProviderForm dispatch by provider type
│       │   ├── 3-Infra.tsx
│       │   ├── 4-Bedrock.tsx
│       │   ├── 5-LoggingQuota.tsx
│       │   ├── 6-Distribution.tsx
│       │   ├── 7-Features.tsx
│       │   ├── 8-Tags.tsx
│       │   └── 9-Review.tsx
│       ├── components/
│       │   ├── providers/            # 페이지 2의 IdP별 sub-form
│       │   │   ├── OktaForm.tsx
│       │   │   ├── AzureForm.tsx
│       │   │   ├── CognitoForm.tsx
│       │   │   ├── Auth0Form.tsx
│       │   │   └── GenericForm.tsx
│       │   ├── distribution/
│       │   │   ├── PresignedS3Form.tsx
│       │   │   └── LandingPageForm.tsx
│       │   └── common/
│       │       ├── FormField.tsx
│       │       ├── StepNav.tsx
│       │       └── ReviewTable.tsx
│       ├── store.ts                  # config draft state (zustand 또는 단순 useState)
│       └── api.ts                    # backend HTTP client
│
└── domain/                           # pure Python 도메인 (backend가 import)
    ├── pyproject.toml
    ├── ccwb_domain/
    │   ├── __init__.py
    │   ├── config.py                 # Config dataclass, schema_version, JSON IO
    │   ├── providers/
    │   │   ├── __init__.py           # registry: PROVIDERS = {"okta": OktaProvider, ...}
    │   │   ├── base.py               # IdentityProvider ABC
    │   │   ├── okta.py
    │   │   ├── azure.py
    │   │   ├── cognito.py
    │   │   ├── auth0.py
    │   │   └── generic.py
    │   ├── distribution.py           # PresignedS3 / LandingPage
    │   ├── bedrock_models.py         # 모델 매트릭스 (literal data)
    │   ├── materialize.py            # Config → DeploymentArtifacts
    │   └── secrets.py                # OS keyring 인터페이스
    └── tests/

/source/credential_provider/          # 변경 없음
/deployment/infrastructure/           # 변경 없음

/.kiro/specs/web-config-wizard/
├── scenarios.md                      # 진실의 원천 (카탈로그)
├── requirements.md
├── design.md                         # 본 문서
└── tasks.md
```

### 컴포넌트 책임

#### Domain (pure Python)

**Config (config.py)**: 운영자가 만든 설정의 영구 저장 형식. Top-level dataclass + JSON IO.

```python
@dataclass
class Config:
    profile_name: str
    schema_version: str
    aws_region: str
    stack_base_name: str
    provider: dict                    # { "type": "okta", "domain": "...", ... }
    model_id: str
    cross_region_profile: str
    source_region: str
    inference_profiles: dict[str, str]
    bedrock_logging: dict
    quota: dict | None
    distribution: dict | None
    enable_codebuild_windows: bool
    enable_cowork_3p: bool
    enable_cc_telemetry: bool             # CLAUDE_CODE_ENABLE_TELEMETRY (기본 false=0)
    tags: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "Config": ...
    def save(self, path: Path) -> None: ...
```

**provider 등은 dataclass가 아니라 dict**으로 직렬화한다. 이유: 다형성을 JSON에 1:1 표현하기 가장 단순하고, agent가 직접 편집하기 쉽다. 도메인 strategy 객체는 `provider_strategy(config.provider)` 식으로 dict에서 매번 인스턴스화한다 (상태 없으므로 비용 무시할 수준).

**IdentityProvider ABC (providers/base.py)**:

```python
class IdentityProvider(ABC):
    type: ClassVar[str]               # registry key, 예: "okta"

    @abstractmethod
    def cfn_template_path(self) -> Path: ...

    @abstractmethod
    def cfn_parameters(self, config: Config) -> dict[str, str]: ...

    @abstractmethod
    def settings_env(self, config: Config) -> dict[str, str]: ...

    @abstractmethod
    def aws_config_section(self, config: Config) -> str: ...

    @classmethod
    @abstractmethod
    def wizard_inputs(cls) -> list[FormField]:
        """위자드 페이지가 렌더할 입력 필드 메타데이터.
        FormField는 type/name/label/required/validator 등을 포함."""

    @classmethod
    def from_dict(cls, data: dict) -> "IdentityProvider":
        """JSON dict → strategy 인스턴스. registry가 'type' 키를 보고 dispatch."""
```

**Provider Registry**:

```python
# providers/__init__.py
PROVIDERS: dict[str, type[IdentityProvider]] = {}

def register(cls):
    PROVIDERS[cls.type] = cls
    return cls

@register
class OktaProvider(IdentityProvider):
    type = "okta"
    ...
```

frontend의 동적 form은 `GET /api/scenarios/providers`가 반환하는 `wizard_inputs()` 결과를 그대로 렌더한다.

**materialize.py**:

```python
def materialize(config: Config) -> DeploymentArtifacts:
    provider = provider_strategy(config.provider)
    distribution = distribution_strategy(config.distribution) if config.distribution else None

    stacks: list[StackPlan] = []

    # 1. auth (provider별 CFN, federation은 항상 IAM Direct)
    stacks.append(StackPlan(
        stack_name=f"{config.stack_base_name}-auth",
        template_path=provider.cfn_template_path(),
        parameters={
            **provider.cfn_parameters(config),
            "FederationType": "direct",                # rule-of-thumb §2 — 항상 direct
            "AllowedBedrockRegions": ",".join(allowed_regions_for(config)),
            "EnableMonitoring": "true",
        },
        capabilities=["CAPABILITY_NAMED_IAM"],
    ))

    # 2. bedrock-logging (항상)
    stacks.append(StackPlan(
        stack_name=f"{config.stack_base_name}-bedrock-logging",
        template_path=DEPLOYMENT / "bedrock-logging.yaml",
        parameters={
            "ProfileName": config.profile_name,
            "BedrockLoggingDestination": config.bedrock_logging["destination"],
            "DataRetentionDays": str(config.bedrock_logging["retention_days"]),
        },
    ))

    # 3. dashboard (항상)
    # 4. quota (옵션)
    # 5. distribution (옵션)
    # 6. codebuild (옵션)
    # 7. s3bucket (항상)

    settings_template = build_settings_template(config, provider)
    aws_config = build_aws_config(config, provider)
    keyring_writes = collect_keyring_writes(config, provider)

    return DeploymentArtifacts(
        stacks=order_by_dependency(stacks),
        settings_json_template=settings_template,
        aws_config_template=aws_config,
        keyring_writes=keyring_writes,
    )
```

#### Backend (FastAPI)

API 엔드포인트:

| Method | Path | 책임 |
|--------|------|------|
| `GET` | `/api/scenarios` | scenarios.md의 카탈로그 데이터 (provider list, distribution types, etc.) |
| `GET` | `/api/profile` | 모든 profile 이름 목록 |
| `GET` | `/api/profile/{name}` | 특정 profile 로드 |
| `POST` | `/api/profile/{name}` | profile 생성/갱신 |
| `DELETE` | `/api/profile/{name}` | profile 삭제 |
| `GET` | `/api/profile/{name}/draft` | draft 로드 |
| `POST` | `/api/profile/{name}/draft` | draft 저장 (페이지 진행 시 매번) |
| `POST` | `/api/profile/{name}/materialize` | Config → DeploymentArtifacts 미리보기 |
| `GET` | `/api/aws/regions` | 가용 region 목록 (Bedrock 가용 region 필터) |
| `GET` | `/api/aws/vpcs?region=...` | VPC 목록 |
| `GET` | `/api/aws/subnets?vpc_id=...` | Subnet 목록 |
| `GET` | `/api/aws/hosted-zones` | Route53 hosted zone 목록 |
| `GET` | `/api/aws/cognito-stack?region=...` | Cognito User Pool 스택 자동 감지 |
| `POST` | `/api/secret/keyring` | OS keyring에 secret PUT |
| `GET` | `/api/health` | backend 상태 체크 |

draft 저장 정책: 페이지 N → N+1 진행 시 매번 `POST /api/profile/{name}/draft` 호출. 사용자 cancel 시 draft는 유지되며, 명시적 "Save as Profile" 버튼을 누를 때만 `POST /api/profile/{name}`로 영구 저장.

#### Frontend (Vite + React)

상태 관리: zustand (단일 store, 50줄 미만 충분).

페이지 흐름:

```
0-Profile        새/편집/복제 선택, profile_name 결정
   │
1-Environment    AWS creds 검증, region 자동 감지
   │
2-Provider       provider type 선택 → 동적 sub-form (OktaForm 등)
   │
3-Infra          aws_region, stack_base_name
   │
4-Bedrock        모델 매트릭스 cascade, inference profile (옵션)
   │
5-LoggingQuota   destination/retention + quota (옵션)
   │
6-Distribution   none/presigned-s3/landing-page → 동적 sub-form
   │
7-Features       CodeBuild, Cowork 3P 토글
   │
8-Tags           동적 key/value
   │
9-Review         materialize 결과 펼침, "Save & Exit" 버튼
```

각 페이지는 `useStore()` 훅에서 자기 영역만 read/write. zustand `subscribe`로 페이지 진행 시 backend draft 저장.


## Components and Interfaces

### 위자드 진입점

```
/web/backend/ccwb_wizard/main.py
```

```python
def main():
    """`ccwb` 명령의 진입점.
    1. 빈 포트 찾기 (8400~8499)
    2. uvicorn 서버를 별도 스레드로 시작
    3. 브라우저 자동 오픈 (http://127.0.0.1:<port>)
    4. SIGINT/SIGTERM에서 graceful shutdown
    """
    port = find_free_port(start=8400, end=8499)
    threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=port)).start()
    webbrowser.open(f"http://127.0.0.1:{port}")
    wait_for_signal()
```

`pyproject.toml`의 `[project.scripts]`에 `ccwb = "ccwb_wizard.main:main"` 등록.

빌드 시 frontend의 정적 산출물을 backend의 `static/` 디렉토리로 복사 → FastAPI가 SPA로 서빙. `yarn build` 후 `pip install -e ./web/backend`만 하면 동작.

### Frontend 빌드 통합

```
# 빌드 단계 (개발자가 실행)
cd web/frontend && yarn build
# 산출물: web/frontend/dist/
# 배포 시: web/backend/ccwb_wizard/static/ 으로 복사

# 개발 모드
cd web/frontend && yarn dev    # localhost:5173
cd web/backend && uvicorn ccwb_wizard.main:app --reload --port 8400
# frontend의 vite proxy가 /api → 8400으로 forward
```

### Domain ↔ Backend 경계

backend는 도메인 모듈을 import만 하고 자체 로직을 가지지 않는다. 예외: HTTP 변환 (Pydantic 모델 ↔ dataclass).

```python
# backend/api/wizard.py
from ccwb_domain.config import Config
from ccwb_domain.materialize import materialize

@router.get("/api/profile/{name}")
async def get_profile(name: str) -> Config:
    return Config.load(profile_path(name))

@router.post("/api/profile/{name}/materialize")
async def materialize_endpoint(name: str) -> DeploymentArtifacts:
    config = Config.load(profile_path(name))
    return materialize(config)
```

### Domain ↔ AI agent 경계

agent는 backend 없이 도메인을 직접 import한다.

```python
# AI agent 사용 예시
from ccwb_domain.config import Config
from ccwb_domain.providers.okta import OktaProvider

config = Config.load(Path.home() / ".ccwb/profiles/default.json")
config.provider = {"type": "okta", "domain": "company.okta.com", "client_id": "..."}
config.save(Path.home() / ".ccwb/profiles/default.json")
```

scenarios.md의 카탈로그가 agent의 가이드 역할. 도메인 모듈의 docstring/타입 힌트가 보조.

### Strategy 인터페이스 예시: OktaProvider

```python
# domain/providers/okta.py
@register
@dataclass
class OktaProvider(IdentityProvider):
    type: ClassVar[str] = "okta"
    domain: str
    client_id: str

    def cfn_template_path(self) -> Path:
        return DEPLOYMENT / "bedrock-auth-okta.yaml"

    def cfn_parameters(self, config: Config) -> dict[str, str]:
        return {
            "OktaDomain": self.domain,
            "OktaClientId": self.client_id,
            "IdentityPoolName": config.stack_base_name,
            "AllowedBedrockRegions": ",".join(config_allowed_regions(config)),
            "EnableMonitoring": "true",
        }

    def settings_env(self, config: Config) -> dict[str, str]:
        return {
            "AWS_PROFILE": "ClaudeCode",
            "AWS_REGION": config.source_region,
            "ANTHROPIC_MODEL": config.model_id,
            "ANTHROPIC_CUSTOM_HEADERS": "__ANTHROPIC_CUSTOM_HEADERS__",  # install.sh가 치환
            "CLAUDE_CODE_ENABLE_TELEMETRY": "0" if not config.enable_cc_telemetry else "1",
            "CLAUDE_CODE_USE_MANTLE": "0",                               # rule-of-thumb §4
        }

    def aws_config_section(self, config: Config) -> str:
        return f"""[profile ClaudeCode]
region = {config.source_region}
credential_process = "{CRED_PROCESS_PATH}" --profile {config.profile_name}
"""

    @classmethod
    def wizard_inputs(cls) -> list[FormField]:
        return [
            FormField(
                name="domain",
                label="Okta Domain",
                type="text",
                placeholder="company.okta.com",
                required=True,
                validator="okta_domain",
            ),
            FormField(
                name="client_id",
                label="Okta Client ID",
                type="text",
                required=True,
                validator="min_length:10",
            ),
        ]
```

다른 4개 provider도 동일 패턴.

### FormField 메타데이터

```python
@dataclass
class FormField:
    name: str
    label: str
    type: Literal["text", "password", "number", "select", "checkbox", "textarea"]
    required: bool = False
    placeholder: str = ""
    default: Any = None
    options: list[dict] = None    # type="select" 시 {value, label}
    validator: str | None = None  # 백엔드/frontend 공유 validator key
    help_text: str = ""
    sensitive: bool = False       # password / keyring 저장 대상
```

frontend의 dynamic form 컴포넌트가 `FormField[]`를 받아 자동 렌더한다. 새 IdP가 추가되면 frontend 코드 수정 없이 동작.


## Data Models

### Config JSON 예시 (schema 3.0)

```json
{
  "schema_version": "3.0",
  "profile_name": "default",
  "aws_region": "us-east-1",
  "stack_base_name": "claude-code-auth",
  "provider": {
    "type": "okta",
    "domain": "company.okta.com",
    "client_id": "0oa1234567890abcdef"
  },
  "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "cross_region_profile": "us",
  "source_region": "us-east-1",
  "inference_profiles": {
    "opus": null,
    "sonnet": null,
    "haiku": null
  },
  "bedrock_logging": {
    "destination": "cloudwatch",
    "retention_days": 90
  },
  "quota": {
    "monthly_token_limit": 225000000,
    "daily_token_limit": 8250000,
    "burst_buffer_percent": 10,
    "daily_enforcement": "alert",
    "monthly_enforcement": "block",
    "enable_finegrained_quotas": false
  },
  "distribution": {
    "type": "presigned-s3"
  },
  "enable_codebuild_windows": false,
  "enable_cowork_3p": true,
  "enable_cc_telemetry": false,
  "tags": {
    "Project": "claude-code",
    "Owner": "platform-team"
  }
}
```

### Provider 다형성 표현

`provider.type`이 5종 중 하나(`okta`/`azure`/`cognito`/`auth0`/`generic`). type별 추가 필드:

```json
// Okta
{ "type": "okta", "domain": "...", "client_id": "..." }

// Azure
{ "type": "azure", "tenant_id": "...", "client_id": "...", "auth_mode": "public" }
{ "type": "azure", "tenant_id": "...", "client_id": "...", "auth_mode": "secret",
  "_keyring_ref": "claude-code-with-bedrock:default-client-secret" }
{ "type": "azure", "tenant_id": "...", "client_id": "...", "auth_mode": "certificate",
  "cert_path": "/path/to/cert.pem", "key_path": "/path/to/key.pem" }

// Cognito User Pool (외부 IdP federation 거치는 경우)
{ "type": "cognito", "user_pool_id": "us-east-1_ABC123",
  "client_id": "...", "user_pool_domain": "myteam-claude" }

// Auth0
{ "type": "auth0", "domain": "company.auth0.com", "client_id": "..." }

// Generic OIDC
{ "type": "generic", "issuer_url": "https://auth.example.com",
  "client_id": "...", "thumbprint": "abc123def456...",
  "authorization_endpoint": "https://...", "token_endpoint": "https://...",
  "jwks_uri": "https://..." }
```

`_keyring_ref`는 `_` prefix로 "이 값은 진짜 secret이 아니라 keyring 참조"임을 명시. config.json에는 절대 raw secret을 두지 않는다.

### Distribution 다형성

```json
// disabled
{ "distribution": null }

// presigned-s3
{ "distribution": { "type": "presigned-s3" } }

// landing-page
{
  "distribution": {
    "type": "landing-page",
    "vpc_id": "vpc-abc",
    "public_subnets": ["subnet-1", "subnet-2"],
    "private_subnets": ["subnet-3", "subnet-4"],
    "idp_provider": "okta",
    "idp_config": { "domain": "...", "client_id": "...",
                    "_secret_arn_ref": "arn:aws:secretsmanager:..." },
    "custom_domain": "downloads.company.com",
    "hosted_zone_id": "Z12345"
  }
}
```

### DeploymentArtifacts (materialize 결과)

```python
@dataclass
class StackPlan:
    stack_name: str
    template_path: Path
    parameters: dict[str, str]
    capabilities: list[str]
    tags: dict[str, str]

@dataclass
class KeyringWrite:
    service: str       # "claude-code-with-bedrock"
    account: str       # f"{profile_name}-client-secret"
    value: str         # 실제 secret (메모리에서만)

@dataclass
class DeploymentArtifacts:
    stacks: list[StackPlan]
    settings_json_template: dict
    aws_config_template: str
    keyring_writes: list[KeyringWrite]

    def to_review_dict(self) -> dict:
        """Review 페이지용 직렬화. KeyringWrite의 value는 마스킹."""
```

`to_review_dict()`로 frontend에 노출 시 secret 값은 항상 마스킹.

### Schema 마이그레이션

본 fork는 schema 3.0이 첫 출시이므로 마이그레이션 룰은 단순:

```python
def migrate(data: dict) -> dict:
    version = data.get("schema_version", "unknown")
    if version == "3.0":
        return data
    if version == "2.0":
        # 기존 ccwb v2 profile은 자동 변환 안 함 — Out of Scope (requirements.md)
        raise UnsupportedSchemaError(
            f"schema_version 2.0 (legacy ccwb)은 자동 변환을 지원하지 않습니다. "
            f"ccwb 위자드를 새로 실행해 다시 작성해주세요."
        )
    raise UnsupportedSchemaError(f"unknown schema_version: {version}")
```

향후 3.1로 진화 시 본 함수에 진화 룰 추가 + 단위 테스트 추가.


## Correctness Properties

### Property 1: scenarios.md ↔ 도메인 코드 동등성

**Validates: Requirements 7.3**

scenarios.md의 IdP 표(5종)에 등록된 provider 목록과 `PROVIDERS` registry의 키 집합이 일치한다. 어느 한 쪽에만 있으면 CI 실패.

**검증**: 단위 테스트 `test_scenarios_registry_consistency`. 표 파싱 → 키 set 비교.

### Property 2: materialize 결정성

**Validates: Requirements 4.1, 4.5**

같은 Config로 `materialize()`를 두 번 호출하면 같은 `DeploymentArtifacts`를 반환한다. 시간/랜덤/외부 상태에 의존 금지.

**검증**: snapshot 테스트. 5종 provider × 2종 distribution(presigned-s3/landing-page) × 4종 logging destination(s3/cwlogs/both, quota on/off) ≈ 20개 fixture를 두고 expected output과 비교.

### Property 3: CFN 파라미터 키 호환성

**Validates: Requirements 4.3**

`materialize()`가 만든 CFN 파라미터 키는 해당 CFN 템플릿의 `Parameters` 섹션에 모두 존재해야 한다 (extra 키도 missing 키도 안 됨).

**검증**: 각 `StackPlan`에 대해 `cfn-lint` 또는 `aws cloudformation validate-template`을 부분적으로 mock해서 키 set 비교.

### Property 4: settings.json env 호환성

**Validates: Requirements 4.4**

materialize가 만든 settings.json template의 env 키는 기존 install.sh가 인식하는 placeholder + 키 set의 부분집합이어야 한다.

**검증**: install.sh의 sed 패턴을 grep해서 placeholder 추출 → settings.json template 키와 비교.

### Property 5: schema_version 무결성

**Validates: Requirements 2.2, 2.7**

Config.save() → Config.load() round-trip이 schema_version을 보존한다.

**검증**: Round-trip 테스트.

### Property 6: secret 비유출

**Validates: Requirements 2.6**

`Config.save()`로 디스크에 쓴 JSON에 raw secret이 포함되지 않는다. azure client_secret, landing-page client_secret 등은 `_keyring_ref` / `_secret_arn_ref` 형태로만 존재.

**검증**: 단위 테스트 `test_no_secret_in_disk_json`. 5종 provider × auth_mode 조합 × distribution 조합 fixture 전수.

### Property 7: AI agent 호환

**Validates: Requirements 5.1**

`ccwb_domain` 패키지는 frontend / FastAPI 의존성 없이 import된다.

**검증**: CI에서 `pip install ./web/domain && python -c "from ccwb_domain.config import Config"` 단독 실행.


## Error Handling

### EH-1: AWS credential 부재

backend가 boto3로 region/VPC 등을 조회할 때 credential이 없으면.

**처리**: `botocore.exceptions.NoCredentialsError` 캐치 → HTTP 503 + 명확한 메시지 ("AWS_PROFILE 환경변수 또는 ~/.aws/credentials를 확인해주세요"). frontend는 페이지 1(Environment)에서 차단.

### EH-2: Config 파일 손상

JSON 파싱 실패 또는 schema_version 불일치.

**처리**: 운영자에게 백업 권장 → 위자드는 새 profile로 시작. 손상된 파일은 `<name>.json.broken-<timestamp>` 으로 rename.

### EH-3: provider type registry 미등록

Config의 `provider.type`이 PROVIDERS에 없는 값.

**처리**: load 시점에 명확한 에러. 운영자가 직접 수정한 config.json에 typo가 있는 경우.

### EH-4: Generic OIDC discovery 실패

well-known 엔드포인트가 도달 불가 또는 invalid response.

**처리**: 백엔드가 frontend에 fallback 모드 신호 → 운영자가 수동 입력. 실패 사유는 stderr 로그.

### EH-5: VPC/Subnet 조회 실패

landing-page 페이지에서 EC2 DescribeVpcs 권한이 없는 경우.

**처리**: frontend에 manual entry 모드 toggle → 운영자가 직접 입력. 위험 알림 표시.

### EH-6: keyring 사용 불가

Linux 환경에서 Secret Service가 없거나 macOS Keychain 접근 거부.

**처리**: backend가 명확한 에러 → frontend 페이지 2 azure secret 분기에서 입력 차단. 가이드 메시지 (`brew install gnome-keyring` 등).

### EH-7: backend port 충돌

8400~8499 모두 사용 중.

**처리**: 진입점 main()이 명확한 에러 출력 후 종료.

### EH-8: 위자드 작업 도중 타 프로세스가 같은 profile 수정

운영자가 두 위자드 인스턴스를 동시에 띄우거나, agent와 위자드를 동시에 사용.

**처리**: file lock (fcntl.flock 또는 portalocker). draft 파일에 락 획득. 두 번째 인스턴스는 read-only 모드로 진입.


## Testing Strategy

### Unit Tests (Python, pytest)

도메인 로직만 단독 테스트.

- `test_config_roundtrip.py` — Config.save → load 동등성 (Property 5)
- `test_provider_strategies.py` — 5종 provider × cfn_parameters/settings_env/aws_config_section 출력 fixture 비교 (Property 2)
- `test_materialize_snapshot.py` — 20개 Config fixture × DeploymentArtifacts snapshot (Property 2)
- `test_no_secret_leak.py` — disk JSON에 raw secret 없음 (Property 6)
- `test_scenarios_consistency.py` — scenarios.md 표 ↔ PROVIDERS registry (Property 1)
- `test_cfn_parameter_compatibility.py` — materialize 산출 키 ↔ CFN 템플릿 Parameters (Property 3)

### Frontend Tests (Vitest)

- 페이지 라우팅, store 상태 업데이트, dynamic form 렌더링.
- Backend는 MSW(mock service worker)로 mock.

### Integration Tests (실 backend)

- backend 띄우고 `httpx` 클라이언트로 API 흐름 (5개 시나리오 = 5종 provider 각각).
- `test_e2e_flow.py` — Profile 생성 → 9 페이지 진행 → save → load.

### Smoke Tests (실 AWS, 옵트인)

- `AWS_INTEGRATION_TEST=1` 시에만 실행.
- 위자드로 만든 Config로 materialize → 한 스택만 실제 deploy → 검증 → cleanup.
- 비용 가드: `AWS_INTEGRATION_TEST_BUDGET=$5`.

### Coverage 목표

- 도메인 모듈 ≥ 90%
- backend API ≥ 80%
- frontend 페이지 ≥ 60% (시각 컴포넌트는 낮은 수준)

## Out of Scope (Phase 1)

- 9개 페이지를 하나씩 마무리하기 전 deploy/package/distribute 명령의 web 이전.
- 기존 schema 2.0 자동 마이그레이션.
- 실시간 협업 (두 운영자가 같은 Config 동시 편집).
- 다국어 UI.
- 모바일 친화 UI (운영자 워크스테이션 가정).
- Cowork (Claude Desktop) 통합 깊이 있는 변경.
