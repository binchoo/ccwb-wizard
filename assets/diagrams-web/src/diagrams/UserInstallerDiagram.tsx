import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type NodeTypes,
} from '@xyflow/react';
import { AwsNode } from '../components/AwsNode';
import { GroupNode } from '../components/GroupNode';
import { CodeBlockNode } from '../components/CodeBlockNode';
import { Legend } from '../components/Legend';
import { userNodes } from './userNodes';
import { userEdges } from './userEdges';

// 다이어그램 2 — User가 산출물 zip을 받아 install.sh로 로컬을 구성하고
// 첫 claude 실행 시 OIDC + STS + Bedrock + 텔레메트리까지 체인이 작동

const nodeTypes: NodeTypes = {
  aws: AwsNode,
  group: GroupNode,
  code: CodeBlockNode,
};

export function UserInstallerDiagram() {
  const nodes = useMemo(() => userNodes, []);
  const edges = useMemo(() => userEdges, []);

  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} color="#e5e9ed" />
        <Controls position="top-right" showInteractive={false} />
        <MiniMap pannable zoomable position="bottom-right" />
      </ReactFlow>
      <Legend
        title="범례 — User Installer & Runtime"
        items={[
          { color: '#5294cf', label: 'install.sh가 로컬 구성' },
          { color: '#c925d1', label: '인증 흐름 (PKCE OIDC + STS)' },
          { color: '#e7157b', label: 'Quota check (STS 발급 직전)', dashed: true },
          { color: '#ed7100', label: 'Bedrock InvokeModel' },
          { color: '#1f8efa', label: 'OTLP 텔레메트리 (Central / Sidecar)' },
        ]}
      />
    </>
  );
}
