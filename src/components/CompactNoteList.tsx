import { Typography } from 'antd';
import { isValidElement } from 'react';
import type { ReactNode } from 'react';

const { Text } = Typography;

type CompactNoteListProps = {
  items: ReactNode[];
};

function renderItem(item: ReactNode, index: number) {
  if (isValidElement(item)) {
    return item;
  }
  return (
    <Text key={`note-${index}`} type="secondary" className="aicomic-console-note">
      {item}
    </Text>
  );
}

export default function CompactNoteList({ items }: CompactNoteListProps) {
  const visibleItems = items.filter((item) => item !== undefined && item !== null && item !== '');
  if (!visibleItems.length) {
    return null;
  }

  return (
    <div className="aicomic-console-note-list">
      {visibleItems.map((item, index) => renderItem(item, index))}
    </div>
  );
}
