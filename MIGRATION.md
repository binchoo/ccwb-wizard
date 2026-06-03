# Migration Guide — CLI → Web Wizard

## 기존 CLI 사용자를 위한 안내

기존 `poetry run ccwb init` 대화형 CLI는 **폐기**되었습니다. 모든 운영자 인터페이스는 web 위자드로 대체됩니다.

## 무엇이 바뀌었는가

| 이전 | 이후 |
|------|------|
| `poetry run ccwb init` (대화형 CLI) | `uv run ccwb` (web 위자드 — 브라우저 자동 오픈) |
| `poetry run ccwb deploy` | 위자드 Phase 2 spec (별도 개발 예정) |
| `poetry run ccwb package` | 위자드 Phase 2 spec (별도 개발 예정) |
| `poetry run ccwb distribute` | 위자드 Phase 2 spec (별도 개발 예정) |
| Poetry | uv |
| `~/.ccwb/profiles/*.json` (schema 2.0) | `~/.ccwb/profiles/*.json` (schema 3.0) |

## Schema 자동 마이그레이션

**지원하지 않습니다.** 기존 schema 2.0 profiles를 자동으로 3.0으로 변환하는 기능은 없습니다.

### 권장 절차

1. `uv run ccwb` 실행
2. web 위자드에서 "신규 프로필 생성"
3. 기존 profile의 값을 참고하면서 페이지별로 입력
4. "프로필 저장"

기존 `~/.ccwb/profiles/*.json` (schema 2.0) 파일은 그대로 보존됩니다 — 삭제하지 않습니다. 새 위자드가 읽으려 하면 "schema_version 2.0은 지원되지 않습니다" 에러를 표시합니다.

## 사용자(개발자) 머신 영향

**없습니다.** credential-process binary와 installer 흐름은 동일합니다. 사용자가 이미 받은 zip/installer는 그대로 동작합니다.

## CFN 인프라 영향

**없습니다.** `deployment/infrastructure/*.yaml` 템플릿은 byte-level 보존됩니다. 이미 배포된 CloudFormation 스택은 변경 없이 그대로 동작합니다.

## 새 환경 설정 방법

```bash
# 1. uv 설치 (미설치 시)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. ccwb 클론 + 의존성 설치
git clone <repository-url>
cd ccwb
uv sync --all-packages
cd web/frontend && yarn install && cd ../..

# 3. 프로덕션 빌드 + 위자드 실행
make build
uv run ccwb
```
