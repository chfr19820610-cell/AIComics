import { ProCard } from '@ant-design/pro-components';
import type { ReactNode } from 'react';

import CompactFactGrid from '@/components/CompactFactGrid';
import CompactNoteList from '@/components/CompactNoteList';

type CompactFactItem = {
  key?: string;
  label: string;
  value: ReactNode;
};

type CompactSummaryCardProps = {
  title: string;
  extra?: ReactNode;
  tags?: ReactNode;
  facts?: CompactFactItem[];
  notes?: ReactNode[];
  children?: ReactNode;
  minColumnWidth?: number;
  className?: string;
};

export default function CompactSummaryCard({
  title,
  extra,
  tags,
  facts,
  notes,
  children,
  minColumnWidth = 140,
  className,
}: CompactSummaryCardProps) {
  return (
    <ProCard
      title={title}
      extra={extra}
      bordered
      className={['aicomic-compact-card', className].filter(Boolean).join(' ')}
    >
      <div className="aicomic-console-stack">
        {tags ? <div className="aicomic-console-tag-row">{tags}</div> : null}
        {facts?.length ? <CompactFactGrid items={facts} minColumnWidth={minColumnWidth} /> : null}
        {children}
        {notes?.length ? <CompactNoteList items={notes} /> : null}
      </div>
    </ProCard>
  );
}
