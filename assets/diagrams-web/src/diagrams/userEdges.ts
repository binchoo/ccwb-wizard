import type { Edge, MarkerType } from '@xyflow/react';

// 엣지 색상 (범례와 일치)
const C = {
  install: '#5294cf', // installer가 파일을 배치하는 흐름
  auth: '#c925d1', // 인증 (OIDC + STS)
  invoke: '#ed7100', // Bedrock 호출
  telemetry: '#1f8efa', // OTLP 텔레메트리
  quota: '#e7157b', // Quota 체크
};

const arrow = (color: string) => ({
  markerEnd: { type: 'arrowclosed' as MarkerType, color },
  style: { stroke: color, strokeWidth: 1.6 },
});

const dashed = (color: string) => ({
  markerEnd: { type: 'arrowclosed' as MarkerType, color },
  style: { stroke: color, strokeWidth: 1.5, strokeDasharray: '6 4' },
  animated: false,
});

export const userEdges: Edge[] = [];


// ===== 단계 1: 산출물 다운로드 → install.sh 실행 =====
userEdges.push(
  {
    id: 'e-zip-user',
    source: 'src-zip',
    sourceHandle: 'right-src',
    target: 'user-persona',
    targetHandle: 'left-tgt',
    label: '① 다운로드 (presigned URL)',
    ...arrow(C.install),
  },
  {
    id: 'e-user-installer',
    source: 'user-persona',
    sourceHandle: 'bottom-src',
    target: 'install-sh',
    targetHandle: 'top-tgt',
    label: '② 1회 실행',
    ...arrow(C.install),
  }
);

// ===== 단계 2: install.sh가 로컬에 배치하는 산출물 =====
userEdges.push(
  {
    id: 'e-installer-bin',
    source: 'install-sh',
    sourceHandle: 'right-src',
    target: 'fs-bin',
    targetHandle: 'left-tgt',
    label: '③ 바이너리 배치',
    ...arrow(C.install),
  },
  {
    id: 'e-installer-settings',
    source: 'install-sh',
    sourceHandle: 'right-src',
    target: 'fs-claude-settings',
    targetHandle: 'left-tgt',
    label: '④ settings.json 생성',
    ...arrow(C.install),
  },
  {
    id: 'e-installer-awscfg',
    source: 'install-sh',
    sourceHandle: 'right-src',
    target: 'fs-aws-config',
    targetHandle: 'left-tgt',
    label: '⑤ ~/.aws/config 추가',
    ...arrow(C.install),
  }
);


// ===== 단계 3: 첫 claude 실행 시 자격증명 체인 =====
userEdges.push(
  {
    id: 'e-claude-awsconfig',
    source: 'rt-claude',
    sourceHandle: 'left-src',
    target: 'fs-aws-config',
    targetHandle: 'right-tgt',
    label: '⑥ AWS_PROFILE 조회',
    ...dashed(C.install),
  },
  {
    id: 'e-awsconfig-credproc',
    source: 'fs-aws-config',
    sourceHandle: 'right-src',
    target: 'rt-credproc',
    targetHandle: 'left-tgt',
    label: '⑦ credential_process 호출',
    ...arrow(C.auth),
  },
  {
    id: 'e-credproc-idp',
    source: 'rt-credproc',
    sourceHandle: 'right-src',
    target: 'aws-idp',
    targetHandle: 'left-tgt',
    label: '⑧ PKCE OIDC (캐시 miss 시)',
    ...arrow(C.auth),
  },
  {
    id: 'e-credproc-quota',
    source: 'rt-credproc',
    sourceHandle: 'right-src',
    target: 'aws-quota',
    targetHandle: 'left-tgt',
    label: '⑨ Quota check (STS 발급 직전)',
    ...dashed(C.quota),
  },
  {
    id: 'e-credproc-sts',
    source: 'rt-credproc',
    sourceHandle: 'right-src',
    target: 'aws-sts',
    targetHandle: 'left-tgt',
    label: '⑩ AssumeRoleWithWebIdentity',
    ...arrow(C.auth),
  }
);


// ===== 단계 4: Bedrock 호출 =====
userEdges.push(
  {
    id: 'e-claude-bedrock',
    source: 'rt-claude',
    sourceHandle: 'right-src',
    target: 'aws-bedrock',
    targetHandle: 'left-tgt',
    label: '⑪ InvokeModel (임시 STS 자격증명)',
    ...arrow(C.invoke),
  }
);

// ===== 단계 5: 텔레메트리 송출 (v3.0+ Bedrock-native) =====
userEdges.push(
  {
    id: 'e-claude-bedrock-logging',
    source: 'rt-claude',
    sourceHandle: 'bottom-src',
    target: 'aws-collector',
    targetHandle: 'left-tgt',
    label: '⑫ ANTHROPIC_CUSTOM_HEADERS → $.requestMetadata.* 자동 기록',
    ...arrow(C.telemetry),
  }
);
