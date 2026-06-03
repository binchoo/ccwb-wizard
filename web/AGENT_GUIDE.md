# AI Agent Guide

ccwb Config를 프로그래밍으로 다루는 방법.

## 핵심 계약

1. Config 텍스트 파일(`~/.ccwb/profiles/<name>.json`)이 사람·UI·agent 공통의 진실의 원천이다.
2. 같은 Config로 시스템이 결정성 있게 동작한다.
3. agent의 구체적 구현 방식(어떤 언어·도구·인터페이스)은 명세하지 않는다.

## Config 형식

```json
{
  "schema_version": "3.0",
  "profile_name": "my-profile",
  "aws_region": "us-east-1",
  "stack_base_name": "claude-code-auth",
  "provider": { "type": "okta", "domain": "company.okta.com", "client_id": "..." },
  "model_id": "us.anthropic.claude-sonnet-4-6",
  "cross_region_profile": "us",
  "source_region": "us-east-1",
  "inference_profiles": { "opus": null, "sonnet": null, "haiku": null },
  "bedrock_logging": { "destination": "cloudwatch", "retention_days": 90 },
  "quota": null,
  "distribution": null,
  "enable_codebuild_windows": false,
  "enable_cowork_3p": true,
  "enable_cc_telemetry": false,
  "tags": {}
}
```

## 가능한 값 카탈로그

### Provider types
`okta`, `azure`, `cognito`, `auth0`, `generic`

### Distribution types
`presigned-s3`, `landing-page`, 또는 `null` (비활성)

### Bedrock Logging destination
`cloudwatch`, `s3`, `both` (둘 다 끄는 건 무효)

### Models
`ccwb/.kiro/specs/web-config-wizard/scenarios.md` §3 참조. 또는 `ccwb_domain.bedrock_models.CLAUDE_MODELS`에서 프로그래밍으로 조회.

## 능력 요약

| 능력 | 무엇이 보장되는가 |
|------|----------------|
| Config 읽기 | schema_version 포함 자기 기술적 JSON, 에러 시 명확한 오류 |
| 카탈로그 조회 | 5종 IdP + 2종 distribution + 12 models (일관된 단일 출처) |
| Config 수정 저장 | 동시성 안전, raw secret 미포함 보장, 위자드에서 즉시 인식 |
| materialize 미리보기 | CFN 스택 계획 + settings.json 템플릿 + ~/.aws/config, 결정성 |
| 가벼운 환경 | UI·backend 없이도 위 능력 모두 사용 가능 |

## 시작하기 (Python 예시)

```python
from ccwb_domain.config import Config
from ccwb_domain.materialize import materialize

# 읽기
config = Config.load(Path.home() / ".ccwb/profiles/default.json")

# 수정
config.model_id = "us.anthropic.claude-opus-4-7"
config.save(Path.home() / ".ccwb/profiles/default.json")

# 미리보기
artifacts = materialize(config)
print(artifacts.to_review_dict())
```

단, 이 Python 예시는 하나의 방법이지 유일한 방법이 아닙니다. JSON 파일을 직접 편집해도 위자드가 인식합니다.
