import type { Edge, MarkerType } from '@xyflow/react';

// 엣지 카테고리별 색상 (범례와 일치)
const C = {
  control: '#5294cf', // Admin 제어 흐름 (CLI → AWS)
  build: '#ed7100', // 빌드/배포 산출물 흐름
  trust: '#c925d1', // IAM trust 관계
  data: '#1f8efa', // 텔레메트리 데이터 흐름
  artifact: '#d4a72c', // 산출물 zip 패키징/저장
};

// 화살표 마커 헬퍼
const arrow = (color: string) => ({
  markerEnd: { type: 'arrowclosed' as MarkerType, color },
  style: { stroke: color, strokeWidth: 1.6 },
});

const dashed = (color: string) => ({
  markerEnd: { type: 'arrowclosed' as MarkerType, color },
  style: { stroke: color, strokeWidth: 1.5, strokeDasharray: '6 4' },
  animated: false,
});

export const adminEdges: Edge[] = [];


// ===== Admin → AWS: ccwb deploy로 스택 생성 =====
adminEdges.push(
  {
    id: 'e-cli-auth',
    source: 'admin-cli',
    sourceHandle: 'right-src',
    target: 'auth-oidc-provider',
    targetHandle: 'left-tgt',
    label: 'ccwb deploy auth',
    ...arrow(C.control),
  },
  {
    id: 'e-cli-build',
    source: 'admin-cli',
    sourceHandle: 'right-src',
    target: 'build-codebuild',
    targetHandle: 'top-tgt',
    label: 'ccwb deploy build (Win 한정)',
    ...arrow(C.control),
  },
  {
    id: 'e-cli-mc',
    source: 'admin-cli',
    sourceHandle: 'right-src',
    target: 'mc-ecs',
    targetHandle: 'left-tgt',
    label: 'ccwb deploy monitoring (central)',
    ...arrow(C.control),
  },
  {
    id: 'e-cli-ms',
    source: 'admin-cli',
    sourceHandle: 'right-src',
    target: 'ms-cw',
    targetHandle: 'left-tgt',
    label: 'ccwb deploy monitoring (sidecar) — 대시보드만',
    ...arrow(C.control),
  }
);


// ===== 인증 스택 내부: IdP ←→ OIDC Provider ←→ IAM Role =====
adminEdges.push(
  {
    id: 'e-idp-prov',
    source: 'auth-idp',
    sourceHandle: 'right-src',
    target: 'auth-oidc-provider',
    targetHandle: 'left-tgt',
    label: 'issuer URL · thumbprint',
    ...dashed(C.trust),
  },
  {
    id: 'e-prov-role',
    source: 'auth-oidc-provider',
    sourceHandle: 'right-src',
    target: 'auth-iam-role',
    targetHandle: 'left-tgt',
    label: 'AssumeRoleWithWebIdentity 신뢰',
    ...dashed(C.trust),
  }
);

// ===== 빌드/배포 산출물 흐름: CodeBuild → S3 → Landing =====
adminEdges.push(
  {
    id: 'e-build-s3',
    source: 'build-codebuild',
    sourceHandle: 'right-src',
    target: 'dist-s3',
    targetHandle: 'left-tgt',
    label: 'Win exe upload',
    ...arrow(C.build),
  },
  {
    id: 'e-cli-s3',
    source: 'admin-cli',
    sourceHandle: 'right-src',
    target: 'dist-s3',
    targetHandle: 'left-tgt',
    label: 'ccwb package → upload (Mac/Linux)',
    ...arrow(C.build),
  },
  {
    id: 'e-s3-landing',
    source: 'dist-s3',
    sourceHandle: 'right-src',
    target: 'dist-landing',
    targetHandle: 'left-tgt',
    label: 'origin',
    ...dashed(C.build),
  }
);


// ===== 산출물 zip로 합쳐지는 흐름 =====
adminEdges.push(
  {
    id: 'e-s3-zip',
    source: 'dist-s3',
    sourceHandle: 'right-src',
    target: 'artifact-zip',
    targetHandle: 'left-tgt',
    label: 'ccwb distribute → presigned URL',
    ...arrow(C.artifact),
  },
  {
    id: 'e-landing-zip',
    source: 'dist-landing',
    sourceHandle: 'bottom-src',
    target: 'artifact-zip',
    targetHandle: 'left-tgt',
    label: 'self-service download',
    ...dashed(C.artifact),
  }
);

// ===== Central 관제 내부 데이터 파이프라인 =====
adminEdges.push(
  {
    id: 'e-vpc-ecs',
    source: 'mc-vpc',
    sourceHandle: 'right-src',
    target: 'mc-ecs',
    targetHandle: 'left-tgt',
    label: 'OTLP/HTTP',
    ...arrow(C.data),
  },
  {
    id: 'e-ecs-cw',
    source: 'mc-ecs',
    sourceHandle: 'right-src',
    target: 'mc-cw',
    targetHandle: 'left-tgt',
    label: 'EMF + Metrics',
    ...arrow(C.data),
  },
  {
    id: 'e-ecs-analytics',
    source: 'mc-ecs',
    sourceHandle: 'right-src',
    target: 'mc-analytics',
    targetHandle: 'top-tgt',
    label: 'Firehose',
    ...arrow(C.data),
  }
);
