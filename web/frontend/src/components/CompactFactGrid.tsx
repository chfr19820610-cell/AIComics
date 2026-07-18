import { Typography } from 'antd';
import type { ReactNode } from 'react';

const { Text } = Typography;

type CompactFactItem = {
  key?: string;
  label: string;
  value: ReactNode;
};

type CompactFactGridProps = {
  items: CompactFactItem[];
  minColumnWidth?: number;
};

function renderValue(value: ReactNode) {
  if (typeof value === 'string' || typeof value === 'number') {
    return <Text>{value}</Text>;
  }
  return value;
}

export default function CompactFactGrid({ items, minColumnWidth = 120 }: CompactFactGridProps) {
  return (
    <div
      className="aicomic-fact-grid"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${minColumnWidth}px, 1fr))` }}
    >
      {items.map((item, index) => (
        <div key={item.key ?? `${item.label}-${index}`} className="aicomic-fact-item">
          <Text type="secondary" className="aicomic-fact-label">
            {item.label}
          </Text>
          <div className="aicomic-fact-value">{renderValue(item.value)}</div>
        </div>
      ))}
    </div>
  );
}
