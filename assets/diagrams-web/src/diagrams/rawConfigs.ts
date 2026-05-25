// 실제 ccwb package가 생성하는 산출물 내용 (raw)
// 출처: source/claude_code_with_bedrock/cli/commands/package.py
//   - _create_settings()    : settings.json 템플릿
//   - _create_installer()   : install.sh 안의 ~/.aws/config 작성 부분
//   - _create_config_json() : config.json (멀티프로파일 메타데이터)

// 산출물 zip — claude-code-package.zip 안의 파일 목록 (v3.0+ Bedrock-native logging)
export const RAW_ZIP_MANIFEST = `claude-code-package/
├── install.sh                       # POSIX 인스톨러
├── install.bat                      # Windows 인스톨러
├── README.md
├── config.json                      # 프로파일 메타데이터
├── credential-process-macos-arm64   # 인증 헬퍼 (PyInstaller)
├── credential-process-macos-intel
├── credential-process-linux-x64
├── credential-process-linux-arm64
├── credential-process.exe           # Windows (Nuitka via CodeBuild)
└── claude-settings/
    └── settings.json                # __ANTHROPIC_CUSTOM_HEADERS__ placeholder 포함`;


// claude-settings/settings.json — install.sh가 placeholder 치환 후 ~/.claude/settings.json에 배치
// v3.0+: Bedrock-native logging. ANTHROPIC_CUSTOM_HEADERS가 매직 헤더를 통해 사용자 attribution 전달.
export const RAW_CLAUDE_SETTINGS = `{
  "env": {
    "AWS_REGION": "us-east-1",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_PROFILE": "ClaudeCode",
    "AWS_CREDENTIAL_PROCESS": "__CREDENTIAL_PROCESS_PATH__ --profile ClaudeCode",
    "ANTHROPIC_MODEL": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "ANTHROPIC_CUSTOM_HEADERS": "__ANTHROPIC_CUSTOM_HEADERS__",
    "CLAUDE_CODE_USE_MANTLE": "0"
  }
}`;


// install.sh 실행 후 ~/.claude/settings.json — placeholder가 실제 값으로 치환된 결과 (v3.0+)
export const RAW_CLAUDE_SETTINGS_RESOLVED = `{
  "env": {
    "AWS_REGION": "us-east-1",
    "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_PROFILE": "ClaudeCode",
    "AWS_CREDENTIAL_PROCESS": "/Users/alice/claude-code-with-bedrock/credential-process --profile ClaudeCode",
    "ANTHROPIC_MODEL": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "ANTHROPIC_CUSTOM_HEADERS": "X-Amzn-Bedrock-Request-Metadata: {\\"user\\":\\"alice@example.com\\",\\"team\\":\\"blue\\",\\"dept\\":\\"engineering\\"}",
    "CLAUDE_CODE_USE_MANTLE": "0"
  }
}`;

// ~/.aws/config — install.sh가 추가하는 stanza (메인 + collector companion 프로파일)
// 출처: package.py:2235-2260 cat >> ~/.aws/config
export const RAW_AWS_CONFIG = `[profile ClaudeCode]
credential_process = /Users/alice/claude-code-with-bedrock/credential-process --profile ClaudeCode
region = us-east-1

[profile ClaudeCode-collector]
credential_process = /Users/alice/claude-code-with-bedrock/credential-process --profile ClaudeCode
region = us-east-1
`;


// config.json — 프로파일 메타데이터. install.sh가 ~/claude-code-with-bedrock/로 그대로 복사.
// 출처: package.py:1908-1981 _create_config_json()
// credential-process가 런타임에 이 파일을 읽어 OIDC 설정과 federation type을 결정.
export const RAW_CONFIG_JSON = `{
  "ClaudeCode": {
    "provider_domain": "company.okta.com",
    "client_id": "0oa1abc2def3...",
    "aws_region": "us-east-1",
    "provider_type": "okta",
    "credential_storage": "keyring",
    "cross_region_profile": "us",
    "federated_role_arn": "arn:aws:iam::123456789012:role/ClaudeCodeFederatedRole",
    "federation_type": "direct",
    "max_session_duration": 43200,
    "selected_model": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "quota_api_endpoint": "https://quota-api.example.com",
    "quota_fail_mode": "open",
    "quota_check_interval": 30
  }
}`;



// (collector-config.yaml은 v3.0에서 제거됨 — Bedrock 자체 로깅이 OTEL Collector를 대체.)
export const RAW_COLLECTOR_CONFIG = `# OTEL Collector sidecar removed in v3.0.
# Bedrock model invocation logging now writes directly to S3 + CloudWatch Logs.
`;
