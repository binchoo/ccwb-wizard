# Wave 5 / Task 2.6 — End-to-end client flow verification

본 fork에서 변경된 클라이언트 흐름을 클린 환경에서 검증하는 절차.

## 전제

- Wave 1~4 task 완료 (코드/CFN 변경 push 됨)
- 본인 PoC 프로파일(`ccwb-dev-us-east-1`) 정상
- Bedrock model invocation logging 활성 상태

## 검증 단계

### 1. 새 zip으로 패키징

```bash
poetry run ccwb package --profile ccwb-dev-us-east-1
```

성공 기준:
- `dist/ccwb-dev-us-east-1/<timestamp>/` 디렉토리 생성
- `claude-settings/settings.json`에 `__ANTHROPIC_CUSTOM_HEADERS__` placeholder 포함
- `claude-settings/settings.json`에 `OTEL_EXPORTER_OTLP_*` 키 부재
- `otel-helper-*` 바이너리 부재 (Phase 4까지 완료된 후)

### 2. 클린 환경에서 install

```bash
cp ~/.claude/settings.json ~/.claude/settings.json.preE2E
cd dist/ccwb-dev-us-east-1/<timestamp>
./install.sh
```

성공 기준:
- 스크립트가 `credential-process --get-bedrock-metadata-headers` 호출
- (필요 시) 브라우저 OIDC 로그인 → 자동 재개
- `~/.claude/settings.json`의 `ANTHROPIC_CUSTOM_HEADERS` 값에 실제 메타데이터 박힘

### 3. 단일 호출 검증

```bash
PROBE="e2e-$(date +%s)"
ANTHROPIC_CUSTOM_HEADERS="X-Amzn-Bedrock-Request-Metadata: {\"user\":\"wnwoqls2@naver.com\",\"team\":\"e2e\",\"probe\":\"$PROBE\"}" \
  claude -p "say hi $PROBE"

sleep 60
aws logs filter-log-events \
  --log-group-name /aws/bedrock/modelinvocations/ccwb-dev-us-east-1 \
  --filter-pattern "{ \$.requestMetadata.probe = \"$PROBE\" }" \
  --region us-east-1 \
  --query 'events[0].message' --output text
```

### 4. 메트릭 필터 → Custom Metrics 전파 검증

```bash
sleep 120
aws cloudwatch get-metric-statistics \
  --namespace ClaudeCodeBedrock \
  --metric-name InputTokensByUser \
  --dimensions Name=User,Value=wnwoqls2@naver.com Name=Team,Value=e2e \
  --start-time $(date -u -v-10M +"%Y-%m-%dT%H:%M:%SZ") \
  --end-time $(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  --period 60 \
  --statistics Sum \
  --region us-east-1
```

### 5. Burst 검증

5명 페르소나 × 5회 호출.

```bash
for i in 1 2 3 4 5; do
  for u in alice bob charlie dave eve; do
    PROBE="burst-$u-$i"
    ANTHROPIC_CUSTOM_HEADERS="X-Amzn-Bedrock-Request-Metadata: {\"user\":\"$u@example.com\",\"team\":\"sim-$((RANDOM%3))\",\"probe\":\"$PROBE\"}" \
      claude -p "ping $PROBE" >/dev/null 2>&1
    sleep 2
  done
done
```

성공 기준: dashboard에 5개 사용자 라인 + 3개 team 라인.

### 6. 복원

```bash
cp ~/.claude/settings.json.preE2E ~/.claude/settings.json
```
