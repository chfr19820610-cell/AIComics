import { ProCard } from '@ant-design/pro-components';
import {
  Button,
  List,
  Popconfirm,
  Space,
  Tag,
  Typography,
} from 'antd';

import type { CreatorWorkspacePayload, ShotRecord } from '@/types/api';
import { displayPriority, displayStatus, displayText } from '@/utils/display';

const { Paragraph, Text, Title } = Typography;

type Props = {
  activeEpisode?: CreatorWorkspacePayload['episodes'][number];
  workspace?: CreatorWorkspacePayload;
  onOpenShotEditor: (shot?: ShotRecord) => void;
  onDeleteShot: (shot: ShotRecord) => Promise<void>;
};

export default function ShotList({ activeEpisode, workspace, onOpenShotEditor, onDeleteShot }: Props) {
  return (
    <ProCard
      title={activeEpisode ? `${activeEpisode.episode_code} 镜头列表` : '镜头列表'}
      bordered
      className="aicomic-compact-card"
      extra={<Button disabled={!activeEpisode} onClick={() => onOpenShotEditor()}>新增镜头</Button>}
    >
      {activeEpisode ? (
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Paragraph style={{ marginBottom: 0 }}>
            <Text strong>{activeEpisode.title}</Text>
            <Text type="secondary"> · {activeEpisode.creator_goal || '还没有补充本集目标'}</Text>
          </Paragraph>
          <List
            className="aicomic-tight-list"
            size="small"
            dataSource={activeEpisode.shots ?? []}
            locale={{ emptyText: '当前还没有镜头，先新增一个。' }}
            renderItem={(shot: ShotRecord) => (
              <List.Item
                actions={[
                  <Button key="edit" type="link" onClick={() => onOpenShotEditor(shot)}>编辑</Button>,
                  <Popconfirm
                    key="delete"
                    title="删除这个镜头？"
                    onConfirm={() => void onDeleteShot(shot)}
                  >
                    <Button type="link" danger>删除</Button>
                  </Popconfirm>,
                ]}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space wrap>
                    <Title level={5} style={{ margin: 0 }}>{shot.shot_id}</Title>
                    <Tag color={shot.ai_video ? 'purple' : 'default'}>
                      {shot.ai_video ? '智能视频镜头' : '静态镜头'}
                    </Tag>
                    <Tag color="blue">{displayPriority(shot.priority)}</Tag>
                    <Tag>{shot.duration} 秒</Tag>
                    {shot.act_id ? <Tag color="gold">{shot.act_id}</Tag> : null}
                    {shot.horror_beat ? <Tag color="volcano">{displayText(shot.horror_beat)}</Tag> : null}
                    {shot.avoidance_strategy ? <Tag color="geekblue">{displayText(shot.avoidance_strategy)}</Tag> : null}
                  </Space>
                  <Text>{shot.scene || '未设场景'}</Text>
                  <Text type="secondary">{shot.characters.join(' / ') || '未设角色'}</Text>
                  {shot.continuity_anchor || shot.sound_cue ? (
                    <Text type="secondary">
                      锚点：{displayText(shot.continuity_anchor || '-')} · 音效：{displayText(shot.sound_cue || '-')}
                    </Text>
                  ) : null}
                  <Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 2, tooltip: shot.visual || '-' }}>
                    {shot.visual || '未设画面描述'}
                  </Paragraph>
                  <Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 2, tooltip: shot.dialogue || '-' }}>
                    {shot.dialogue || '无台词'}
                  </Paragraph>
                </Space>
              </List.Item>
            )}
          />
        </Space>
      ) : (
        <Text type="secondary">先选择一个剧集。</Text>
      )}
    </ProCard>
  );
}
