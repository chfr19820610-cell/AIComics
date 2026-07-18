import { ProCard, ProTable } from '@ant-design/pro-components';
import { Button, Progress, Space, Tag, Typography } from 'antd';

import CompactFactGrid from '@/components/CompactFactGrid';
import type { EpisodeRecord, ShotRecord } from '@/types/api';
import { displayStatus, displayText } from '@/utils/display';

const { Text } = Typography;

type CreatorEpisode = EpisodeRecord & {
  creator_goal?: string;
  ending_hook?: string;
  job_status_distribution?: Record<string, number>;
  shots?: ShotRecord[];
};

type EpisodeTableProps = {
  episodes: CreatorEpisode[];
  activeEpisode?: CreatorEpisode;
  onSelectEpisode: (episodeCode: string) => void;
  onEditEpisode: (episode: CreatorEpisode) => void;
  previewReadyEpisodeCount: number;
  publishReadyEpisodeCount: number;
};

export default function EpisodeTable({
  episodes,
  activeEpisode,
  onSelectEpisode,
  onEditEpisode,
  previewReadyEpisodeCount,
  publishReadyEpisodeCount,
}: EpisodeTableProps) {
  return (
    <ProCard title={`剧集推进（${episodes.length ?? 0}）`} bordered className="aicomic-compact-card">
      <Space direction="vertical" size={8} style={{ width: '100%' }}>
        <Text type="secondary">这里只看每一集走到哪、完成度多少、产物是否齐。</Text>
        <CompactFactGrid
          items={[
            { label: '当前剧集', value: activeEpisode?.episode_code || '-' },
            { label: '当前标题', value: activeEpisode?.title || '-' },
            { label: '预览就绪', value: `${previewReadyEpisodeCount}/${episodes.length || 0}` },
            { label: '发布包就绪', value: `${publishReadyEpisodeCount}/${episodes.length || 0}` },
          ]}
          minColumnWidth={160}
        />
        <Text type="secondary">点击剧集行即可同步切换右侧详情和下方镜头列表。</Text>
        <ProTable<EpisodeRecord>
          size="small"
          rowKey="episode_code"
          search={false}
          options={false}
          pagination={false}
          tableExtraRender={() => (
            <Text type="secondary">表格只保留推进判断所需字段，用来快速挑出当前该推进的剧集。</Text>
          )}
          dataSource={episodes ?? []}
          onRow={(record) => ({
            onClick: () => onSelectEpisode(record.episode_code),
            tabIndex: 0,
            onKeyDown: (event: React.KeyboardEvent) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onSelectEpisode(record.episode_code);
              }
            },
            'aria-selected': record.episode_code === activeEpisode?.episode_code,
          })}
          rowClassName={(record) => (record.episode_code === activeEpisode?.episode_code ? 'creator-active-row' : '')}
          columns={[
            { title: '剧集编码', dataIndex: 'episode_code', width: 88 },
            {
              title: '标题 / 本集目标 / 封面',
              dataIndex: 'title',
              ellipsis: true,
              render: (_, record) => {
                const episode = record as CreatorEpisode;
                return (
                  <Space direction="vertical" size={0} style={{ width: '100%' }}>
                    <Text strong>{episode.title || episode.episode_code}</Text>
                    <Text type="secondary">
                      {episode.creator_goal || episode.publish_title || '待补本集目标'}
                    </Text>
                    <Text type="secondary">
                      {episode.cover_text || episode.ending_hook || '待补封面文案或结尾钩子'}
                    </Text>
                  </Space>
                );
              },
            },
            {
              title: '状态',
              dataIndex: 'status',
              width: 110,
              render: (_, record) => <Tag color="blue">{displayStatus(record.status)}</Tag>,
            },
            {
              title: '镜头数',
              dataIndex: 'shot_count',
              width: 76,
              render: (_, record) => `${record.shot_count} 镜头`,
            },
            {
              title: '时长',
              dataIndex: 'total_duration_seconds',
              width: 84,
              render: (_, record) => `${record.total_duration_seconds} 秒`,
            },
            {
              title: '任务完成度',
              width: 170,
              render: (_, record) => {
                const percent = record.total_jobs > 0 ? Math.round((record.completed_jobs / record.total_jobs) * 100) : 0;
                return (
                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                    <Progress percent={percent} size="small" />
                    <Text type="secondary">{record.completed_jobs}/{record.total_jobs} 项</Text>
                  </Space>
                );
              },
            },
            {
              title: '交付产物状态',
              width: 180,
              render: (_, record) => (
                <Space wrap size={[4, 4]}>
                  <Tag color={record.preview_exists ? 'green' : 'default'}>预览</Tag>
                  <Tag color={record.release_exists ? 'green' : 'default'}>正式版</Tag>
                  <Tag color={record.publish_pack_exists ? 'green' : 'default'}>发布包</Tag>
                </Space>
              ),
            },
            {
              title: '操作入口',
              width: 110,
              render: (_, record) => (
                <Button
                  type="link"
                  aria-label={`编辑 ${record.episode_code} 剧集详情`}
                  onClick={(event) => {
                    event.stopPropagation();
                    onEditEpisode(record as CreatorEpisode);
                  }}
                >
                  编辑剧集详情
                </Button>
              ),
            },
          ]}
        />
      </Space>
    </ProCard>
  );
}
