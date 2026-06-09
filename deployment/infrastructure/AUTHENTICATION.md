# Authentication Architecture

Claude Code with Bedrock(CCWB)는 조직의 기존 인프라 상황에 따라 세 가지 인증 경로를 제공합니다.
어떤 경로를 선택하든 최종 결과는 동일합니다: 인증된 사용자가 Amazon Bedrock API를 호출할 수 있는 임시 AWS 자격증명을 받습니다.

---

## 어떤 경로를 선택해야 하나요?

### 경로 1: 기존 IdP가 있고, 그대로 사용하겠다

> "우리 회사는 이미 Okta/Azure AD/Auth0를 쓰고 있다. 별도 사용자 관리 없이 기존 SSO로 Bedrock 접근을 열어주고 싶다."

**구성**: OIDC IdP → Direct STS Federation (`AssumeRoleWithWebIdentity`)

- CFN 스택: `bedrock-auth-okta.yaml`, `bedrock-auth-azure.yaml`, `bedrock-auth-auth0.yaml`
- Cognito 불필요 (User Pool도, Identity Pool도 없음)
- 세션 시간: 최대 12시간
- 가장 단순한 구성, 추가 AWS 서비스 비용 $0

**전제 조건**: IdP 관리자가 OIDC 앱을 등록해줄 수 있어야 합니다.

---

### 경로 2: IdP가 없고, 지금부터 사용자를 관리하겠다

> "사내 IdP가 없거나 연동이 불가능하다. CCWB 전용 사용자 계정을 AWS에서 직접 관리하겠다."

**구성**: Cognito User Pool(사용자 저장소) + Cognito Identity Pool(자격증명 교환)

- CFN 스택: `cognito-user-pool-setup.yaml` + `cognito-identity-pool.yaml` (AuthProviderType=CognitoUserPool)
- CUP이 사용자 가입/로그인/MFA를 처리, CIP가 CUP 토큰을 AWS 자격증명으로 변환
- 세션 시간: 최대 8시간
- 비용: CUP MAU 요금 발생 (10,000 MAU 무료, 이후 $0.015/MAU), CIP는 무료

**전제 조건**: 없음. AWS 계정만 있으면 됩니다.

---

### 경로 3: 기존 IdP도 쓰고, 자체 가입 유저도 받겠다

> "Kakao/Google 같은 소셜 로그인도 지원하고, 이메일 가입 유저도 동시에 받고 싶다.
> 하나의 통합 인증 허브로 모든 유저를 관리하겠다."

**구성**: Cognito User Pool(통합 IdP 허브) + Cognito Identity Pool(자격증명 교환)

```
외부 IdP (Kakao, Google 등) ─┐
                              ├→ CUP (통합) → CIP → Bedrock Role
자체 가입 유저 (email/pw) ────┘
```

- CFN 스택: `cognito-user-pool-setup.yaml` + `cognito-identity-pool.yaml` (AuthProviderType=CognitoUserPool)
- CUP이 외부 IdP를 Federated Provider로 수용하면서 자체 유저도 동시 관리
- 세션 시간: 최대 8시간
- 비용: CUP MAU 요금 (소셜/자체 로그인 10,000 MAU 무료, SAML/OIDC 페더레이션 50 MAU 무료), CIP 무료

**전제 조건**: CUP에 외부 IdP를 Federated Identity Provider로 등록해야 합니다.

---

## 비교 요약

| | 경로 1: Direct STS | 경로 2: CUP + CIP | 경로 3: CUP(허브) + CIP |
|---|---|---|---|
| **고객 니즈** | 기존 IdP 그대로 사용 | IdP 없이 신규 시작 | 복수 인증 소스 통합 |
| **사용자 저장소** | 외부 IdP | CUP | CUP + 외부 IdP |
| **AWS 인프라** | IAM OIDC Provider + Role | CUP + CIP + Role | CUP + CIP + Role |
| **세션 시간** | 최대 12시간 | 최대 8시간 | 최대 8시간 |
| **Cognito 비용** | $0 | CUP MAU 요금 | CUP MAU 요금 |
| **설정 복잡도** | 낮음 | 중간 | 높음 |
| **IdP 관리자 협조** | 필요 (앱 등록) | 불필요 | 부분 필요 |

---

## 인증 흐름 상세

세 경로 모두 최종 사용자 관점에서는 동일합니다:

1. `credential_process` 바이너리가 AWS CLI/SDK의 자격증명 프로세스로 등록됨
2. Claude Code가 Bedrock 호출 시 SDK가 `credential_process`를 자동 실행
3. 브라우저 기반 OIDC 로그인 → ID Token 획득
4. 토큰을 AWS 임시 자격증명으로 교환 (경로에 따라 Direct STS 또는 CIP)
5. 자격증명 캐시 → 만료 전까지 재사용

```
┌─────────────────────────────────────────────────────┐
│  Claude Code CLI                                    │
│    ↓ (Bedrock API 호출 시)                          │
│  AWS SDK → credential_process 실행                  │
│    ↓                                                │
│  ┌─────────────────────────────────────────────┐    │
│  │ credential_process                          │    │
│  │   1. 캐시 확인 (유효하면 즉시 반환)         │    │
│  │   2. 브라우저 OIDC 로그인                   │    │
│  │   3. ID Token 획득                          │    │
│  │   4a. Direct STS: AssumeRoleWithWebIdentity │    │
│  │   4b. CIP: GetId → GetCredentialsForIdentity│    │
│  │   5. 임시 자격증명 반환 (JSON)              │    │
│  └─────────────────────────────────────────────┘    │
│    ↓                                                │
│  Bedrock API 호출 (서명된 요청)                     │
└─────────────────────────────────────────────────────┘
```

---

## CFN 스택 매핑

| 스택 파일 | 용도 | 해당 경로 |
|-----------|------|-----------|
| `bedrock-auth-okta.yaml` | Okta OIDC + Direct STS | 경로 1 |
| `bedrock-auth-azure.yaml` | Azure AD + Direct STS | 경로 1 |
| `bedrock-auth-auth0.yaml` | Auth0 + Direct STS | 경로 1 |
| `bedrock-auth-generic.yaml` | 범용 OIDC + Direct STS | 경로 1 |
| `cognito-user-pool-setup.yaml` | CUP 생성 + 외부 IdP 연동 | 경로 2, 3 |
| `cognito-identity-pool.yaml` | CIP + Role 매핑 | 경로 2, 3 |
| `cognito-custom-domain-cert.yaml` | CUP 커스텀 도메인 인증서 | 경로 2, 3 (선택) |
