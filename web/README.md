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
- **모델 매트릭스**: 12 Claude models × 5 CRIS profiles
