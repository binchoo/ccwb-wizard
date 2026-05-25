# Implementation Plan: bedrock-native-logging

## Overview

본 구현은 OTEL 파이프라인 통째 제거와 Bedrock-native logging 도입을 동시에 수행한다. 핵심 제약은 **ccwb 5단계 워크플로우(`init` → `configure` → `deploy` → `package` → `distribute`)가 변경 없이 동작**해야 한다는 점이다.

작업은 의존성 순서로 5단계 phase로 나눈다.

- **Phase 1: 사전 검증** — Bedrock 매직 헤더가 본인 셋업의 Cognito 흐름에서 동작함을 확인.
- **Phase 2: 클라이언트 측 메커니즘** — credential-process 새 서브명령, install.sh 치환, settings.json 템플릿.
- **Phase 3: 서버 측 인프라** — bedrock-logging CFN 신설, quota_monitor 데이터 소스 교체, dashboard 갱신.
- **Phase 4: OTEL 제거** — Phase 2~3 검증 완료 후. OTEL 코드/CFN/문서 삭제.
- **Phase 5: 문서화 및 마이그레이션 도구** — README/QUICK_START/diagrams, `--remove-otel-stacks` 명령.

## Tasks

### Phase 1 — 사전 검증

- [x] 1.1 Bedrock 매직 헤더 동작 검증 (Cognito 경로)
  - 본인 PoC 셋업에서 `ANTHROPIC_CUSTOM_HEADERS`로 호출 → invocation log 도달 확인
  - 결과: `.kiro/specs/bedrock-native-logging/poc-results.md` 참조 (1차+2차 evidence PASS)
  - _Validates: Design §Overview 핵심 결정 (Bedrock-native 동작 가능성)_

### Phase 2 — 클라이언트 측 메커니즘

- [x] 2.1 `credential-process --get-bedrock-metadata-headers` 서브명령 추가
  - `source/credential_provider/__main__.py`의 argparse에 추가, 분기 처리 신규
  - `source/credential_provider/bedrock_metadata.py` 신규 모듈 (sanitize_for_bedrock, build_metadata_from_jwt, build_header_line)
  - JWT claim → 매직 헤더 변환은 mapping 없이 passthrough (OIDC 보일러플레이트만 deny-list로 제거)
  - 추가로 dashboard 호환용 fixed alias 3개(`user`/`team`/`dept`)를 가장 흔한 IdP claim에서 additive 채움
  - 단위 테스트 32개 PASS (`source/tests/credential_provider/test_bedrock_metadata.py`)
  - _Validates: Design §Components — credential-process 인터페이스, §Correctness Property 2_

- [x] 2.2 프로파일 schema에 `bedrock_logging_destination` 필드 추가
  - `source/claude_code_with_bedrock/config.py`의 Profile dataclass에 신규 필드 추가
  - 매핑 추상화는 도입하지 않음 — JWT claim은 credential-process가 install 시점에 OIDC 보일러플레이트만 빼고 그대로 직렬화
  - 기존 프로파일과 schema 호환 검증 PASS
  - _Validates: Design §Components — `ccwb init` 변경 지점_

- [x] 2.3 `package.py` settings.json 템플릿 신규 형식 적용
  - OTEL_* env, otelHeadersHelper 제거
  - `__ANTHROPIC_CUSTOM_HEADERS__` placeholder + `CLAUDE_CODE_USE_MANTLE=0` 추가
  - _Validates: Design §Data Models — settings.json (변경 후)_

- [x] 2.4 `install.sh` 치환 스니펫 추가 (POSIX)
  - `_create_installer()`에 `credential-process --get-bedrock-metadata-headers` 호출 + sed 치환
  - 인증 실패 시 빈 메타데이터 fallback
  - _Validates: Design §Components — install.sh 변경, §Correctness Property 1_

- [x] 2.5 `install.bat` 치환 스니펫 추가 (Windows)
  - `_create_windows_installer()`에 PowerShell 동등 패턴 추가
  - 환경변수 경유로 cmd.exe quoting 회피
  - _Validates: Design §Components — install.sh 변경 (Windows 동등 지원)_

- [ ] 2.6 End-to-end 클라이언트 흐름 검증 (사용자 수동 단계)
  - `wave5-verification.md` 절차 6단계 본인이 PoC 환경에서 실행 후 PASS 마킹
  - 본 task는 코드 변경 없음 — 검증 단계
  - _Validates: Design §Correctness Property 1, 3, 4_

### Phase 3 — 서버 측 인프라

- [x] 3.1 `bedrock-logging.yaml` CFN 템플릿 신설
  - 11 resources, 5 outputs. CW Logs / S3 / both destination 지원
  - 4개 metric filter (input/output tokens by user, invocation count, untagged invocations)
  - YAML syntax 검증 PASS
  - _Validates: Design §Components — Bedrock Model Invocation Logging CFN_

- [x] 3.2 Bedrock logging 활성화 custom resource Lambda
  - `lambda-functions/bedrock_logging_config/index.py` 신규 작성
  - PutModelInvocationLoggingConfiguration / Delete 처리
  - _Validates: Design §Components — bedrock-logging.yaml CFN_

- [x] 3.3 `quota_monitor` Lambda를 GetMetricData로 전환
  - PromQL → boto3 cloudwatch.get_metric_data
  - 함수 시그니처 보존 (`fetch_usage_from_promql` 별칭 유지)
  - 단위 테스트 5개 PASS
  - _Validates: Design §Components — quota_monitor Lambda 변경, §Correctness Property 5_

- [x] 3.4 `claude-code-dashboard.yaml` 데이터 소스 교체
  - 기존 PromQL 위젯 통째 → ClaudeCodeBedrock namespace 위젯
  - 9개 위젯 (single-value KPI 4 + timeSeries 4 + 헤더 1)
  - YAML syntax 검증 PASS
  - _Validates: Design §Architecture — 변경 후 다이어그램, §Components — dashboard 스택_

- [x] 3.5 `bedrock-logging` 스택을 `ccwb deploy` orchestration에 추가
  - `deploy.py`의 stack_arg 분기 + 배포 분기 추가
  - 기존 monitoring/networking/analytics 분기는 deploy 대상에서 제외 (Phase 4에서 파일 삭제)
  - dashboard 분기 파라미터 갱신 (ProfileName, MetricNamespace)
  - _Validates: Design §Architecture — CFN 스택 구조 9→5, §Correctness Property 6_

### Phase 4 — OTEL 제거 (Phase 2~3 검증 완료 후)

- [x] 4.1 OTEL helper 코드 및 테스트 삭제
- [x] 4.2 `package.py`에서 OTEL helper / otelcol 빌드 분기 제거
- [x] 4.3 OTEL 관련 CFN 템플릿 삭제 (networking, otel-collector, analytics-pipeline)
- [x] 4.4 `ccwb init` 대화 흐름에서 OTEL 옵션 제거
- [x] 4.5 `ccwb configure`가 OTEL 모드 선택을 거부 (init과 같은 흐름)

### Phase 5 — 문서화 및 마이그레이션 도구

- [x] 5.1 `ccwb deploy --remove-otel-stacks` 마이그레이션 명령
- [x] 5.2 README, QUICK_START 갱신
- [x] 5.3 다이어그램 (`assets/diagrams-web/`) 갱신
  - `userNodes.ts`: rt-otelhelper, rt-sidecar, fs-collector-config 노드 제거
  - `userEdges.ts`: OTEL 관련 엣지 제거, ⑫ ANTHROPIC_CUSTOM_HEADERS → $.requestMetadata 흐름으로 갱신
  - `rawConfigs.ts`: settings.json v3.0 형태(매직 헤더 + CLAUDE_CODE_USE_MANTLE=0), RAW_COLLECTOR_CONFIG는 stub
  - `npm run build` PASS (204 modules transformed)
  - _Validates: Design §Architecture — 변경 후 다이어그램 sync_
- [x] 5.4 마이그레이션 가이드 문서
- [x] 5.5 통합 테스트 스위트 작성
  - `source/tests/integration/test_bedrock_native_e2e.py` (T-INT-1~4 매핑, opt-in 게이트, 비용 예산 가드)
  - `source/tests/integration/test_migration.py` (T-MIG-1: `_remove_otel_stacks` 의존성 순서 정적 검증)
  - `source/tests/integration/conftest.py` (AWS_INTEGRATION_TEST opt-in, AWS_INTEGRATION_TEST_BUDGET=$5 default)
  - `pyproject.toml`에 `integration`/`slow` pytest marker 등록
  - opt-in 미설정 시 6/6 skip 동작 확인 PASS, 단위 테스트 25/25 PASS 회귀 없음
  - _Validates: Design §Testing Strategy — T-INT-1~4 + T-MIG-1_

## Task Dependency Graph

```json
{
  "waves": [
    {"wave": 1, "name": "사전 검증", "tasks": ["1.1"]},
    {"wave": 2, "name": "기반 컴포넌트", "tasks": ["2.2", "3.1"]},
    {"wave": 3, "name": "핵심 메커니즘", "tasks": ["2.1", "3.2"]},
    {"wave": 4, "name": "통합 클라이언트+서버", "tasks": ["2.3", "2.4", "2.5", "3.3", "3.4"]},
    {"wave": 5, "name": "오케스트레이션 + E2E 검증", "tasks": ["2.6", "3.5"]},
    {"wave": 6, "name": "OTEL 제거", "tasks": ["4.1", "4.2", "4.3"]},
    {"wave": 7, "name": "온보딩 흐름 정리", "tasks": ["4.4", "4.5"]},
    {"wave": 8, "name": "마이그레이션 + 문서", "tasks": ["5.1", "5.2", "5.3", "5.4"]},
    {"wave": 9, "name": "통합 테스트", "tasks": ["5.5"]}
  ]
}
```

## Notes

### Out of Scope

- Cowork (Claude Desktop) 통합 — 별도 spec
- Bedrock Cost Explorer (CUR) 통합 — 별도 spec
- W3C distributed tracing — Anthropic SDK 변경 대기
- Landing Page distribution 검증 — 별도
- GovCloud 검증 — commercial partition 검증 후 별도

### 작업 순서 권장

병렬 갈래:
- **클라이언트 갈래**: 2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6
- **서버 갈래**: 3.1 → 3.2 → 3.3 → 3.4 → 3.5

Phase 4의 OTEL 코드 통째 삭제는 Phase 2.6 + 3.5 검증 PASS 후에만 시작.
