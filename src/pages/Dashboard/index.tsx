import { PageContainer, ProCard } from '@ant-design/pro-components';
import { Button, Col, List, Progress, Row, Skeleton, Space, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useRef, useState } from 'react';

import MetricCard from '@/components/MetricCard';
import CompactNoteList from '@/components/CompactNoteList';
import CompactSummaryCard from '@/components/CompactSummaryCard';
import { getDashboard, getEdition } from '@/services/api';
import type { DashboardPayload, EditionCapabilityPayload } from '@/types/api';
import { displayBoolean, displayEditionName, displayEnabled, displayFieldLabel, displayStatus, displayText } from '@/utils/display';

const { Text } = Typography;

function formatSummaryValue(value: unknown, key?: string): string {
  if (value === undefined || value === null || value === '') return '-';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return displayBoolean(value);
  if (typeof value === 'string') {
    if (key?.includes('edition_name')) {
      return displayEditionName(value);
    }
    if (value.includes('/') && value.endsWith('.json')) {
      const parts = value.split(/[\\\\/]/).filter(Boolean);
      return parts[parts.length - 1] ?? value;
    }
    if (key?.includes('path') || key?.includes('id')) {
      return value;
    }
    return key?.includes('status') || key?.includes('enabled') ? displayStatus(value) : displayText(value);
  }
  if (Array.isArray(value)) return value.join(', ') || '-';
  return Object.entries(value as Record<string, unknown>)
    .map(([itemKey, item]) => `${displayFieldLabel(itemKey)}：${formatSummaryValue(item, itemKey)}`)
    .join(' / ');
}

function SummaryCard({
  title,
  source,
  columns = 1,
  maxItems = 8,
}: {
  title: string;
  source?: Record<string, unknown>;
  columns?: 1 | 2 | 3;
  maxItems?: number;
}) {
  const entries = Object.entries(source ?? {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .slice(0, maxItems);
  return (
    <CompactSummaryCard
      title={title}
      minColumnWidth={columns === 1 ? 220 : columns === 2 ? 180 : 140}
      facts={entries.map(([key, value]) => ({
        key,
        label: displayFieldLabel(key),
        value: (
          <Text ellipsis={{ tooltip: formatSummaryValue(value, key) }}>
            {formatSummaryValue(value, key)}
          </Text>
        ),
      }))}
    >
      {entries.length ? null : <Text type="secondary">暂无数据</Text>}
    </CompactSummaryCard>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardPayload>();
  const [edition, setEdition] = useState<EditionCapabilityPayload>();
  const [loading, setLoading] = useState(true);

  const mountedRef = useRef(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [dashboardPayload, editionPayload] = await Promise.all([getDashboard(), getEdition()]);
      if (mountedRef.current) {
        setData(dashboardPayload);
        setEdition(editionPayload);
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadData();
    return () => { mountedRef.current = false; };
  }, [loadData]);

  const overview = data?.overview ?? {};
  const episodeStates = Object.values(data?.episode_states ?? {});
  const jobStatusByEpisode = data?.job_status_by_episode ?? {};
  const nextActions = data?.next_actions ?? [];
  const totalEpisodes = overview.episodes ?? 0;
  const totalBatches = overview.batches ?? 0;
  const totalJobs = overview.jobs ?? 0;
  const dashboardRemainingJobs = episodeStates.reduce(
    (sum, item) => sum + Math.max((item.total_jobs ?? 0) - (item.completed_jobs ?? 0), 0),
    0,
  );
  const dashboardReadyEpisodes = episodeStates.filter((item) => {
    const status = item.status ?? '';
    const statusLabel = displayStatus(status);
    const totalJobs = item.total_jobs ?? 0;
    const completedJobs = item.completed_jobs ?? 0;
    return (
      ['done', 'completed', 'ready', 'assets_ready'].includes(status)
      || statusLabel === '素材就绪'
      || (totalJobs > 0 && completedJobs >= totalJobs)
    );
  }).length;
  const episodeRows = episodeStates.map((item) => {
    const totalJobs = item.total_jobs ?? 0;
    const completedJobs = item.completed_jobs ?? 0;
    const remainingJobs = Math.max(totalJobs - completedJobs, 0);
    const percent = totalJobs ? Math.round((completedJobs / totalJobs) * 100) : 0;
    const jobSummary = Object.entries(jobStatusByEpisode[item.episode_code ?? ''] ?? {})
      .map(([key, value]) => `${displayFieldLabel(key)} ${value}`)
      .join(' / ');

    return {
      key: item.episode_code ?? `episode-${item.status ?? 'unknown'}`,
      episodeCode: item.episode_code ?? '-',
      statusLabel: displayStatus(item.status ?? 'unknown'),
      totalJobs,
      completedJobs,
      remainingJobs,
      percent,
      jobSummary: jobSummary || '暂无任务状态明细',
    };
  });
  const dashboardModeLabel = dashboardRemainingJobs > 0 ? '继续推进中' : '可进入发布复核';
  const dashboardConclusion =
    dashboardRemainingJobs > 0
      ? `当前仍有 ${dashboardRemainingJobs} 个剩余任务，先处理阻塞，再决定回哪个项目继续推进。`
      : '当前主链健康，可直接进入项目页或创作者页继续审核与放行。';

  return (
    <PageContainer
      title="总控板"
      subTitle="先判断系统状态，再决定去哪个项目"
      className="aicomic-compact-page"
      extra={[
        <Button key="refresh" size="small" icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>,
        <Button key="creator" size="small" href="/creator">进入工作台</Button>,
        <Button key="projects" size="small" href="/projects">查看项目队列</Button>,
      ]}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={14}>
            <CompactSummaryCard
              title="当前是否能继续推进"
              tags={(
                <>
                  <Tag color={data?.status === 'needs_attention' ? 'gold' : 'green'}>
                    {displayStatus(data?.status ?? 'unknown')}
                  </Tag>
                  <Tag color="blue">{displayEditionName(edition?.display_name ?? 'unknown')}</Tag>
                  <Tag color={dashboardRemainingJobs > 0 ? 'gold' : 'green'}>{dashboardModeLabel}</Tag>
                  <Tag>项目 {overview.projects ?? 0}</Tag>
                  <Tag>剧集 {totalEpisodes}</Tag>
                  <Tag>任务 {totalJobs}</Tag>
                  <Tag>批次 {totalBatches}</Tag>
                </>
              )}
              facts={[
                { label: '成功任务', value: overview.succeeded_jobs ?? 0 },
                { label: '剩余任务', value: dashboardRemainingJobs },
                { label: '就绪剧集', value: `${dashboardReadyEpisodes}/${episodeStates.length || 0}` },
                { label: '批次运行', value: overview.batch_runs ?? 0 },
              ]}
              notes={[
                <Text key="conclusion" type="secondary" className="aicomic-section-note">{dashboardConclusion}</Text>,
                '先看剩余任务、就绪剧集和批次运行，判断今天是继续生产，还是先修阻塞。',
                '这里不解释系统能力，只回答当前是否适合继续推进。',
                '如果状态异常，先去批次、任务或项目页定位问题，再回创作者页执行。',
              ]}
            />
          </Col>
          <Col xs={24} xl={10}>
            <CompactSummaryCard
              title="环境口径"
              tags={(
                <>
                  <Tag color={edition?.capabilities.auth_enabled ? 'green' : 'default'}>
                    鉴权 {displayEnabled(edition?.capabilities.auth_enabled)}
                  </Tag>
                  <Tag color={edition?.capabilities.single_user_mode ? 'green' : 'default'}>
                    单用户 {displayEnabled(edition?.capabilities.single_user_mode)}
                  </Tag>
                  <Tag color={edition?.capabilities.batch_enabled ? 'green' : 'default'}>
                    批量执行 {displayEnabled(edition?.capabilities.batch_enabled)}
                  </Tag>
                </>
              )}
              facts={[
                { label: '版本', value: displayEditionName(edition?.edition_name ?? 'unknown') },
                { label: '显示名称', value: displayEditionName(edition?.display_name ?? 'unknown') },
                { label: '工作台模式', value: '个人创作者' },
                { label: '当前建议', value: dashboardRemainingJobs > 0 ? '先处理阻塞' : '可进入项目页' },
                { label: '默认入口', value: '总控板 / 项目队列 / 创作者页' },
                { label: '鉴权模式', value: edition?.capabilities.auth_enabled ? '密码登录' : '匿名访问' },
                { label: '执行模式', value: edition?.capabilities.batch_enabled ? '支持批量执行' : '单次执行' },
              ]}
            />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={12} md={8} xl={4}><MetricCard title="项目数" value={overview.projects ?? 0} /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="季数" value={overview.seasons ?? 0} /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="剧集数" value={overview.episodes ?? 0} /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="任务数" value={overview.jobs ?? 0} /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="成功任务" value={overview.succeeded_jobs ?? 0} /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="批次运行" value={overview.batch_runs ?? 0} /></Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={16}>
            <SummaryCard
              title="批次 / 季进度 / 服务商"
              columns={2}
              maxItems={12}
              source={{
                batch_id: data?.batch?.batch_id,
                batch_status: data?.batch?.status,
                batch_step_count: data?.batch?.step_count,
                batch_completed_step_count: data?.batch?.completed_step_count,
                season_episode_count: data?.season?.episode_count,
                season_job_count: data?.season?.job_count,
                season_ready_episode_count: data?.season?.ready_episode_count,
                season_rendered_episode_count: data?.season?.rendered_episode_count,
                provider_count: data?.provider?.provider_count,
                provider_request_count: data?.provider?.request_count,
                provider_ready_request_count: data?.provider?.ready_request_count,
                provider_readiness_status: data?.provider?.readiness_status,
              }}
            />
          </Col>
          <Col xs={24} xl={8}>
            <CompactSummaryCard
              title="导入与重试 / 当前结论"
              facts={[
                {
                  label: '手工导入',
                  value: `已导入 ${formatSummaryValue(data?.manual_import?.imported_count, 'imported_count')} / 缺失 ${formatSummaryValue(data?.manual_import?.missing_count, 'missing_count')}`,
                },
                {
                  label: '导入后结果',
                  value: `成功 ${formatSummaryValue(data?.manual_import?.succeeded_after_import, 'succeeded_after_import')} / 人工处理 ${formatSummaryValue(data?.manual_import?.manual_required_after_import, 'manual_required_after_import')}`,
                },
                {
                  label: '重试',
                  value: `已重试 ${formatSummaryValue(data?.retry?.retried_count, 'retried_count')} / 范围内任务 ${formatSummaryValue(data?.retry?.scoped_job_count, 'scoped_job_count')}`,
                },
                {
                  label: '当前建议',
                  value: displayText(nextActions[0] ?? '当前没有待处理建议'),
                },
              ]}
              minColumnWidth={220}
            >
              <List
                className="aicomic-tight-list"
                size="small"
                split={false}
                dataSource={nextActions.slice(0, 3)}
                locale={{ emptyText: '当前没有待处理建议' }}
                renderItem={(item) => <List.Item style={{ paddingBlock: 2 }}>{displayText(item)}</List.Item>}
              />
            </CompactSummaryCard>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={7}>
            <CompactSummaryCard
              title="剧集状态"
              tags={(
                <>
                  <Tag color="green">已就绪 {dashboardReadyEpisodes}/{episodeStates.length || 0}</Tag>
                  <Tag color={dashboardRemainingJobs > 0 ? 'orange' : 'blue'}>剩余任务 {dashboardRemainingJobs}</Tag>
                  <Tag color={dashboardRemainingJobs > 0 ? 'gold' : 'purple'}>
                    {dashboardRemainingJobs > 0 ? '需继续推进' : '可发布前复核'}
                  </Tag>
                </>
              )}
              facts={[
                { label: '已完成任务', value: overview.succeeded_jobs ?? 0 },
                { label: '总任务', value: totalJobs },
                { label: '样本剧集', value: episodeStates.length || 0 },
              ]}
              notes={['剧集卡片只保留就绪数、剩余任务和当前结论，避免总览区再次展开长段解释。']}
            />
          </Col>

          <Col xs={24} xl={17}>
            <SummaryCard
              title="版本与来源"
              source={{
                edition_name: edition?.edition_name,
                edition_display_name: edition?.display_name,
                source_validation: data?.source_reports?.validation,
                source_batch_summary: data?.source_reports?.batch_summary,
                source_manual_import: data?.source_reports?.manual_import,
                source_retry_batch: data?.source_reports?.retry_batch,
              }}
              maxItems={6}
            />
          </Col>
        </Row>

        {episodeRows.length ? (
          <Row gutter={[12, 12]}>
            {episodeRows.map((record) => (
              <Col xs={24} md={12} key={record.key}>
                <ProCard
                  title={record.episodeCode}
                  extra={<Tag color="blue">{record.statusLabel}</Tag>}
                  bordered
                  className="aicomic-compact-card"
                >
                  <Space direction="vertical" size={6} style={{ width: '100%' }}>
                    <CompactNoteList
                      items={[
                        `当前集已完成 ${record.completedJobs}/${record.totalJobs} 个任务，剩余 ${record.remainingJobs} 个任务，当前完成度 ${record.percent}%。`,
                        record.jobSummary,
                      ]}
                    />
                    <Progress percent={record.percent} size="small" showInfo={false} />
                  </Space>
                </ProCard>
              </Col>
            ))}
          </Row>
        ) : null}
      </Space>
      )}
    </PageContainer>
  );
}
