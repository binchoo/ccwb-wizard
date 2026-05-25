import type { Node } from '@xyflow/react';
import {
  RAW_AWS_CONFIG,
  RAW_CLAUDE_SETTINGS_RESOLVED,
  RAW_CONFIG_JSON,
} from './rawConfigs';

// User 다이어그램 노드 정의
// 좌→우 흐름: 산출물 zip 다운로드 → install.sh 실행 → 로컬 파일 생성 (raw 내용 표시)
//          → 첫 claude 실행 시 OIDC + STS + Bedrock + 텔레메트리

export const userNodes: Node[] = [
  // ===== 그룹 컨테이너 =====
  {
    id: 'g-source',
    type: 'group',
    position: { x: 0, y: 60 },
    data: { label: '관리자가 만든 산출물 (S3 / Landing Page)', variant: 'aws' },
    style: { width: 460, height: 460 },
    draggable: true,
    selectable: false,
  },
  {
    id: 'g-user-local',
    type: 'group',
    position: { x: 500, y: 0 },
    data: { label: 'End User 로컬 머신 (Mac/Win/Linux)', variant: 'local' },
    style: { width: 1280, height: 1180 },
    draggable: true,
    selectable: false,
  },
  {
    id: 'g-aws-runtime',
    type: 'group',
    position: { x: 1820, y: 60 },
    data: { label: 'AWS — 런타임 호출 대상', variant: 'aws' },
    style: { width: 290, height: 760 },
    draggable: true,
    selectable: false,
  },
];


// ===== 산출물 영역 — config.json은 zip 안의 raw 내용 그대로 =====
userNodes.push(
  {
    id: 'src-zip',
    type: 'aws',
    parentId: 'g-source',
    extent: 'parent',
    position: { x: 30, y: 40 },
    data: {
      title: 'claude-code-package.zip',
      subtitle: 'presigned URL 또는 Landing Page',
      tag: 'DELIVERABLE',
      category: 'artifact',
      handles: ['right', 'bottom'],
    },
  },
  {
    id: 'src-config-json',
    type: 'code',
    parentId: 'g-source',
    extent: 'parent',
    position: { x: 30, y: 130 },
    data: {
      title: 'config.json',
      subtitle: 'zip 내부. credential-process가 런타임에 읽어 OIDC/federation 설정 결정',
      tag: 'CONFIG',
      language: 'json',
      code: RAW_CONFIG_JSON,
      handles: ['right', 'bottom'],
    },
  }
);


// ===== End User 로컬 - persona / installer (좌상단) =====
userNodes.push(
  {
    id: 'user-persona',
    type: 'aws',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 20, y: 40 },
    data: {
      title: 'End User',
      subtitle: '개발자',
      tag: 'PERSONA',
      category: 'user',
      handles: ['left', 'right', 'bottom'],
    },
  },
  {
    id: 'install-sh',
    type: 'aws',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 20, y: 160 },
    data: {
      title: 'install.sh / install.bat',
      subtitle: '1회 실행 → 로컬 구성 자동화',
      tag: 'INSTALLER',
      category: 'user',
      handles: ['top', 'right', 'bottom'],
    },
  }
);


// ===== End User 로컬 - 설치 결과물 (CodeBlock으로 raw 내용 표시) =====
userNodes.push(
  {
    id: 'fs-bin',
    type: 'aws',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 240, y: 40 },
    data: {
      title: '~/claude-code-with-bedrock/',
      subtitle: 'credential-process · otel-helper · otelcol(sidecar)',
      tag: 'BINARIES',
      category: 'artifact',
      handles: ['left', 'right', 'bottom'],
    },
  },
  {
    id: 'fs-claude-settings',
    type: 'code',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 240, y: 160 },
    data: {
      title: '~/.claude/settings.json',
      subtitle: 'install.sh가 placeholder 치환해서 작성. Claude Code가 직접 읽음.',
      tag: 'SETTINGS',
      language: 'json',
      code: RAW_CLAUDE_SETTINGS_RESOLVED,
      handles: ['left', 'right', 'bottom', 'top'],
    },
  },
  {
    id: 'fs-aws-config',
    type: 'code',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 240, y: 580 },
    data: {
      title: '~/.aws/config',
      subtitle: 'AWS SDK가 AWS_PROFILE 조회 시 credential_process 호출',
      tag: 'AWS PROFILE',
      language: 'ini',
      code: RAW_AWS_CONFIG,
      handles: ['left', 'right', 'bottom', 'top'],
    },
  }
);


// ===== End User 로컬 - 런타임 컴포넌트 (우측 컬럼, v3.0+ Bedrock-native) =====
userNodes.push(
  {
    id: 'rt-claude',
    type: 'aws',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 670, y: 40 },
    data: {
      title: 'Claude Code CLI',
      subtitle: 'AWS_PROFILE=ClaudeCode + ANTHROPIC_CUSTOM_HEADERS',
      tag: 'CLI',
      category: 'user',
      handles: ['left', 'right', 'bottom'],
    },
  },
  {
    id: 'rt-credproc',
    type: 'aws',
    parentId: 'g-user-local',
    extent: 'parent',
    position: { x: 670, y: 160 },
    data: {
      title: 'credential-process',
      subtitle: 'PKCE OIDC + STS · keychain 캐시 · --get-bedrock-metadata-headers',
      tag: 'AUTH HELPER',
      category: 'user',
      handles: ['left', 'right', 'top', 'bottom'],
    },
  }
);


// ===== AWS 런타임 호출 대상 =====
userNodes.push(
  {
    id: 'aws-idp',
    type: 'aws',
    parentId: 'g-aws-runtime',
    extent: 'parent',
    position: { x: 30, y: 40 },
    data: {
      title: 'External OIDC IdP',
      subtitle: 'Okta/Entra/Auth0/Cognito',
      tag: 'IDP',
      category: 'external',
      handles: ['left', 'bottom'],
    },
  },
  {
    id: 'aws-sts',
    type: 'aws',
    parentId: 'g-aws-runtime',
    extent: 'parent',
    position: { x: 30, y: 160 },
    data: {
      title: 'AWS STS',
      subtitle: 'AssumeRoleWithWebIdentity → 임시 자격증명',
      tag: 'STS',
      category: 'aws-iam',
      handles: ['left', 'top', 'bottom'],
    },
  },
  {
    id: 'aws-bedrock',
    type: 'aws',
    parentId: 'g-aws-runtime',
    extent: 'parent',
    position: { x: 30, y: 290 },
    data: {
      title: 'Amazon Bedrock',
      subtitle: 'Claude Sonnet/Opus/Haiku · Cross-region inference',
      tag: 'BEDROCK',
      category: 'aws-compute',
      handles: ['left', 'top', 'bottom'],
    },
  },
  {
    id: 'aws-quota',
    type: 'aws',
    parentId: 'g-aws-runtime',
    extent: 'parent',
    position: { x: 30, y: 430 },
    data: {
      title: 'Quota API (옵션)',
      subtitle: 'API GW + DynamoDB · STS 발급 직전 호출',
      tag: 'QUOTA',
      category: 'aws-mgmt',
      handles: ['left', 'top'],
    },
  },
  {
    id: 'aws-collector',
    type: 'aws',
    parentId: 'g-aws-runtime',
    extent: 'parent',
    position: { x: 30, y: 550 },
    data: {
      title: 'Bedrock Model Invocation Logging',
      subtitle: '$.requestMetadata → CloudWatch Logs + S3 → Custom Metrics',
      tag: 'OBSERVE',
      category: 'aws-mgmt',
      handles: ['left', 'top'],
    },
  }
);
