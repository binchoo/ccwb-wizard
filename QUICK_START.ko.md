# 빠른 시작 가이드 (한국어)

**Claude Code with Amazon Bedrock (ccwb)** 를 web 위자드(`uv run ccwb`)로 배포하기 위한 액션 중심 가이드입니다.

- 이 문서는 **무엇을 순서대로 실행해야 하는지**에 집중합니다. 각 옵션의 상세 설명은 [영문 QUICK_START](QUICK_START.md)를 참고하세요.
- 독자는 둘로 나뉩니다. **IT 어드민**(인프라 배포)과 **엔드 유저**(개발자, 패키지 설치). 본인 역할의 섹션부터 읽으세요.

> 0~6단계는 반드시 성공해야 하는 통제된 경로(Critical Path)입니다. 7~8단계와 "선택"으로 표시된 항목은 그 다음에 추가하면 됩니다.

---

## IT 어드민 — 배포 액션 순서

```
0. IdP 설정          (Okta / Entra ID / Auth0 / Google / Cognito / generic OIDC)
        ▼
1. 사전 도구 설치     (uv, Node.js + yarn, AWS CLI v2, Git)
        ▼
2. 코드 받기 + 빌드   (uv sync --all-packages → make build)
        ▼
3. AWS 인증          (aws sso login / export AWS_PROFILE → 확인)
        ▼
4. 위자드 실행        (uv run ccwb → 브라우저 자동 오픈)
        ▼
5. 위자드 입력        (프로필 → AWS → IdP → 인프라 → 모델 → 로깅 → 검토)
        ▼
6. 배포 → 패키징 → 테스트   (위자드 10단계에서 일괄 수행)
        ▼
7. 엔드 유저에게 배포  (presigned URL 또는 zip 수동 전달)
```

### 0단계 — IdP 먼저 설정하기

위자드는 **provider domain(또는 issuer URL)과 client ID**를 요구합니다. 위자드 실행 전에 IdP를 먼저 준비하세요.

| 사용하는 IdP | 설정 가이드 |
|---|---|
| **Okta** | [okta-setup.md](assets/docs/providers/okta-setup.md) |
| **Microsoft Entra ID (Azure AD)** | [microsoft-entra-id-setup.md](assets/docs/providers/microsoft-entra-id-setup.md) |
| **Auth0** | [auth0-setup.md](assets/docs/providers/auth0-setup.md) |
| **Google** | [google-setup.md](assets/docs/providers/google-setup.md) |
| **AWS Cognito User Pool** | [cognito-user-pool-setup.md](assets/docs/providers/cognito-user-pool-setup.md) |
| **PingFederate / Keycloak / 기타 generic OIDC** | [generic-oidc-setup.md](assets/docs/providers/generic-oidc-setup.md) |

각 가이드에서 애플리케이션을 만들고, redirect URI를 `http://localhost:8400/callback`로 설정하고, PKCE를 켠 뒤 **provider domain**과 **client ID**를 확보하세요.

> **Google은 generic OIDC가 아니라 전용 경로입니다.** Google "Desktop app" 클라이언트는 PKCE와 함께 `client_secret`을 토큰 교환에 요구합니다. **Desktop app** 클라이언트를 만들고, 위자드에는 **Client ID만** 입력합니다. `client_secret`은 패키지에 포함되지 않으며, 각 엔드 유저가 설치 후 자신의 OS 키링에 한 번 주입합니다(엔드 유저 [3단계](#3단계--google-사용-시에만-client-secret-등록) 참고).

### 1단계 — 사전 도구 설치

| 도구 | 용도 | 설치 |
|---|---|---|
| **Python 3.10–3.12** | 위자드 백엔드 런타임 | python.org 또는 패키지 매니저 |
| **[uv](https://docs.astral.sh/uv/)** | Python 패키지/워크스페이스 매니저 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js ≥ 18 + yarn** | 위자드 프론트엔드 빌드 | `npm install -g yarn` |
| **AWS CLI v2** | AWS 인증 및 검증 | [AWS 문서](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |
| **Git** | 저장소 클론 | 패키지 매니저 |

AWS 계정에는 CloudFormation, IAM(OIDC Provider/역할), Bedrock model-invocation 로깅, CloudWatch 생성 권한이 필요합니다. 대상 리전에서 Amazon Bedrock 모델 접근이 활성화되어 있어야 합니다.

### 2단계 — 코드 받기 + 빌드

```bash
git clone https://github.com/binchoo/ccwb-wizard
cd ccwb-wizard

uv sync --all-packages    # Python 워크스페이스 의존성 설치
make build                # 프론트엔드 빌드 → 백엔드 static에 복사
```

`make build`가 끝나면 `Build complete. Run 'uv run ccwb' to start.` 메시지가 출력됩니다.

### 3단계 — AWS 인증

위자드는 **관리자** 자격증명으로 AWS API를 호출합니다. 실행 전에 유효한 세션을 준비하세요.

```bash
aws sso login --profile <관리자-프로필>
export AWS_PROFILE=<관리자-프로필>

aws sts get-caller-identity   # 위자드 실행 전 반드시 확인
```

> **가장 흔한 실패**: 만료된 AWS 환경변수가 우선순위를 가로챕니다. `AWS_ACCESS_KEY_ID`가 export되어 있는데 만료됐다면 boto3가 자격증명 파일로 폴백하지 않습니다. 문제 시 `unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN` 후 재시도하세요.

### 4단계 — 위자드 실행

```bash
uv run ccwb
```

백엔드가 **localhost 전용**(`127.0.0.1:8400`)으로 뜨고 브라우저가 자동으로 열립니다. 위자드 10단계에 도달하기 전까지는 AWS에 아무것도 배포되지 않으며, 입력은 `~/.ccwb/profiles/<name>.json`에만 저장됩니다.

### 5단계 — 위자드 입력 (11개 페이지)

| 페이지 | 이름 | 입력 내용 | Critical Path |
|---|---|---|---|
| 0 | 프로필 | 신규/편집/복제 + 프로필명 | 필수 |
| 1 | AWS 환경 | 배포용 named profile + 리전 | 필수 |
| 2 | Identity Provider | OIDC IdP + 연결 테스트 + attribution 매핑 | 필수 |
| 3 | 인프라 이름 | CFN 스택 base name | 필수 |
| 4 | Bedrock 모델 | 모델 tier + CRIS 프로파일 + source region | 필수 |
| 5 | 로깅 & 할당량 | Bedrock invocation 로깅 + quota(선택) | 로깅 필수 |
| 6 | 배포 방식 | presigned S3 / landing page | 선택 |
| 7 | 추가 기능 | Windows 빌드, CoWork 3P | 선택 |
| 8 | 리소스 태그 | 전체 CFN 스택 태그 | 선택 |
| 9 | 검토 및 저장 | 설정 검토 + materialize 미리보기 + 저장 | 필수 |
| 10 | 배포 및 테스트 | 배포 → 패키징 → 테스트 → 배포 | 필수 |

**2단계(IdP) 핵심**: provider domain과 client ID를 입력합니다. Okta/Entra/Auth0/Cognito는 자동 감지되고, **Google·generic OIDC는 수동 선택**합니다. attribution 매핑(IdP claim → `user`/`team`/`dept`)은 **매 인증 시점에 동적 적용**되어, 조직 변경이 재패키징 없이 다음 로그인에 반영됩니다. Google 경로는 여기서 **Client ID만** 입력합니다.

### 6단계 — 배포 → 패키징 → 테스트 (위자드 10단계)

10단계에서 아래 순서로 실행합니다.

1. **Deploy** — CFN 스택을 의존성 순서로 배포(기존 스택 인식, 중복 OIDC/로깅 skip). 5~15분 소요.
2. **Package** — `credential-process` 바이너리 + `config.json` + `install.sh`/`install.bat` + `settings.json` 템플릿을 zip으로 묶음. macOS는 빌드 전 `uname -m`으로 아키텍처 확인(`arm64` → `macos-arm64`, `x86_64` → `macos-intel`).
3. **Test** — 엔드 유저 설치를 시뮬레이션(OIDC 인증 → AWS 자격증명 발급 → Bedrock 접근 확인). **이 테스트 통과가 Critical Path의 최종 관문입니다.**

### 7단계 — 엔드 유저에게 배포 (선택 인프라)

- **수동 전달**: `dist/` 폴더를 zip으로 묶어 이메일/사내 공유. 추가 인프라 불필요.
- **Presigned S3 URL**: 위자드 **Distribute**가 S3 업로드 후 시간 제한 URL(기본 48시간) 생성.
- **인증 Landing Page**: SSO 로그인 기반 셀프서비스 다운로드 포털. 감사 추적이 필요한 대규모 조직용.

---

## 엔드 유저 — 온보딩 액션 순서

배포받은 패키지를 본인 머신에서 한 번만 설정하면 됩니다. **AWS 지식은 필요 없습니다.**

```
1. 패키지 압축 해제
        ▼
2. 인스톨러 실행        (macOS/Linux: install.sh, Windows: install.bat)
        ▼
3. (Google 사용 시만) client secret을 OS 키링에 등록   ← 1회
        ▼
4. 첫 로그인           (credential-process --profile <name> → 브라우저 오픈)
        ▼
5. Claude Code 실행    (자동으로 Bedrock 경로 사용)
```

### 1~2단계 — 압축 해제 후 인스톨러 실행

```bash
# macOS / Linux
./install.sh

# Windows (압축 푼 폴더에서)
install.bat
```

인스톨러는 `credential-process` 바이너리 배치, `~/.aws/config`에 `[profile <name>]` 작성, `~/.claude/settings.json` 템플릿 설치를 수행합니다. **Claude Code 자체는 설치하지 않으므로** 미리 설치되어 있어야 합니다. `aws`/`claude`가 `PATH`에 없으면 안내 메시지를 출력합니다.

### 3단계 — (Google 사용 시에만) client secret 등록

다른 IdP는 PKCE만 사용하므로 이 단계를 건너뜁니다. Google은 client secret이 패키지에 포함되지 않으므로 본인 OS 보안 저장소에 한 번 주입합니다.

```bash
# 대화형 — 입력값은 화면/히스토리에 남지 않음
credential-process --set-client-secret --profile <name>
```

MDM/스크립트 배포 시에는 인자 대신 환경변수로 전달하세요(프로세스 목록·히스토리 노출 방지).

```bash
CCWB_CLIENT_SECRET="GOCSPX-..." credential-process --set-client-secret --profile <name>
```

> secret은 OS 보안 저장소(macOS Keychain, Windows Credential Manager, freedesktop Secret Service, KWallet)에만 저장되며, 비보안 백엔드에서는 실행을 거부합니다.

### 4단계 — 첫 로그인

```bash
credential-process --profile <name>
```

브라우저로 회사 계정 로그인을 마치면, 임시 AWS 자격증명이 캐시되고 attribution "매직 헤더"가 `~/.claude/settings.json`에 기록되며 본인의 `user`/`team`/`dept` 값이 출력됩니다. AWS 자격증명 자체는 화면에 출력되지 않습니다.

### 5단계 — Claude Code 실행

이후에는 Claude Code를 평소처럼 실행하면 됩니다. `settings.json`의 env 블록이 모든 요청을 Bedrock 경로(`CLAUDE_CODE_USE_BEDROCK=1`)로 라우팅합니다. 모델 설정은 위자드가 이미 고정해 두었으므로 추가 작업이 없습니다.

### 팀/부서가 바뀌었을 때

attribution claim은 로그인 시점에 캐시되므로, IdP에서 조직 정보를 바꿔도 **재인증 전까지는 반영되지 않습니다.** 어드민이 IdP에서 그룹/부서를 변경한 뒤, 해당 사용자에게 아래 실행을 요청하세요.

```bash
credential-process --profile <name> --refresh-identity
```

캐시(자격증명 + ID 토큰)를 비우고 새로 로그인하여 바뀐 claim을 받아오고 매직 헤더를 갱신합니다. 완료 후 Claude Code를 재시작하면 다음 사용량부터 새 팀/부서로 집계됩니다. 전체 멤버 라이프사이클 절차는 [User Lifecycle Runbook](web/binaries/credential_provider/USER_LIFECYCLE_RUNBOOK.md)을 참고하세요.

---

## 문제 해결

| 증상 | 조치 |
|---|---|
| 위자드가 AWS 자격증명 오류 (그런데 `aws sts get-caller-identity`는 성공) | 만료된 환경변수가 원인. `unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN` 후 재실행 |
| 브라우저가 안 열림 / 위자드 접속 불가 | `http://localhost:8400` 직접 접속. 8400 포트 점유 시 점유 프로세스 종료 |
| `make build` 프론트엔드 단계 실패 | `node -v`(≥18), `yarn -v` 확인. `make clean` 후 재빌드 |
| 엔드 유저 `Exec format error` | 바이너리 아키텍처 불일치. 어드민이 올바른 macOS 타겟으로 재빌드 후 재배포 |
| Google `invalid_client` | 키링의 client secret 누락/오류. `--set-client-secret`로 재등록 |

상세 설명·전체 옵션·런타임 시퀀스 다이어그램은 [영문 QUICK_START](QUICK_START.md)를 참고하세요.
