import { Handle, Position, type NodeProps } from '@xyflow/react';

// CodeBlockNode - 산출물 노드. 카드 안에 raw JSON/INI 코드를 그대로 표시.
// data.title    : 파일 경로 또는 제목
// data.subtitle : 한 줄 설명
// data.tag      : 카테고리 태그
// data.language : 'json' | 'ini' (현재는 스타일 동일, 향후 하이라이트 분기용)
// data.code     : 실제 파일 내용 raw 문자열
// data.handles  : 표시할 핸들 위치

export type CodeBlockNodeData = {
  title: string;
  subtitle?: string;
  tag?: string;
  language?: 'json' | 'ini';
  code: string;
  handles?: Array<'top' | 'right' | 'bottom' | 'left'>;
};

const positionMap: Record<string, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
};

export function CodeBlockNode({ data }: NodeProps) {
  const d = data as unknown as CodeBlockNodeData;
  const handles = d.handles ?? ['left', 'right', 'top', 'bottom'];

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
    <div className="codeblock-node">
      {handleNodes}
      <div className="codeblock-header">
        <div className="codeblock-title">{d.title}</div>
        {d.tag && <span className="codeblock-tag">{d.tag}</span>}
      </div>
      {d.subtitle && <div className="codeblock-subtitle">{d.subtitle}</div>}
      <pre className={`codeblock-pre lang-${d.language ?? 'json'}`}>
        <code>{d.code}</code>
      </pre>
    </div>
  );
}
