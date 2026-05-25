# Implementation Plan — web-config-wizard

> **상위 문서**: `requirements.md`, `design.md`, `scenarios.md`

## Overview

기존 `source/claude_code_with_bedrock/` (CLI/위자드 코드)를 통째 삭제하고, web 위자드를 새로 구축한다. 보존 자산은 `deployment/infrastructure/*`, `source/credential_provider/*`, `source/claude_code_with_bedrock/models.py`(모델 매트릭스 발췌), `install.sh`/`install.bat`.

작업은 6 phase로 진행한다.

- **Phase 1: 정리 + 보존 자산 이동**
- **Phase 2: Domain 모듈 (Python)**
- **Phase 3: Backend (FastAPI)**
- **Phase 4: Frontend (Vite + React)**
- **Phase 5: 진입점 통합**
- **Phase 6: 검증 + 문서**

## Tasks

### Phase 1 — 정리 및 보존 자산 이동

- [ ] 1.1 보존 자산을 `web/preserved/`로 카피
  - `source/credential_provider/` → `web/preserved/credential_provider/` (참조용 사본)
  - `source/claude_code_with_bedrock/models.py`에서 모델 매트릭스 발췌 → `web/domain/ccwb_domain/bedrock_models.py`
  - 기존 install.sh / install.bat 자산 위치 확인 (현재 package.py가 동적 생성하므로 별도 정적 파일 없음 → Phase 2.5에서 도메인이 생성하도록 이전)
  - _Validates: Requirement 4.1, 4.2_

- [ ] 1.2 CLI/위자드 코드 통째 삭제
  - `source/claude_code_with_bedrock/` (단, 모델 매트릭스 발췌 후)
  - `source/tests/test_*.py` 중 cli/init/config 관련 (credential_provider, integration 디렉토리는 보존)
  - `source/pyproject.toml`에서 cleo, questionary, rich, click 등 CLI 의존성 제거
  - _Validates: Requirement 4.1, 4.2_

- [ ] 1.3 새 디렉토리 스켈레톤 생성
  - `/web/domain/`, `/web/backend/`, `/web/frontend/` 디렉토리
  - 각 디렉토리에 README.md 한 줄 placeholder
  - 루트 `.gitignore`에 `web/frontend/dist/`, `web/frontend/node_modules/`, `**/__pycache__/`, `.venv/` 등 추가
  - _Validates: Requirement 5.1_

### Phase 2 — Domain 모듈 (Python, 의존성 최소)

- [ ] 2.1 Config dataclass + JSON IO
  - `web/domain/ccwb_domain/config.py` 작성
  - `Config.load(path)`, `Config.save(path)`, `migrate(data)` 구현
  - file lock (portalocker) 적용
  - 단위 테스트: roundtrip, schema_version 보존, lock 동작
  - _Validates: Requirement 2.1, 2.2, 2.7, 7.4_

- [ ] 2.2 Provider Strategy ABC + registry
  - `web/domain/ccwb_domain/providers/base.py` (`IdentityProvider` ABC)
  - `web/domain/ccwb_domain/providers/__init__.py` (registry, `register()` 데코레이터)
  - `FormField` dataclass
  - 단위 테스트: ABC 인스턴스화 차단, registry 등록/조회
  - _Validates: Requirement 3.1, 3.2_

- [ ] 2.3 5종 Provider Strategy 구현
  - `okta.py`, `azure.py`, `cognito.py`, `auth0.py`, `generic.py`
  - 각 strategy의 cfn_parameters/settings_env/aws_config_section/wizard_inputs 구현
  - Azure는 auth_mode 분기 (public/secret/certificate)
  - Generic은 OIDC discovery + thumbprint 계산 helper 포함
  - 단위 테스트: 각 strategy snapshot
  - _Validates: Requirement 3.1, 3.4, scenarios §1_

- [ ] 2.4 Federation / Distribution Strategy
  - `federation.py` (cognito / direct)
  - `distribution.py` (PresignedS3 / LandingPage)
  - 단위 테스트
  - _Validates: Requirement 3.5, scenarios §2 §6_

- [ ] 2.5 materialize() 통합
  - `web/domain/ccwb_domain/materialize.py`
  - StackPlan / DeploymentArtifacts / KeyringWrite dataclass
  - 의존성 순서 정렬 (auth → bedrock-logging → dashboard → quota → distribution → codebuild → s3bucket)
  - settings.json template 생성, ~/.aws/config 본문 생성
  - keyring_writes 수집 (azure secret, distribution secret)
  - to_review_dict() 마스킹
  - 단위 테스트: 20개 fixture × snapshot 비교
  - _Validates: Requirement 4.3, 4.4, Property 2_

- [ ] 2.6 secrets.py — keyring helper
  - `web/domain/ccwb_domain/secrets.py`
  - keyring 라이브러리 wrapper, `_keyring_ref` 형식 명시
  - 단위 테스트: keyring backend mock으로 round-trip
  - _Validates: Requirement 2.6, Property 6_

- [ ] 2.7 Bedrock 모델 매트릭스 정리
  - `web/domain/ccwb_domain/bedrock_models.py` (Phase 1.1 자산 정리)
  - `get_available_profiles_for_model`, `get_source_regions_for_model_profile`, `get_destination_regions_for_model_profile`, `get_profile_description` helper 보존
  - 단위 테스트: 호출 결과가 scenarios.md 표와 일치
  - _Validates: scenarios §3_

- [ ] 2.8 Property 검증 테스트
  - test_scenarios_consistency.py — scenarios.md ↔ PROVIDERS registry
  - test_cfn_parameter_compatibility.py — materialize 키 ↔ CFN Parameters
  - test_no_secret_leak.py
  - test_domain_standalone.py — frontend/backend 의존성 없이 import 가능
  - _Validates: Property 1, 3, 6, 7_

### Phase 3 — Backend (FastAPI)

- [ ] 3.1 backend 프로젝트 스켈레톤
  - `web/backend/pyproject.toml` (fastapi, uvicorn, pydantic, boto3, keyring, ccwb-domain editable install)
  - `web/backend/ccwb_wizard/main.py` (FastAPI app)
  - `web/backend/ccwb_wizard/settings.py`
  - 정적 파일 서빙 디렉토리 `static/` (frontend dist 복사 위치)
  - _Validates: Requirement 6.1_

- [ ] 3.2 Profile / Draft API
  - `api/wizard.py` — Profile CRUD, draft CRUD
  - 도메인 Config import 사용
  - 통합 테스트: httpx로 모든 엔드포인트
  - _Validates: Requirement 1.6, 1.7, 2.1, 2.5_

- [ ] 3.3 Scenarios API
  - `api/scenarios.py` — provider list, distribution types, federation types, model matrix를 frontend가 쓸 수 있는 JSON으로 export
  - `wizard_inputs()` 결과 직렬화
  - _Validates: Requirement 3.6, 5.4_

- [ ] 3.4 AWS Lookup API
  - `api/aws_lookup.py` — region/VPC/subnet/HostedZone/Cognito-stack
  - boto3 호출, NoCredentialsError 핸들링 (EH-1)
  - _Validates: Requirement 6.2, 6.5, EH-1, EH-5_

- [ ] 3.5 Secret API
  - `api/secret.py` — POST keyring (azure secret), POST secrets-manager (distribution secret)
  - keyring 사용 불가 시 명확한 에러 (EH-6)
  - _Validates: Requirement 2.6, 6.4, EH-6_

- [ ] 3.6 materialize 미리보기 API
  - `POST /api/profile/{name}/materialize` — DeploymentArtifacts.to_review_dict() 반환
  - _Validates: Property 2_

- [ ] 3.7 backend 진입점 (main 함수)
  - free port 검색 (8400~8499)
  - uvicorn 별도 스레드 실행
  - 브라우저 자동 오픈
  - SIGINT graceful shutdown
  - port 충돌 시 명확한 에러 (EH-7)
  - _Validates: Requirement 6.1, 6.6, EH-7_

### Phase 4 — Frontend (Vite + React + TS, yarn)

- [ ] 4.1 frontend 스켈레톤
  - `cd web/frontend && yarn create vite . --template react-ts`
  - tsconfig, vite.config.ts (proxy /api → backend)
  - 디렉토리 정리: `src/{pages,components,hooks,api,store}.ts`
  - _Validates: Requirement 1.1_

- [ ] 4.2 zustand store
  - `src/store.ts` — config draft 상태, page navigation 상태, AWS lookup cache
  - subscribe로 page 진행 시 backend draft 저장 트리거
  - _Validates: Requirement 1.5, 1.6_

- [ ] 4.3 API client
  - `src/api.ts` — backend HTTP 호출 wrapper, 에러 타입 변환
  - _Validates: Requirement 1.3, 6.5_

- [ ] 4.4 페이지 0 — Profile 선택
  - 신규/편집/복제 분기, profile_name validator
  - _Validates: Requirement 1.1, 1.2_

- [ ] 4.5 페이지 1 — Environment Check
  - backend `/api/aws/regions` 호출, AWS creds 체크
  - 차단/경고 표시
  - _Validates: Requirement 6.5, EH-1_

- [ ] 4.6 페이지 2 — Provider (5종 dispatch)
  - `<ProviderForm provider={selected}>` 컴포넌트
  - 각 provider sub-form은 wizard_inputs() 메타데이터로 dynamic 렌더
  - Azure auth_mode sub-분기
  - Generic OIDC discovery (자동 endpoint 추출 + thumbprint 계산)
  - _Validates: Requirement 1.4, 3.6, scenarios §1_

- [ ] 4.7 페이지 3 — AWS Infrastructure
  - region select, stack_base_name input, federation_type radio
  - _Validates: Requirement 1.2, scenarios §2_

- [ ] 4.8 페이지 4 — Bedrock 모델
  - 모델 매트릭스 cascade (model → profile → source_region)
  - inference profile per tier (옵션)
  - _Validates: scenarios §3_

- [ ] 4.9 페이지 5 — Logging + Quota
  - destination select, retention input
  - quota toggle → 활성 시 monthly/daily/enforcement 입력
  - _Validates: scenarios §4 §5_

- [ ] 4.10 페이지 6 — Distribution
  - none/presigned-s3/landing-page select
  - landing-page 선택 시 VPC/subnet/IdP/custom_domain sub-form
  - Cognito 자동 감지 (`/api/aws/cognito-stack`)
  - _Validates: scenarios §6_

- [ ] 4.11 페이지 7 — Features
  - CodeBuild Windows 토글, Cowork 3P 토글
  - _Validates: scenarios §7_

- [ ] 4.12 페이지 8 — Tags
  - 동적 key/value, validator (aws: prefix 차단, length)
  - _Validates: scenarios §8_

- [ ] 4.13 페이지 9 — Review
  - `/api/profile/{name}/materialize` 호출 → DeploymentArtifacts 펼침
  - secret 마스킹 표시
  - "Save as Profile" 버튼 → POST profile + 위자드 종료
  - _Validates: Requirement 1.3, Property 6_

- [ ] 4.14 vitest + MSW
  - 페이지 단위 테스트
  - store 테스트
  - _Validates: scenarios.md 영향 항목_

### Phase 5 — 진입점 통합

- [ ] 5.1 빌드 스크립트
  - `web/Makefile` 또는 root `package.json` 스크립트
  - `make build` = `yarn build && cp -r web/frontend/dist/* web/backend/ccwb_wizard/static/`
  - `make dev` = backend reload + frontend hot reload 동시 실행
  - _Validates: Requirement 6.1_

- [ ] 5.2 `ccwb` 단일 명령 진입점
  - `pyproject.toml`의 `[project.scripts]`에 `ccwb = "ccwb_wizard.main:main"` 등록
  - `pip install -e ./web/backend` 후 `ccwb` 실행 → 위자드 동작
  - _Validates: Requirement 6.1, 6.6_

- [ ] 5.3 packaging 스모크
  - 클린 가상환경에서 `pip install` → `yarn build` → `ccwb` 실행 → 페이지 0 도달 확인
  - _Validates: Requirement 6.1_

### Phase 6 — 검증 + 문서

- [ ] 6.1 통합 테스트 (5종 provider 각각 E2E)
  - backend + 도메인 통합, 9페이지 흐름 시뮬레이션
  - _Validates: Property 2_

- [ ] 6.2 README 작성 + scenarios.md 링크
  - `web/README.md` — 개발/실행/빌드 흐름
  - 루트 `README.md`에서 새 위자드로 가이드
  - `MIGRATION.md` — 기존 CLI 사용자에게 (자동 마이그레이션 없음 명시)
  - _Validates: Requirement 7.1_

- [ ] 6.3 AI agent 가이드 문서
  - `web/AGENT_GUIDE.md` — agent가 Config를 직접 작성/수정하는 패턴 예시
  - scenarios.md를 1차 출처로 가리킴
  - _Validates: Requirement 5.4, 5.5_

- [ ] 6.4 CI 워크플로
  - GitHub Actions: `pytest` (도메인 + backend), `yarn test`, scenarios 일관성 검증
  - _Validates: Requirement 7.3_

- [ ] 6.5 (옵션) PoC 환경 실 배포 검증
  - 위자드로 새 profile 생성 → materialize → 한 스택만 실 deploy → cleanup
  - 비용 가드 $5
  - _Validates: Property 2 실증_

## Task Dependency Graph

```json
{
  "waves": [
    {"wave": 1, "name": "정리", "tasks": ["1.1", "1.2", "1.3"]},
    {"wave": 2, "name": "도메인 기반", "tasks": ["2.1", "2.2", "2.7"]},
    {"wave": 3, "name": "도메인 strategy", "tasks": ["2.3", "2.4", "2.6"]},
    {"wave": 4, "name": "도메인 통합", "tasks": ["2.5", "2.8"]},
    {"wave": 5, "name": "backend", "tasks": ["3.1", "3.2", "3.3", "3.4", "3.5", "3.6", "3.7"]},
    {"wave": 6, "name": "frontend 기반", "tasks": ["4.1", "4.2", "4.3"]},
    {"wave": 7, "name": "frontend 페이지", "tasks": ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "4.10", "4.11", "4.12", "4.13"]},
    {"wave": 8, "name": "frontend 테스트", "tasks": ["4.14"]},
    {"wave": 9, "name": "통합 진입점", "tasks": ["5.1", "5.2", "5.3"]},
    {"wave": 10, "name": "검증 + 문서", "tasks": ["6.1", "6.2", "6.3", "6.4", "6.5"]}
  ]
}
```

병렬 갈래 안내:
- Phase 2(도메인)와 Phase 4 페이지 4.4~4.5(데이터 의존성 약한 것)는 약간 겹쳐 진행 가능
- Phase 3 backend와 Phase 4 frontend는 API 계약(scenarios.md) 잡힌 이후 병렬

## Notes

### 보존 자산 위치 결정

- `web/preserved/credential_provider/` — 참조용 사본 (실제 빌드/배포에 사용되는 사본은 `source/credential_provider/`로 유지). package.py 부재로 인해 zip 포함 로직은 별도 task에서 처리 (Out of Scope, Phase 2 spec).
- `web/domain/ccwb_domain/bedrock_models.py` — 정식 위치 (모델 매트릭스 import 출처)

### Out of Scope (재명시)

- deploy/package/distribute 명령의 web 이전 (다음 spec)
- 실 zip 빌드 및 install.sh 자동 생성 (다음 spec)
- 기존 schema 2.0 자동 마이그레이션
- 다국어 UI

### Schema 진화 정책

본 spec 출시 = schema 3.0. 향후 진화 시 `migrate()` 함수에 룰 추가 + 단위 테스트. schema 2.0은 영원히 자동 변환하지 않는다.
