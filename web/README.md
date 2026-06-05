# ccwb Web Wizard

Claude Code with Amazon Bedrock의 web 기반 배포 위자드.

## 구조

```
web/
├── domain/          # ccwb_domain — pure Python 도메인 모듈 (Config, providers, materialize)
├── backend/         # ccwb_wizard — FastAPI backend (localhost only)
├── frontend/        # Vite + React + TypeScript + Cloudscape 9-page wizard
└── binaries/        # credential-process (OIDC ↔ STS 자격증명 브리지)
```

## 빠른 시작

### 사전 요구

- Python 3.10–3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js ≥ 18
- yarn (`npm install -g yarn`)

### 설치 + 실행

```bash
# ccwb/ 디렉토리에서
uv sync --all-packages        # Python 환경 + 도메인/백엔드 설치
cd web/frontend && yarn install  # Frontend 의존성
cd ../..

# 개발 모드 (vite + uvicorn 병렬)
make dev

# 프로덕션 빌드 (frontend → static 복사 후 단일 서버)
make build
uv run ccwb
```

### 주요 명령

| 명령 | 설명 |
|------|------|
| `make dev` | 개발 모드 (hot reload) |
| `make build` | 프로덕션 빌드 |
| `uv run ccwb` | 위자드 실행 (빌드 후) |
| `make clean` | 빌드 아티팩트 정리 |
| `uv run pytest web/domain/tests/` | 도메인 테스트 (41 tests) |
| `uv run pytest web/backend/tests/` | 백엔드 테스트 (11 tests) |

## 아키텍처

```
Operator Browser ←→ FastAPI (127.0.0.1:8400) ←→ ccwb_domain
                          ↕
                    boto3 (AWS APIs)
                    OS keyring (secrets)
```

- Backend는 **localhost bind** — 외부에서 도달 불가 (Spec Req 6.3)
- Config는 `~/.ccwb/profiles/<name>.json`에 저장 (UI/CLI/agent 공통)
- CFN 템플릿과 credential-process는 byte-level 보존

## 기술 스택

- **도메인**: pure Python (외부 의존성 없음 — agent 단독 import 가능)
- **백엔드**: FastAPI + uvicorn + pydantic
- **프론트엔드**: Vite + React 18 + TypeScript + Cloudscape Design System + zustand
- **빌드 도구**: uv (Python) + yarn (Node)
- **모델 매트릭스**: 13 Claude models × 5 CRIS profiles

## 위자드 흐름 (11 단계)

| 단계 | 페이지 | 역할 |
|------|--------|------|
| 0 | 프로필 | 신규/편집/복제 모드 + 프로필 선택 |
| 1 | AWS 환경 | 배포 자격증명(named profile) + 리전 |
| 2 | Identity Provider | OIDC IdP 선택 + **연결 테스트(claims preview)** + **Attribution 매핑** |
| 3 | 인프라 이름 | CFN 스택 base name |
| 4 | Bedrock 모델 | tier별 모델 + CRIS source region |
| 5 | 로깅 & 할당량 | Bedrock invocation 로깅 + quota |
| 6 | 배포 방식 | Presigned S3 / Landing Page |
| 7 | 추가 기능 | Windows 빌드, Cowork 3P, telemetry |
| 8 | 리소스 태그 | CFN 일괄 태그 |
| 9 | 검토 및 저장 | 설정 검토 + materialize preview + 프로필 저장 |
| 10 | 배포 및 테스트 | ① Deploy → ② Package → ③ 로컬 테스트 → ④ Distribute |

## Attribution 매핑 (동적 바인딩)

운영자가 IdP claim을 대시보드 dimension에 매핑하면, credential-process가 **매 인증 시점**에 적용합니다 (install 시점 정적 치환이 아님).

```
IdP claim (email, cognito:groups, ...) 
   → attribution.mapping (user←email, team←cognito:groups)
   → attribution.passthrough (sub, cognito:username)
   → settings.json ANTHROPIC_CUSTOM_HEADERS 동적 갱신
   → Bedrock invocation log $.requestMetadata.{user,team,...}
```

신뢰 근거는 헤더(위조 가능)가 아니라 STS role session name(`identity.arn`, IdP 보증)입니다.

## 배포 파이프라인 (단계 10)

| 액션 | API | 동작 |
|------|-----|------|
| Deploy | `POST /profile/{name}/deploy` | CFN 스택 순차 배포 (SSE 진행률), 기존 스택 인식, OIDC/logging 중복 skip, output→프로필 동기화 |
| Package | `POST /profile/{name}/package` | PyInstaller 바이너리 + config.json + install.sh → zip |
| Distribute | `POST /profile/{name}/distribute` | S3 업로드 + presigned URL (48h) |

엔드유저는 zip을 받아 `install.sh` 실행 → `credential-process --profile <name>`로 첫 인증.

