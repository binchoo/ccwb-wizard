#!/usr/bin/env bash
# Wave 1 / Task 1.1 검증 스크립트
# Bedrock 매직 헤더 X-Amzn-Bedrock-Request-Metadata가 본인의 Cognito 흐름에서
# model invocation log의 requestMetadata 필드에 도달하는지 확인한다.
#
# 출력: poc-results.md 에 검증 결과 기록.
#
# 전제:
#   - ccwb 셋업 완료 (~/.ccwb/profiles/ccwb-dev-us-east-1.json 존재)
#   - claude CLI가 PATH에 있고 첫 OIDC 인증 완료된 상태
#   - aws CLI 사용 가능 (현재 셸의 자격증명으로 logs:DescribeLogGroups 가능)

set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
SPEC_DIR="$(cd "$HERE/.." && pwd)"
RESULTS="$SPEC_DIR/poc-results.md"
REGION="${AWS_REGION:-us-east-1}"
PROBE="slim-poc-$(date +%Y%m%d-%H%M%S)"

echo "=== Wave 1 / Task 1.1 검증 시작 ===" | tee "$RESULTS"
echo "" | tee -a "$RESULTS"
echo "## 환경" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"
echo "- region: \`$REGION\`" | tee -a "$RESULTS"
echo "- probe: \`$PROBE\`" | tee -a "$RESULTS"
echo "- 시각: $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"


# ===== Step 1: Bedrock invocation logging 활성 상태 확인 =====
echo "## Step 1: Bedrock invocation logging 활성 상태" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"

LOGGING_CFG=$(aws bedrock get-model-invocation-logging-configuration \
  --region "$REGION" --output json 2>&1 || echo '{"error":"failed"}')
echo "$LOGGING_CFG" | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

# logging 비활성이면 abort
if echo "$LOGGING_CFG" | grep -q '"loggingConfig": null' \
   || echo "$LOGGING_CFG" | grep -q '"error"'; then
  echo "**결과: Bedrock invocation logging 비활성 또는 권한 없음. 활성화 후 재실행 필요.**" \
    | tee -a "$RESULTS"
  echo "" | tee -a "$RESULTS"
  echo "활성화 명령 예시 (CW Logs 대상):" | tee -a "$RESULTS"
  echo '```sh' | tee -a "$RESULTS"
  echo "aws bedrock put-model-invocation-logging-configuration --region $REGION --logging-config '{\"cloudWatchConfig\":{\"logGroupName\":\"/aws/bedrock/modelinvocations\",\"roleArn\":\"<your-role-arn>\"}}'" \
    | tee -a "$RESULTS"
  echo '```' | tee -a "$RESULTS"
  exit 1
fi

# 로그 그룹 이름 추출 (CW Logs 모드인 경우)
LOG_GROUP=$(echo "$LOGGING_CFG" | python3 -c '
import json, sys
cfg = json.load(sys.stdin).get("loggingConfig", {})
cw = cfg.get("cloudWatchConfig", {})
print(cw.get("logGroupName", ""))
')

if [ -z "$LOG_GROUP" ]; then
  echo "**경고: CloudWatch Logs 대상이 설정되지 않음. S3 대상이라면 별도 검증 필요.**" \
    | tee -a "$RESULTS"
  exit 1
fi

echo "✓ logging 활성. 로그 그룹: \`$LOG_GROUP\`" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"


# ===== Step 2: 매직 헤더와 함께 claude 호출 =====
echo "## Step 2: 매직 헤더 첨부 claude 호출" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

METADATA_JSON="{\"probe\":\"$PROBE\",\"user\":\"wnwoqls2@naver.com\",\"team\":\"poc\",\"dept\":\"engineering\"}"
HEADER_LINE="X-Amzn-Bedrock-Request-Metadata: $METADATA_JSON"

echo "사용 헤더:" | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "$HEADER_LINE" | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

CALL_START=$(date +%s)
echo "claude 호출 시각: $(date -r $CALL_START '+%H:%M:%S')" | tee -a "$RESULTS"

CALL_OUTPUT=$(ANTHROPIC_CUSTOM_HEADERS="$HEADER_LINE" claude -p "Reply: probe $PROBE acknowledged" 2>&1 || echo "<claude 호출 실패>")
echo "" | tee -a "$RESULTS"
echo "claude 응답 (요약):" | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "$CALL_OUTPUT" | head -3 | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"


# ===== Step 3: 60초 대기 후 invocation log 도달 확인 =====
echo "## Step 3: 로그 도달 확인 (60초 대기)" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

sleep 60
DETECT_TIME=$(date +%s)
LATENCY=$((DETECT_TIME - CALL_START))

FILTER_PATTERN="{ \$.requestMetadata.probe = \"$PROBE\" }"
echo "filter pattern: \`$FILTER_PATTERN\`" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

EVENT=$(aws logs filter-log-events \
  --region "$REGION" \
  --log-group-name "$LOG_GROUP" \
  --filter-pattern "$FILTER_PATTERN" \
  --start-time "$((CALL_START * 1000))" \
  --query 'events[0].message' \
  --output text 2>&1 || echo "<filter-log-events 실패>")

if [ "$EVENT" = "None" ] || [ -z "$EVENT" ] || echo "$EVENT" | grep -q "<.*실패>"; then
  echo "**결과: 60초 내 로그 미도달.**" | tee -a "$RESULTS"
  echo "" | tee -a "$RESULTS"
  echo "추가 대기 60초..." | tee -a "$RESULTS"
  sleep 60
  EVENT=$(aws logs filter-log-events \
    --region "$REGION" \
    --log-group-name "$LOG_GROUP" \
    --filter-pattern "$FILTER_PATTERN" \
    --start-time "$((CALL_START * 1000))" \
    --query 'events[0].message' \
    --output text 2>&1 || echo "<>")
  LATENCY=$(($(date +%s) - CALL_START))
fi

if [ "$EVENT" = "None" ] || [ -z "$EVENT" ] || echo "$EVENT" | grep -q "<>"; then
  echo "" | tee -a "$RESULTS"
  echo "## 결과: ❌ FAIL" | tee -a "$RESULTS"
  echo "" | tee -a "$RESULTS"
  echo "120초 내 도달 실패. 가능한 원인:" | tee -a "$RESULTS"
  echo "- ANTHROPIC_CUSTOM_HEADERS가 SDK에 인식되지 않음" | tee -a "$RESULTS"
  echo "- Mantle endpoint 사용 중 (CLAUDE_CODE_USE_MANTLE 확인)" | tee -a "$RESULTS"
  echo "- IAM 권한 부족 (logs:FilterLogEvents)" | tee -a "$RESULTS"
  exit 1
fi

echo "" | tee -a "$RESULTS"
echo "✓ 도달 확인 (지연: ${LATENCY}초)" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"
echo "도달한 invocation log:" | tee -a "$RESULTS"
echo '```json' | tee -a "$RESULTS"
echo "$EVENT" | python3 -m json.tool 2>/dev/null | head -30 | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"


# ===== Step 4: requestMetadata 필드 무결성 확인 =====
echo "## Step 4: requestMetadata 필드 무결성" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

REQ_META=$(echo "$EVENT" | python3 -c '
import json, sys
e = json.loads(sys.stdin.read())
print(json.dumps(e.get("requestMetadata", {}), ensure_ascii=False, indent=2))
')

echo '```json' | tee -a "$RESULTS"
echo "$REQ_META" | tee -a "$RESULTS"
echo '```' | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"

# 4개 키 모두 존재하는지 확인
EXPECTED_KEYS="probe user team dept"
MISSING=""
for key in $EXPECTED_KEYS; do
  if ! echo "$REQ_META" | grep -q "\"$key\""; then
    MISSING="$MISSING $key"
  fi
done

if [ -n "$MISSING" ]; then
  echo "## 결과: ⚠ PARTIAL — 누락 키:$MISSING" | tee -a "$RESULTS"
  exit 2
fi

echo "## 결과: ✅ PASS" | tee -a "$RESULTS"
echo "" | tee -a "$RESULTS"
echo "- 매직 헤더가 본인 Cognito 흐름에서 정상 동작" | tee -a "$RESULTS"
echo "- requestMetadata 4개 키 모두 정확히 도달" | tee -a "$RESULTS"
echo "- 도달 지연: ${LATENCY}초" | tee -a "$RESULTS"
echo "- Wave 2 진입 가능" | tee -a "$RESULTS"
