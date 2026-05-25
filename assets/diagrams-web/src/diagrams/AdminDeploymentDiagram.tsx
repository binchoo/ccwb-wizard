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
import { adminNodes } from './adminNodes';
import { adminEdges } from './adminEdges';

// 다이어그램 1 — Admin이 ccwb CLI로 AWS 스택 배포 후 사용자 배포용 zip 산출물을 생성
// 인증(IAM OIDC), 빌드(CodeBuild), 관제(Central/Sidecar)를 한 화면에서 비교

const nodeTypes: NodeTypes = {
  aws: AwsNode,
  group: GroupNode,
  code: CodeBlockNode,
};

export function AdminDeploymentDiagram() {
  const nodes = useMemo(() => adminNodes, []);
  const edges = useMemo(() => adminEdges, []);

  return (
    <>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} color="#e5e9ed" />
        <Controls position="top-right" showInteractive={false} />
        <MiniMap pannable zoomable position="bottom-right" />
      </ReactFlow>
      <Legend
        title="범례 — Admin Deployment"
        items={[
          { color: '#5294cf', label: 'ccwb CLI 제어 흐름 (배포 명령)' },
          { color: '#ed7100', label: '빌드/패키징 흐름' },
          { color: '#c925d1', label: 'IAM 신뢰 관계', dashed: true },
          { color: '#1f8efa', label: '관제 데이터 흐름 (OTLP/EMF)' },
          { color: '#d4a72c', label: '산출물(zip) 배포' },
        ]}
      />
    </>
  );
}
