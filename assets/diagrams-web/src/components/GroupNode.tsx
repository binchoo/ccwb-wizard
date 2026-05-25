import type { NodeProps } from '@xyflow/react';

// GroupNode - 컨테이너 박스 (AWS Account, 사용자 로컬, 관제 스택 등)
// data.label    : 그룹 이름
// data.variant  : 'aws' | 'local' | 'monitoring-central' | 'monitoring-sidecar'
// width/height는 style로 주입

export type GroupNodeData = {
  label: string;
  variant?: 'aws' | 'local' | 'monitoring-central' | 'monitoring-sidecar';
};

export function GroupNode({ data, width, height }: NodeProps) {
  const d = data as unknown as GroupNodeData;
  const variant = d.variant ?? 'aws';
  return (
    <div
      className={`group-node group-${variant}`}
      style={{ width, height }}
    >
      <div className="group-label">{d.label}</div>
    </div>
  );
}
