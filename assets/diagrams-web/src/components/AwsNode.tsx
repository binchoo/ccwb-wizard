import { Handle, Position, type NodeProps } from '@xyflow/react';

// AwsNode - 다이어그램 공통 노드 컴포넌트
// data.title  : 메인 라벨
// data.subtitle : 보조 설명 (옵션)
// data.tag    : 카테고리 태그 (예: "IAM", "ECS", "OIDC IdP")
// data.category : 색상 카테고리 (CSS 클래스 매핑)
// data.handles  : 표시할 핸들 위치 배열 (default: ['left','right'])

export type AwsNodeData = {
  title: string;
  subtitle?: string;
  tag?: string;
  category?:
    | 'admin'
    | 'user'
    | 'aws-iam'
    | 'aws-compute'
    | 'aws-storage'
    | 'aws-mgmt'
    | 'aws-network'
    | 'aws-analytics'
    | 'external'
    | 'artifact';
  handles?: Array<'top' | 'right' | 'bottom' | 'left'>;
};

const positionMap: Record<string, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
};

export function AwsNode({ data }: NodeProps) {
  const d = data as unknown as AwsNodeData;
  const handles = d.handles ?? ['left', 'right', 'top', 'bottom'];
  const cat = d.category ?? 'external';

  // 핸들은 source/target 두 쌍을 각 위치마다 같은 좌표에 깔아 주어
  // 다이어그램 작성자가 양방향 어느 쪽으로든 엣지를 연결할 수 있게 한다.
  const handleNodes = handles.flatMap((h) => [
    <Handle
      key={`src-${h}`}
      type="source"
      position={positionMap[h]}
      id={`${h}-src`}
      style={{ background: '#8a96a6', width: 6, height: 6 }}
    />,
    <Handle
      key={`tgt-${h}`}
      type="target"
      position={positionMap[h]}
      id={`${h}-tgt`}
      style={{ background: '#8a96a6', width: 6, height: 6 }}
    />,
  ]);

  return (
    <div className={`node-card cat-${cat}`}>
      {handleNodes}
      <div className="node-title">{d.title}</div>
      {d.subtitle && <div className="node-subtitle">{d.subtitle}</div>}
      {d.tag && <span className="node-tag">{d.tag}</span>}
    </div>
  );
}
