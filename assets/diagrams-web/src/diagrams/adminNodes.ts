import type { Node } from '@xyflow/react';
import { RAW_ZIP_MANIFEST } from './rawConfigs';

// Admin 다이어그램 노드 정의
// 좌→우 흐름: Admin 로컬 (ccwb CLI)  →  AWS 배포 스택  →  배포 산출물(zip/Landing Page)
// 인증 스택 / 빌드 스택 / 관제 스택(Central, Sidecar) 4계열로 그룹화

export const adminNodes: Node[] = [
  // ===== 그룹 컨테이너 =====
  {
    id: 'g-admin-local',
    type: 'group',
    position: { x: 0, y: 80 },
    data: { label: 'Admin 로컬 (Mac/Win/Linux)', variant: 'local' },
    style: { width: 260, height: 360 },
    draggable: true,
    selectable: false,
  },
  {
    id: 'g-aws',
    type: 'group',
    position: { x: 340, y: 0 },
    data: { label: 'AWS Account (Commercial 또는 GovCloud)', variant: 'aws' },
    style: { width: 720, height: 880 },
    draggable: true,
    selectable: false,
  },
  {
    id: 'g-monitoring-central',
    type: 'group',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 20, y: 380 },
    data: { label: '관제 — Central Collector (옵션)', variant: 'monitoring-central' },
    style: { width: 680, height: 240 },
    draggable: false,
    selectable: false,
  },
  {
    id: 'g-monitoring-sidecar',
    type: 'group',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 20, y: 640 },
    data: { label: '관제 — Sidecar Mode (대시보드만 AWS 측)', variant: 'monitoring-sidecar' },
    style: { width: 680, height: 220 },
    draggable: false,
    selectable: false,
  },
];

// ===== Admin 로컬 측 노드 =====
adminNodes.push(
  {
    id: 'admin-user',
    type: 'aws',
    parentId: 'g-admin-local',
    extent: 'parent',
    position: { x: 50, y: 40 },
    data: {
      title: 'IT Admin',
      subtitle: 'ccwb CLI 운영자',
      tag: 'PERSONA',
      category: 'admin',
      handles: ['right', 'bottom'],
    },
  },
  {
    id: 'admin-cli',
    type: 'aws',
    parentId: 'g-admin-local',
    extent: 'parent',
    position: { x: 30, y: 140 },
    data: {
      title: 'ccwb CLI',
      subtitle: 'init → configure → deploy → package → distribute',
      tag: 'PYTHON',
      category: 'admin',
      handles: ['top', 'right'],
    },
  },
  {
    id: 'admin-source',
    type: 'aws',
    parentId: 'g-admin-local',
    extent: 'parent',
    position: { x: 30, y: 250 },
    data: {
      title: 'CFN Templates',
      subtitle: 'auth / build / monitoring / analytics',
      tag: 'CLOUDFORMATION',
      category: 'admin',
      handles: ['top', 'right'],
    },
  }
);

// ===== AWS 측 - 인증 스택 =====
adminNodes.push(
  {
    id: 'auth-idp',
    type: 'aws',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 20, y: 50 },
    data: {
      title: 'External OIDC IdP',
      subtitle: 'Okta / Entra ID / Auth0 / Cognito UP',
      tag: 'IDP',
      category: 'external',
      handles: ['right', 'bottom'],
    },
  },
  {
    id: 'auth-oidc-provider',
    type: 'aws',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 250, y: 50 },
    data: {
      title: 'IAM OIDC Provider',
      subtitle: '발급자 thumbprint 등록',
      tag: 'IAM',
      category: 'aws-iam',
      handles: ['left', 'right', 'bottom'],
    },
  },
  {
    id: 'auth-iam-role',
    type: 'aws',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 480, y: 50 },
    data: {
      title: 'IAM Role',
      subtitle: 'Bedrock InvokeModel + sts:TagSession',
      tag: 'IAM ROLE',
      category: 'aws-iam',
      handles: ['left', 'bottom'],
    },
  }
);

// ===== AWS 측 - 빌드 스택 + 산출물 저장 =====
adminNodes.push(
  {
    id: 'build-codebuild',
    type: 'aws',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 20, y: 200 },
    data: {
      title: 'AWS CodeBuild',
      subtitle: 'Windows Nuitka 빌드 (옵션)',
      tag: 'BUILD',
      category: 'aws-compute',
      handles: ['top', 'right', 'bottom'],
    },
  },
  {
    id: 'dist-s3',
    type: 'aws',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 250, y: 200 },
    data: {
      title: 'S3 — Distribution Bucket',
      subtitle: 'Presigned URL 발급',
      tag: 'S3',
      category: 'aws-storage',
      handles: ['left', 'right', 'bottom'],
    },
  },
  {
    id: 'dist-landing',
    type: 'aws',
    parentId: 'g-aws',
    extent: 'parent',
    position: { x: 480, y: 200 },
    data: {
      title: 'Landing Page (옵션)',
      subtitle: 'IdP 인증 + Self-service 다운로드',
      tag: 'CLOUDFRONT',
      category: 'aws-network',
      handles: ['left', 'bottom'],
    },
  }
);

// ===== AWS 측 - 관제 Central =====
adminNodes.push(
  {
    id: 'mc-vpc',
    type: 'aws',
    parentId: 'g-monitoring-central',
    extent: 'parent',
    position: { x: 20, y: 50 },
    data: {
      title: 'VPC + ALB',
      subtitle: 'OTLP 수신 + JWT Authorizer',
      tag: 'NETWORK',
      category: 'aws-network',
      handles: ['right', 'bottom'],
    },
  },
  {
    id: 'mc-ecs',
    type: 'aws',
    parentId: 'g-monitoring-central',
    extent: 'parent',
    position: { x: 230, y: 50 },
    data: {
      title: 'ECS Fargate',
      subtitle: 'OTEL Collector (recv→proc→exp)',
      tag: 'ECS',
      category: 'aws-compute',
      handles: ['left', 'right'],
    },
  },
  {
    id: 'mc-cw',
    type: 'aws',
    parentId: 'g-monitoring-central',
    extent: 'parent',
    position: { x: 440, y: 50 },
    data: {
      title: 'CloudWatch',
      subtitle: 'EMF Logs + Metrics + Dashboard',
      tag: 'CW',
      category: 'aws-mgmt',
      handles: ['left', 'right'],
    },
  },
  {
    id: 'mc-analytics',
    type: 'aws',
    parentId: 'g-monitoring-central',
    extent: 'parent',
    position: { x: 230, y: 150 },
    data: {
      title: 'Firehose → S3 → Glue/Athena',
      subtitle: '히스토리컬 SQL 분석 (옵션)',
      tag: 'ANALYTICS',
      category: 'aws-analytics',
      handles: ['top', 'left', 'right'],
    },
  }
);

// ===== AWS 측 - 관제 Sidecar (대시보드만) =====
adminNodes.push(
  {
    id: 'ms-cw',
    type: 'aws',
    parentId: 'g-monitoring-sidecar',
    extent: 'parent',
    position: { x: 230, y: 60 },
    data: {
      title: 'CloudWatch Metrics + Dashboard',
      subtitle: '서버 인프라 없음. Sidecar가 SigV4로 직접 push',
      tag: 'CW',
      category: 'aws-mgmt',
      handles: ['left', 'right', 'top'],
    },
  }
);

// ===== 산출물 (zip) =====
adminNodes.push(
  {
    id: 'artifact-zip',
    type: 'code',
    position: { x: 1110, y: 220 },
    data: {
      title: 'claude-code-package.zip',
      subtitle: 'ccwb package + ccwb distribute 산출물 (S3 presigned URL로 배포)',
      tag: 'DELIVERABLE',
      language: 'ini',
      code: RAW_ZIP_MANIFEST,
      handles: ['left', 'right'],
    },
  }
);
