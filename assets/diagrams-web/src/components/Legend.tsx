// Legend - 다이어그램 우하단 범례 (엣지 의미 안내)

export type LegendItem = {
  color: string;
  label: string;
  dashed?: boolean;
};

export function Legend({ title, items }: { title: string; items: LegendItem[] }) {
  return (
    <div className="legend-panel">
      <h4>{title}</h4>
      {items.map((it, i) => (
        <div key={i} className="legend-row">
          {it.dashed ? (
            <div
              className="legend-swatch dashed"
              style={{ borderTopColor: it.color, width: 20 }}
            />
          ) : (
            <div className="legend-swatch" style={{ background: it.color }} />
          )}
          <div className="legend-text">{it.label}</div>
        </div>
      ))}
    </div>
  );
}
