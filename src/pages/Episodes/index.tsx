import { PageContainer, ProCard, ProTable } from '@ant-design/pro-components';
import { Alert, Button, Col, List, Progress, Row, Skeleton, Space, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import MetricCard from '@/components/MetricCard';
import CompactNoteList from '@/components/CompactNoteList';
import CompactSummaryCard from '@/components/CompactSummaryCard';
import { getEpisodes } from '@/services/api';
import type { EpisodeRecord, ListPayload } from '@/types/api';
import { displayStatus } from '@/utils/display';

const { Text } = Typography;

function statusColor(status: string) {
  if (status === 'done' || status === 'completed' || status === 'ready' || status === 'assets_ready') {
    return 'green';
  }
  if (status === 'current' || status === 'running' || status === 'script_ready' || status === 'shotlist_ready') {
    return 'blue';
  }
  return 'gold';
}

export default function EpisodesPage() {
  const [data, setData] = useState<ListPayload<EpisodeRecord>>();
  const [loading, setLoading] = useState(true);

  const mountedRef = useRef(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await getEpisodes();
      if (mountedRef.current) setData(payload);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadData();
    return () => { mountedRef.current = false; };
  }, [loadData]);

  const items = data?.items ?? [];
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((item) => {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
    });
    return Object.entries(counts).sort((left, right) => right[1] - left[1]);
  }, [items]);

  const previewReadyCount = items.filter((item) => item.preview_exists).length;
  const releaseReadyCount = items.filter((item) => item.release_exists).length;
  const publishPackReadyCount = items.filter((item) => item.publish_pack_exists).length;
  const totalShots = items.reduce((sum, item) => sum + item.shot_count, 0);
  const totalDurationMinutes = Math.round((items.reduce((sum, item) => sum + item.total_duration_seconds, 0) / 60) * 10) / 10;
  const totalJobs = items.reduce((sum, item) => sum + item.total_jobs, 0);
  const completedJobs = items.reduce((sum, item) => sum + item.completed_jobs, 0);
  const weightedCompletionRate = totalJobs > 0 ? Math.round((completedJobs / totalJobs) * 100) : 0;
  const aiVideoShotCount = items.reduce((sum, item) => sum + item.ai_video_shot_count, 0);
  const staticShotCount = items.reduce((sum, item) => sum + item.static_shot_count, 0);
  const fullyReadyCount = items.filter((item) => item.preview_exists && item.release_exists && item.publish_pack_exists).length;
  const previewGapCount = items.filter((item) => !item.preview_exists).length;
  const releaseGapCount = items.filter((item) => !item.release_exists).length;
  const publishPackGapCount = items.filter((item) => !item.publish_pack_exists).length;
  const averageShots = items.length ? Math.round((totalShots / items.length) * 10) / 10 : 0;
  const averageDurationSeconds = items.length ? Math.round(items.reduce((sum, item) => sum + item.total_duration_seconds, 0) / items.length) : 0;
  const releaseGapEpisodes = items
    .filter((item) => !item.preview_exists || !item.release_exists || !item.publish_pack_exists)
    .map((item) => {
      const missing: string[] = [];
      if (!item.preview_exists) missing.push('预览');
      if (!item.release_exists) missing.push('正式版');
      if (!item.publish_pack_exists) missing.push('发布包');
      return {
        key: item.episode_code,
        episodeCode: item.episode_code,
        missing,
      };
    })
    .slice(0, 3);
  const contentNotes = items
    .map((item) => ({
      key: item.episode_code,
      episodeCode: item.episode_code,
      title: item.publish_title || item.title,
      note: item.cover_text || '未填写封面文案',
    }))
    .slice(0, 4);
  const episodeReleaseNotes = items.map((item) => ({
    key: item.episode_code,
    episodeCode: item.episode_code,
    title: item.title,
    publishTitle: item.publish_title || '未设置发布标题',
    coverText: item.cover_text || '未填写封面文案',
    aiVideoShotCount: item.ai_video_shot_count,
    staticShotCount: item.static_shot_count,
    previewExists: item.preview_exists,
    releaseExists: item.release_exists,
    publishPackExists: item.publish_pack_exists,
  }));

  return (
    <PageContainer
      title="剧集"
      subTitle="查看剧集进度、产物与镜头结构"
      className="aicomic-compact-page"
      extra={[
        <Button key="refresh" size="small" icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>,
      ]}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={18}>
            <CompactSummaryCard
              title="剧集状态与产物摘要"
              tags={(
                <>
                  {statusCounts.length ? (
                    statusCounts.map(([status, count]) => (
                      <Tag key={status} color={statusColor(status)}>
                        {displayStatus(status)} {count}
                      </Tag>
                    ))
                  ) : (
                    <Tag>暂无剧集数据</Tag>
                  )}
                  <Tag color={previewReadyCount > 0 ? 'green' : 'default'}>预览 {previewReadyCount}</Tag>
                  <Tag color={releaseReadyCount > 0 ? 'green' : 'default'}>正式版 {releaseReadyCount}</Tag>
                  <Tag color={publishPackReadyCount > 0 ? 'green' : 'default'}>发布包 {publishPackReadyCount}</Tag>
                </>
              )}
              facts={[
                { label: '累计镜头', value: totalShots },
                { label: '总时长', value: `${totalDurationMinutes} 分钟` },
                { label: '任务完成率', value: `${weightedCompletionRate}%` },
                { label: '完整就绪', value: `${fullyReadyCount}/${items.length || 0}` },
                { label: 'AI 视频镜头', value: aiVideoShotCount },
                { label: '静态镜头', value: staticShotCount },
                { label: '平均镜头', value: averageShots },
                { label: '平均时长', value: `${averageDurationSeconds} 秒` },
              ]}
              notes={[
                <Text key="episode-summary" type="secondary" className="aicomic-section-note">
                  当前共 {data?.count ?? 0} 集，发布前优先看完整就绪数和右侧缺口列表，再逐集补预览、正式版和发布包。
                </Text>,
                '当前摘要同时覆盖进度、镜头结构和发布物料，方便个人创作者在单页内完成发布前核对。',
                '若后续新增剧集或产物缺口，也会先在完整就绪、镜头结构和任务完成率这几项数字里体现出来。',
              ]}
            />
          </Col>
          <Col xs={24} xl={6}>
            <CompactSummaryCard
              title="发布就绪检查"
              tags={(
                <>
                  <Tag color={fullyReadyCount === items.length && items.length > 0 ? 'green' : 'blue'}>
                    全量就绪 {fullyReadyCount}/{items.length || 0}
                  </Tag>
                  <Tag color={publishPackGapCount > 0 ? 'gold' : 'green'}>缺发布包 {publishPackGapCount}</Tag>
                </>
              )}
              facts={[
                { label: 'AI 视频 / 静态镜头', value: `${aiVideoShotCount} / ${staticShotCount}` },
                { label: '缺预览 / 缺正式版', value: `${previewGapCount} / ${releaseGapCount}` },
                { label: '缺发布包', value: publishPackGapCount },
                { label: '已完整就绪', value: fullyReadyCount },
              ]}
              minColumnWidth={180}
            >
              {releaseGapEpisodes.length ? (
                <List
                  className="aicomic-tight-list"
                  size="small"
                  split={false}
                  dataSource={releaseGapEpisodes}
                  renderItem={(item) => (
                    <List.Item style={{ paddingBlock: 1 }}>
                      <Space size={8} wrap>
                        <Tag color="blue">{item.episodeCode}</Tag>
                        <Text type="secondary">缺 {item.missing.join(' / ')}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              ) : (
                <Text type="secondary">当前没有发布缺口。</Text>
              )}
            </CompactSummaryCard>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="剧集数" value={data?.count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="总镜头" value={totalShots} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="总时长" value={totalDurationMinutes} suffix="分钟" />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="任务完成率" value={weightedCompletionRate} suffix="%" />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="预览就绪" value={previewReadyCount} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="发布包就绪" value={publishPackReadyCount} />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={16}>
            <ProCard title={`剧集明细（${data?.count ?? 0}）`} bordered className="aicomic-compact-card">
              {items.length ? (
                <ProTable<EpisodeRecord>
                  size="small"
                  scroll={{ x: 'max-content' }}
                  rowKey="episode_code"
                  search={false}
                  options={false}
                  loading={loading}
                  pagination={items.length > 12 ? { pageSize: 12, showSizeChanger: true } : false}
                  tableExtraRender={() => (
                    <Text type="secondary" className="aicomic-console-table-note">
                      表格保留剧集编码、标题、镜头结构、任务进度和三类交付产物，用来快速确认哪一集还缺发布前关键物料。
                    </Text>
                  )}
                  dataSource={items}
                  columns={[
                    { title: '剧集', dataIndex: 'episode_code', width: 90 },
                    { title: '标题', dataIndex: 'title', width: 220, ellipsis: true },
                    { title: '发布标题', dataIndex: 'publish_title', width: 220, ellipsis: true },
                    {
                      title: '状态',
                      dataIndex: 'status',
                      width: 110,
                      render: (_, record) => <Tag color={statusColor(record.status)}>{displayStatus(record.status)}</Tag>,
                    },
                    {
                      title: '镜头 / 时长',
                      width: 150,
                      render: (_, record) => `${record.shot_count} 镜头 / ${record.total_duration_seconds} 秒`,
                    },
                    {
                      title: '镜头构成',
                      width: 140,
                      render: (_, record) => `AI ${record.ai_video_shot_count} / 静态 ${record.static_shot_count}`,
                    },
                    {
                      title: '任务进度',
                      width: 220,
                      render: (_, record) => {
                        const percent = record.total_jobs > 0 ? Math.round((record.completed_jobs / record.total_jobs) * 100) : 0;
                        return (
                          <Space direction="vertical" size={2} style={{ width: '100%' }}>
                            <Text type="secondary">
                              {record.completed_jobs}/{record.total_jobs} 任务
                            </Text>
                            <Progress percent={percent} size="small" />
                          </Space>
                        );
                      },
                    },
                    {
                      title: '产物',
                      width: 220,
                      render: (_, record) => (
                        <Space wrap size={[4, 4]}>
                          <Tag color={record.preview_exists ? 'green' : 'gold'}>预览</Tag>
                          <Tag color={record.release_exists ? 'green' : 'gold'}>正式版</Tag>
                          <Tag color={record.publish_pack_exists ? 'green' : 'gold'}>发布包</Tag>
                        </Space>
                      ),
                    },
                  ]}
                />
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message="当前暂无剧集数据"
                  description="完成项目初始化或生成剧集蓝图后，这里会展示剧集进度、产物与任务完成率。"
                />
              )}
            </ProCard>
          </Col>
          <Col xs={24} xl={8}>
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              <CompactSummaryCard
                title="发布标题与封面文案"
                facts={[
                  { label: '抽样条数', value: contentNotes.length },
                  { label: '完整就绪剧集', value: `${fullyReadyCount}/${items.length || 0}` },
                ]}
                notes={[
                  `当前整理 ${contentNotes.length} 条发布标题与封面文案，主要用于发布前快速核对对外展示内容。`,
                  '这里主要检查对外展示口径是否统一，包括发布标题、封面文案和单集对外表达是否一致。',
                  '如果标题、封面和单集钩子不一致，优先在这里收口，再进入最终发布前复核。',
                ]}
              >
                {contentNotes.length ? (
                  <List
                    className="aicomic-tight-list"
                    size="small"
                    split={false}
                    dataSource={contentNotes}
                    renderItem={(item) => (
                      <List.Item style={{ paddingBlock: 2 }}>
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Space size={8} wrap>
                            <Tag color="blue">{item.episodeCode}</Tag>
                            <Text strong ellipsis={{ tooltip: item.title }}>
                              {item.title}
                            </Text>
                          </Space>
                          <Text type="secondary" ellipsis={{ tooltip: item.note }}>
                            {item.note}
                          </Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Text type="secondary">当前没有可展示的发布标题或封面文案。</Text>
                )}
              </CompactSummaryCard>

              <CompactSummaryCard
                title="任务与产物比例"
                facts={[
                  { label: '总任务', value: `${completedJobs}/${totalJobs || 0}` },
                  { label: '预览 / 正式版', value: `${previewReadyCount} / ${releaseReadyCount}` },
                  { label: '发布包', value: `${publishPackReadyCount}/${items.length || 0}` },
                  { label: '完整就绪', value: `${fullyReadyCount}/${items.length || 0}` },
                ]}
                minColumnWidth={180}
                notes={[
                  '该比例卡只负责看任务完成和交付产物覆盖，不再重复展开剧集标题与镜头结构。',
                  '当总任务已经完成但发布包仍未齐时，说明当前阻塞通常集中在最后的导出或发布整理环节。',
                  '如果预览、正式版和发布包比例不同步，优先回到对应剧集补最后一段交付链路。',
                  '这里更适合做跨剧集横向比较，用来判断当前到底是任务未跑完，还是产物导出还没有真正收口。',
                ]}
              />
            </Space>
          </Col>
        </Row>

        <ProCard title="按集发布摘要" bordered className="aicomic-compact-card">
          {episodeReleaseNotes.length ? (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <CompactNoteList
                items={[
                  '每行同时保留发布标题、封面文案、镜头结构和三类产物状态，用于逐集确认是否达到可发布条件。',
                  '这个区域偏向最终发布前核对，适合在项目已接近完成时逐集做最后一轮检查。',
                ]}
              />
              <List
                size="small"
                split
                dataSource={episodeReleaseNotes}
                renderItem={(item) => (
                  <List.Item style={{ paddingBlock: 6 }}>
                    <Row gutter={[12, 8]} style={{ width: '100%' }}>
                      <Col xs={24} xl={7}>
                        <Space direction="vertical" size={2}>
                          <Space size={8} wrap>
                            <Tag color="blue">{item.episodeCode}</Tag>
                            <Text strong>{item.title}</Text>
                          </Space>
                          <Text type="secondary" ellipsis={{ tooltip: item.publishTitle }}>
                            发布标题：{item.publishTitle}
                          </Text>
                        </Space>
                      </Col>
                      <Col xs={24} xl={9}>
                        <Space direction="vertical" size={2} style={{ width: '100%' }}>
                          <Text type="secondary" ellipsis={{ tooltip: item.coverText }}>
                            封面文案：{item.coverText}
                          </Text>
                          <Text type="secondary">AI 视频 {item.aiVideoShotCount} / 静态 {item.staticShotCount}</Text>
                          <Text type="secondary">
                            {item.previewExists && item.releaseExists && item.publishPackExists
                              ? '产物已完整，可直接进入发布前复核。'
                              : '仍需补齐预览、正式版或发布包后再发布。'}
                          </Text>
                        </Space>
                      </Col>
                      <Col xs={24} xl={4}>
                        <Space wrap size={[4, 4]}>
                          <Tag>AI 视频 {item.aiVideoShotCount}</Tag>
                          <Tag>静态 {item.staticShotCount}</Tag>
                        </Space>
                      </Col>
                      <Col xs={24} xl={4}>
                        <Space wrap size={[4, 4]}>
                          <Tag color={item.previewExists ? 'green' : 'gold'}>预览</Tag>
                          <Tag color={item.releaseExists ? 'green' : 'gold'}>正式版</Tag>
                          <Tag color={item.publishPackExists ? 'green' : 'gold'}>发布包</Tag>
                        </Space>
                      </Col>
                    </Row>
                  </List.Item>
                )}
              />
            </Space>
          ) : (
            <Text type="secondary">当前没有按集发布摘要。</Text>
          )}
        </ProCard>
      </Space>
      )}
    </PageContainer>
  );
}
