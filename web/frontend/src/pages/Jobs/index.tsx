import { PageContainer, ProCard, ProTable } from '@ant-design/pro-components';
import { Alert, Button, Col, Row, Skeleton, Space, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useMemo, useState } from 'react';

import MetricCard from '@/components/MetricCard';
import { getJobs } from '@/services/api';
import type { JobRecord } from '@/types/api';
import { displayStatus } from '@/utils/display';

const { Text } = Typography;

function statusColor(status: string) {
  if (status === 'succeeded' || status === 'completed') {
    return 'green';
  }
  if (status === 'failed' || status === 'manual_required' || status === 'blocked') {
    return 'red';
  }
  if (status === 'running' || status === 'active') {
    return 'blue';
  }
  return 'gold';
}

function isSuccessStatus(status: string) {
  return status === 'succeeded' || status === 'completed';
}

function isFailedStatus(status: string) {
  return status === 'failed' || status === 'manual_required' || status === 'blocked';
}

function isActiveStatus(status: string) {
  return status === 'running' || status === 'active' || status === 'queued';
}

function isPendingStatus(status: string) {
  return !isSuccessStatus(status) && !isFailedStatus(status) && !isActiveStatus(status);
}

function jobTypeLabel(jobType: string) {
  if (jobType === 'image') return '图片';
  if (jobType === 'video') return '视频';
  if (jobType === 'tts') return '配音';
  return jobType;
}

export default function JobsPage() {
  const [data, setData] = useState<{ items: JobRecord[]; count: number }>();
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getJobs();
      setData(result);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const items = data?.items ?? [];
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((item) => {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
    });
    return Object.entries(counts).sort((left, right) => right[1] - left[1]);
  }, [items]);

  const providerCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((item) => {
      counts[item.provider] = (counts[item.provider] ?? 0) + 1;
    });
    return Object.entries(counts).sort((left, right) => right[1] - left[1]);
  }, [items]);

  const uniqueEpisodeCount = new Set(items.map((item) => item.episode_code).filter(Boolean)).size;
  const uniqueProviderCount = providerCounts.length;
  const succeededCount = items.filter((item) => isSuccessStatus(item.status)).length;
  const activeCount = items.filter((item) => isActiveStatus(item.status)).length;
  const failedCount = items.filter((item) => isFailedStatus(item.status)).length;
  const pendingCount = items.filter((item) => isPendingStatus(item.status)).length;
  const dominantProvider = providerCounts[0]?.[0] ?? '-';
  const jobTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items.forEach((item) => {
      counts[item.job_type] = (counts[item.job_type] ?? 0) + 1;
    });
    return Object.entries(counts).sort((left, right) => right[1] - left[1]);
  }, [items]);
  const pendingEpisodeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    items
      .filter((item) => isPendingStatus(item.status))
      .forEach((item) => {
        const episodeCode = item.episode_code || '未分配剧集';
        counts[episodeCode] = (counts[episodeCode] ?? 0) + 1;
      });
    return Object.entries(counts).sort((left, right) => right[1] - left[1]);
  }, [items]);

  return (
    <PageContainer
      title="任务"
      subTitle="按剧集、服务商与状态查看当前任务负载"
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
          <Col xs={24} xl={12}>
            <ProCard title="任务状态摘要" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space wrap>
                  {statusCounts.length ? (
                    statusCounts.map(([status, count]) => (
                      <Tag key={status} color={statusColor(status)}>
                        {displayStatus(status)} {count}
                      </Tag>
                    ))
                  ) : (
                    <Tag>暂无任务</Tag>
                  )}
                </Space>
                <Space wrap>
                  <Tag>总任务 {data?.count ?? 0}</Tag>
                  <Tag>剧集 {uniqueEpisodeCount}</Tag>
                  <Tag>服务商 {uniqueProviderCount}</Tag>
                  <Tag>待处理 {pendingCount}</Tag>
                  <Tag>运行中 {activeCount}</Tag>
                  <Tag>主要剧集 {pendingEpisodeCounts[0]?.[0] ?? '-'}</Tag>
                  <Tag>主要服务商 {dominantProvider}</Tag>
                </Space>
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={12}>
            <ProCard title="待处理聚焦" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="gold">主要剧集 {pendingEpisodeCounts[0]?.[0] ?? '-'}</Tag>
                  <Tag color="blue">主要服务商 {dominantProvider}</Tag>
                  {providerCounts.length ? (
                    providerCounts.slice(0, 6).map(([provider, count]) => (
                      <Tag key={provider} color="blue">
                        {provider} {count}
                      </Tag>
                    ))
                  ) : (
                    <Tag>暂无服务商数据</Tag>
                  )}
                </Space>
                <Space wrap>
                  {jobTypeCounts.length ? (
                    jobTypeCounts.map(([jobType, count]) => (
                      <Tag key={jobType} color="purple">
                        {jobTypeLabel(jobType)} {count}
                      </Tag>
                    ))
                  ) : (
                    <Tag>暂无类型分布</Tag>
                  )}
                </Space>
              </Space>
            </ProCard>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="任务总数" value={data?.count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="成功任务" value={succeededCount} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="待处理" value={pendingCount} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="失败/人工" value={failedCount} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="剧集数" value={uniqueEpisodeCount} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="服务商数" value={uniqueProviderCount} />
          </Col>
        </Row>

        <ProCard title={`任务明细（${data?.count ?? 0}）`} bordered className="aicomic-compact-card">
          <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
            任务表按编号、剧集、类型、服务商和状态展示当前负载。优先关注“待处理”任务集中在哪一集、哪一种类型，避免只看总数看不出堵点。
          </Text>
          {items.length ? (
            <ProTable<JobRecord>
              size="small"
              scroll={{ x: 'max-content' }}
              rowKey="job_id"
              search={false}
              options={false}
              loading={loading}
              pagination={items.length > 12 ? { pageSize: 12, showSizeChanger: true } : false}
              dataSource={items}
              columns={[
                { title: '任务编号', dataIndex: 'job_id', copyable: true, width: 220, ellipsis: true },
                {
                  title: '剧集 / 镜头',
                  width: 180,
                  render: (_, record) => (
                    <Space size={6} wrap>
                      <Tag color="blue">{record.episode_code || '-'}</Tag>
                      <Text type="secondary">{record.shot_id || '整集任务'}</Text>
                    </Space>
                  ),
                },
                {
                  title: '类型',
                  dataIndex: 'job_type',
                  width: 140,
                  render: (_, record) => jobTypeLabel(record.job_type),
                },
                { title: '服务商', dataIndex: 'provider', width: 180, ellipsis: true },
                {
                  title: '状态',
                  dataIndex: 'status',
                  width: 120,
                  render: (_, record) => <Tag color={statusColor(record.status)}>{displayStatus(record.status)}</Tag>,
                },
              ]}
            />
          ) : (
            <Alert
              type="info"
              showIcon
              message="当前暂无任务数据"
              description="生成任务包或执行批次后，这里会展示剧集、镜头、服务商与状态。"
            />
          )}
        </ProCard>
      </Space>
      )}
    </PageContainer>
  );
}
