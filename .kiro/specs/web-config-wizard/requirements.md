# Requirements Document

> **상위 문서**: `rule-of-thumb.md` (운영 원칙), `scenarios.md` (선택지 카탈로그, 진실의 원천)

## Introduction

기존 `poetry run ccwb init` 대화형 위자드는 init.py 한 파일이 2700줄에 달하는 단일 거대 함수, ~70 필드의 평탄한 Profile dataclass, IdP/distribution 분기가 if/elif로 흩어진 구조다. 위자드 진행 추적이 어렵고, AI agent가 동일한 작업을 수행하려면 별도 인터페이스를 또 만들어야 한다.

본 spec은 위 위자드를 **웹 기반 SPA + 스키마 있는 텍스트 파일** 구조로 갈아엎는다. 핵심 결정:

1. 운영자 입력은 **Vite + React 위자드**로 받는다.
2. 위자드 산출물은 **단일 Config text file**(`~/.ccwb/profiles/<name>.json`)이며, schema_version으로 진화한다.
3. CLI 명령과 AI agent도 동일한 Config 파일을 read/write할 수 있어야 한다.
4. **CFN 템플릿과 credential-process 바이너리는 변경하지 않는다** — 위자드가 만들어내는 입력만 새 형태로 바꾼다.
5. 코드 양은 절반 이하로 줄인다 — IdP/distribution 분기는 strategy 패턴으로 응집한다.
6. **Federation은 IAM Direct 단일 경로**다. 5종 IdP는 그 백엔드 OIDC 제공자일 뿐이며 federation 타입 분기는 두지 않는다 (rule-of-thumb §2).

## Requirements

### Requirement 1: 위자드는 모든 운영자 입력을 단계별로 수집한다

**User Story:** 운영자로서, 분기를 따라가며 필요한 입력만 보면서 Config를 완성하고 싶다. 그래서 한 번에 모든 옵션을 외우거나 잘못된 값을 입력하지 않는다.

**Objective:** 운영자로서, 분기를 따라가며 필요한 입력만 보면서 Config를 완성하고 싶다. 그래서 한 번에 모든 옵션을 외우거나 잘못된 값을 입력하지 않는다.

#### Acceptance Criteria

1. WHEN 운영자가 위자드를 처음 열면 THEN 시스템은 신규 / 기존 편집 / 복제 중 선택지를 표시해야 한다.
2. WHEN 운영자가 신규를 선택하면 THEN 시스템은 9개 단계(Profile, Environment, Provider, Infra, Bedrock, Logging+Quota, Distribution, Features, Tags)를 순서대로 진행해야 한다.
3. WHEN 운영자가 페이지 N에서 페이지 N+1로 진행하려 하면 THEN 시스템은 페이지 N의 모든 필수 필드가 유효함을 확인하고 차단/경고해야 한다.
4. WHERE 페이지가 분기 입력을 가지면 (예: Provider page의 IdP 종류) THE 시스템은 선택에 따라 노출 필드를 동적으로 바꿔야 한다.
5. WHEN 운영자가 페이지 사이를 자유로이 왕복하면 THEN 시스템은 이전에 입력한 값을 보존해야 한다.
6. WHEN 운영자가 브라우저를 닫고 다시 열면 THEN 시스템은 마지막 draft를 복구해 같은 단계에서 재개할 수 있어야 한다.
7. IF 운영자가 위자드 도중 cancel하면 THEN 시스템은 draft를 유지하고 실제 Profile 파일에는 영향을 주지 않아야 한다.

### Requirement 2: Config는 스키마 있는 텍스트 파일로 영구 저장된다

**User Story:** 운영자/CLI/agent로서, Config를 텍스트로 읽고 쓰고 diff하고 싶다. 그래서 GUI 없이도 변경을 추적/리뷰/자동화할 수 있다.

**Objective:** 운영자/CLI/agent로서, Config를 텍스트로 읽고 쓰고 diff하고 싶다. 그래서 GUI 없이도 변경을 추적/리뷰/자동화할 수 있다.

#### Acceptance Criteria

1. WHEN 위자드가 저장을 수행하면 THEN 시스템은 Config를 `~/.ccwb/profiles/<name>.json`에 직렬화해야 한다.
2. WHERE Config는 `schema_version` 필드를 포함해야 한다. THE 첫 출시는 `"3.0"`이다 (기존 v2.0과 의미 호환 X).
3. WHILE 시스템이 Config를 읽는 동안, 알려지지 않은 필드는 무시하고 경고 로그만 남겨야 한다.
4. IF 알려진 필드가 누락되면 THEN 시스템은 schema_version에 정의된 기본값을 적용해야 한다.
5. WHEN 외부 도구(agent/CLI)가 Config 파일을 직접 수정한 뒤 위자드를 열면 THEN 위자드는 그 값을 prefill해 보여야 한다.
6. WHERE Config의 일부 필드(예: azure client_secret)는 보안상 텍스트 파일에 저장 금지 THE 시스템은 운영자 머신의 OS keyring에 별도 저장하고 텍스트 파일에는 keyring 참조 메타데이터만 남긴다.
7. WHEN Config의 schema_version이 현재 위자드 버전과 다르면 THEN 시스템은 자동 마이그레이션하거나 명확한 에러 메시지를 표시해야 한다.

### Requirement 3: 분기 시나리오는 strategy 클래스로 응집된다

**User Story:** 개발자로서, IdP를 추가하거나 Distribution 옵션을 변경할 때 한 곳만 수정하고 싶다. 그래서 위자드/CLI/AI 인터페이스가 동시에 따라온다.

**Objective:** 개발자로서, IdP를 추가하거나 Distribution 옵션을 변경할 때 한 곳만 수정하고 싶다. 그래서 위자드/CLI/AI 인터페이스가 동시에 따라온다.

#### Acceptance Criteria

1. WHERE 5종 IdP는 각각 별도 `IdentityProvider` 서브클래스를 가져야 한다.
2. THE 각 서브클래스는 `cfn_template_path`, `cfn_parameters`, `settings_env`, `aws_config_section`, `wizard_inputs` 5개 메서드를 구현해야 한다.
3. WHEN 새 IdP를 추가하면 THEN 도메인 디렉토리에 클래스 1개를 추가하고 registry에 등록하는 것 외 다른 코드 변경이 없어야 한다.
4. WHERE Distribution은 PresignedS3 / LandingPage 두 strategy를 가진다.
5. WHERE Federation은 IAM Direct 단일 경로이며 strategy로 응집하지 않는다 (rule-of-thumb §2). 도메인 코드는 federation 분기 없이 작성된다.
6. WHEN 위자드 페이지가 strategy 메타데이터를 표시할 때 THE 페이지 코드는 strategy의 `wizard_inputs()`만 호출하고 자체 분기 로직을 가지지 않아야 한다.
7. THE 도메인 모델은 frontend/CLI/agent와 상관없이 단독 import 가능해야 한다 (FastAPI/React 의존성 없음).

### Requirement 4: 기존 CFN 템플릿과 credential-process는 변경하지 않는다

**User Story:** 솔루션 운영자로서, 위자드 갈아엎기 작업이 인프라/사용자 머신 동작을 깨지 않기를 원한다. 그래서 PoC 환경의 사용자 zip을 재배포할 필요가 없다.

**Objective:** 솔루션 운영자로서, 위자드 갈아엎기 작업이 인프라/사용자 머신 동작을 깨지 않기를 원한다. 그래서 PoC 환경의 사용자 zip을 재배포할 필요가 없다.

#### Acceptance Criteria

1. THE 새 위자드는 기존 `deployment/infrastructure/*.yaml`을 byte-level로 변경하지 않아야 한다.
2. THE 새 위자드는 기존 `source/credential_provider/*.py`를 변경하지 않아야 한다.
3. WHEN materialize(config)가 CFN 파라미터를 생성할 때 THE 파라미터 키 이름은 기존 CFN 템플릿이 정의한 그대로여야 한다 (`OktaDomain`, `CognitoUserPoolId`, `BedrockLoggingDestination` 등).
4. WHEN materialize(config)가 settings.json을 생성할 때 THE env 키 이름과 값 형식은 기존 install.sh의 placeholder와 호환되어야 한다.
5. IF 운영자가 변경 후 새 위자드로 만든 Profile이 변경 전 도구로 deploy됐을 때와 다른 결과를 만들면 THEN 그것은 본 spec의 결함으로 간주한다.

### Requirement 5: AI agent와 CLI도 동일한 도메인 모델을 사용한다

**User Story:** AI agent로서, 운영자가 위자드를 열지 않아도 Config를 작성하거나 수정해 deploy/package 작업을 자동화하고 싶다. 그래서 사용자가 동일한 task를 반복하지 않는다.

**Objective:** AI agent로서, 운영자가 위자드를 열지 않아도 Config를 작성하거나 수정해 deploy/package 작업을 자동화하고 싶다. 그래서 사용자가 동일한 task를 반복하지 않는다.

#### Acceptance Criteria

1. THE 도메인 모듈(`Config`, strategy 클래스, `materialize`)은 frontend 의존성 없이 import 가능해야 한다.
2. WHERE CLI 진입점이 존재한다면 (예: `ccwb` 명령) THE 같은 도메인 모듈을 호출해야 하며, 자체 도메인 로직을 두지 않아야 한다.
3. WHEN AI agent가 Config를 직접 작성/수정한 후 위자드를 열면 THEN 위자드는 그 값을 인식하고 표시해야 한다 (Requirement 2.5).
4. WHILE AI agent가 Config 파일을 작성하는 동안, scenarios.md는 agent에게 가능한 값의 카탈로그를 제공해야 한다 (예: provider type 5종, distribution 2종 등).
5. THE scenarios.md의 Python literal export(예: 모델 매트릭스)는 agent와 코드 양쪽이 import 가능한 형태여야 한다.

### Requirement 6: 위자드는 운영자 머신에서 로컬로 실행된다

**User Story:** 운영자로서, AWS 자격증명과 OS keyring에 접근하는 위자드를 외부 호스팅에 의존하지 않고 자기 머신에서 실행하고 싶다. 그래서 자격증명이 외부로 새지 않는다.

**Objective:** 운영자로서, AWS 자격증명과 OS keyring에 접근하는 위자드를 외부 호스팅에 의존하지 않고 자기 머신에서 실행하고 싶다. 그래서 자격증명이 외부로 새지 않는다.

#### Acceptance Criteria

1. WHEN 운영자가 위자드를 시작하면 THEN 시스템은 localhost에 backend HTTP 서버를 띄우고 브라우저를 자동으로 연다.
2. WHERE backend는 운영자 머신의 AWS credential chain (env / ~/.aws / IAM Role)을 사용해야 한다.
3. WHILE backend가 실행 중일 때, 외부 네트워크에서 backend에 도달할 수 없어야 한다 (bind 127.0.0.1).
4. WHEN backend가 OS keyring에 secret을 저장할 때 THE OS 표준 keyring(macOS Keychain, Windows Credential Manager, Linux Secret Service)을 사용해야 한다.
5. IF AWS credential을 백엔드가 얻지 못하면 THEN 시스템은 명확한 에러 메시지와 가이드를 표시해야 한다.
6. WHEN 위자드 사용이 끝나면 THE backend 프로세스는 운영자가 명시적으로 종료할 수 있어야 한다 (Ctrl+C 또는 UI 종료 버튼).

### Requirement 7: 변경 관리

**User Story:** 개발자로서, scenarios가 코드와 어긋나는 것을 막고 싶다. 그래서 위자드와 매핑이 silently 깨지지 않는다.

**Objective:** 개발자로서, scenarios가 코드와 어긋나는 것을 막고 싶다. 그래서 위자드와 매핑이 silently 깨지지 않는다.

#### Acceptance Criteria

1. WHEN scenarios.md의 표가 변경되면 THEN 도메인 strategy 클래스에 대응하는 변경이 동시에 PR에 포함되어야 한다.
2. WHERE scenarios.md가 코드 import 가능한 데이터를 가지면 (예: 모델 매트릭스, provider 목록) THE 그 데이터는 별도 Python 모듈로 export되어야 한다.
3. THE CI는 scenarios.md의 카탈로그와 도메인 코드의 strategy registry 간 일관성을 검증해야 한다 (registry에 등록된 IdP가 scenarios.md에 모두 있고, 그 역도 성립).
4. WHEN 새 schema_version이 추가되면 THEN 마이그레이션 함수와 단위 테스트가 함께 추가되어야 한다.

## Out of Scope

- 기존 `~/.ccwb/profiles/*.json` (schema 2.0)에서 새 schema 3.0으로의 자동 마이그레이션 — 운영자는 새 위자드로 다시 작성한다 (PoC 단계라 손해 적음, scenario 카탈로그가 1:1 매핑이 아니므로 자동 변환에 가치 없음).
- 위자드 진입점의 OS-level 패키징 (`.dmg`, `.exe`, `.deb`) — Phase 1에서는 `pip install` 또는 `git clone + yarn dev` 수준으로 충분.
- 다국어 UI — 한국어 단일 (운영자 본인 환경 한정).
- 기존 CLI 명령(`ccwb deploy`, `package`, `distribute`, `test`, `status` 등)의 web 이전 — Phase 2 영역. 본 spec은 init(위자드)만 다룬다.
- Cowork (Claude Desktop) 통합 깊이 있는 변경 — 토글만 노출, 패키징 결과는 기존과 동일.

## Glossary

| 용어 | 정의 |
|------|------|
| **Config** | 운영자가 한 번 작성하는 단일 JSON 파일. `~/.ccwb/profiles/<name>.json`에 영구 저장됨. UI/CLI/agent 공통 진실의 원천. |
| **Profile** | Config 파일 1개. 이름(`profile_name`)으로 식별. 한 운영자가 여러 profile 보유 가능. |
| **Draft** | 위자드 진행 중 임시 저장본. 명시적 "Save as Profile" 전까지 영구 저장본에 영향 없음. |
| **Strategy** | 분기 시나리오(IdP, Distribution)를 응집한 클래스. ABC + 서브클래스 패턴. Federation은 단일 경로라 strategy로 두지 않음. |
| **materialize** | `Config → DeploymentArtifacts` 함수. CFN 파라미터, settings.json 템플릿, ~/.aws/config, keyring writes를 한꺼번에 생성. |
| **DeploymentArtifacts** | materialize의 출력. UI/CLI/agent가 deploy 단계에서 소비. |
| **scenarios.md** | 선택지 카탈로그. 사람 가독 표 + Python literal export. 도메인 코드의 진실의 원천. |
| **provider_strategy** | Config의 `provider` dict를 strategy 인스턴스로 변환하는 dispatch 함수. |
| **wizard_inputs** | strategy가 노출하는 FormField 메타데이터. frontend가 dynamic form 렌더에 사용. |
| **schema_version** | Config 텍스트 파일의 버전. 본 spec은 `"3.0"`. 향후 진화 시 `migrate()`에 룰 추가. |
