import { PageContainer, ProCard } from '@ant-design/pro-components';
import { Alert, Button, Col, List, Row, Skeleton, Space, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useState } from 'react';

import CompactFactGrid from '@/components/CompactFactGrid';
import MetricCard from '@/components/MetricCard';
import { getReviewMetrics } from '@/services/api';
import type { ReviewMetricsPayload } from '@/types/api';
import { displayBoolean, displayFieldLabel, displayStatus, displayText } from '@/utils/display';

const { Text } = Typography;

function SummaryCard({ title, source }: { title: string; source?: Record<string, unknown> }) {
  const entries = Object.entries(source ?? {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .slice(0, 5);

  const renderValue = (key: string, value: unknown) => {
    if (typeof value === 'boolean') {
      return displayBoolean(value);
    }
    if (value === undefined || value === null || value === '') {
      return '-';
    }
    if (typeof value === 'string') {
      if (key.includes('status')) {
        return displayStatus(value);
      }
      if (key.includes('report') || key.includes('path')) {
        const parts = value.split(/[\\/]/).filter(Boolean);
        return parts[parts.length - 1] ?? value;
      }
      return displayText(value);
    }
    return displayText(String(value));
  };

  return (
    <ProCard title={title} bordered className="aicomic-compact-card">
      {entries.length ? (
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          {entries.map(([key, value]) => (
            <div
              key={key}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <Text type="secondary" style={{ flex: '0 0 132px' }}>
                {displayFieldLabel(key)}
              </Text>
              <Text style={{ flex: 1, textAlign: 'right' }}>
                {renderValue(key, value)}
              </Text>
            </div>
          ))}
        </Space>
      ) : (
        '暂无数据'
      )}
    </ProCard>
  );
}

export default function ReviewPage() {
  const [data, setData] = useState<ReviewMetricsPayload>();
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getReviewMetrics();
      setData(result);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const metrics = data?.metrics ?? {};
  const counts = data?.counts ?? {};
  const riskFlags = data?.risk_flags ?? [];
  const recommendations = data?.recommendations ?? [];
  const blockingRiskCount = Number(counts.production_risk_blocking_count ?? 0);
  const warningRiskCount = Number(counts.production_risk_warning_count ?? 0);
  const localProviderReady = counts.production_local_provider_ready === true;
  const localVideoReady = counts.production_local_video_ready === true;
  const liveProviderReady = counts.production_live_provider_ready === true;
  const fallbackReady = counts.production_fallback_ready === true;
  const localReadyCount = Number(counts.local_ready_count ?? 0);
  const canProceedLocal = data?.status === 'healthy' && blockingRiskCount === 0 && localProviderReady && localVideoReady;
  const reviewAlertType = canProceedLocal ? 'success' : blockingRiskCount > 0 ? 'error' : 'warning';
  const reviewAlertMessage = canProceedLocal ? '当前可继续本地正式链路' : blockingRiskCount > 0 ? '当前仍有阻塞风险' : '当前仍需继续验收';
  const reviewAlertDescription = canProceedLocal
    ? `${liveProviderReady ? '本地链路与真实服务商均已就绪。' : '本地链路已就绪，真实服务商未就绪。'}`
    : blockingRiskCount > 0
      ? `当前存在 ${blockingRiskCount} 个阻塞风险，需先收口后再推进批量生产。`
      : '当前没有阻塞风险，但仍需结合服务商与回退口径继续验收。';

  return (
    <PageContainer
      title="数据复盘"
      subTitle="看当前链路成功率、风险提示和下一步动作"
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
          <Col xs={24} xl={10}>
            <ProCard title="复盘状态" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={data?.status === 'healthy' ? 'green' : 'gold'}>
                    {displayStatus(data?.status ?? 'unknown')}
                  </Tag>
                  <Tag color="blue">风险项 {riskFlags.length}</Tag>
                  <Tag color="cyan">建议 {recommendations.length}</Tag>
                  <Tag color={localProviderReady ? 'green' : 'gold'}>本地服务商 {displayBoolean(localProviderReady)}</Tag>
                  <Tag color={liveProviderReady ? 'green' : 'default'}>真实服务商 {displayBoolean(liveProviderReady)}</Tag>
                </Space>
                <Alert
                  type={reviewAlertType}
                  showIcon
                  message={reviewAlertMessage}
                />
                <CompactFactGrid
                  items={[
                    { label: '阻塞风险', value: blockingRiskCount },
                    { label: '警告风险', value: warningRiskCount },
                    { label: '本地就绪数', value: localReadyCount },
                    { label: '回退就绪', value: displayBoolean(fallbackReady) },
                    { label: '本地视频', value: displayBoolean(localVideoReady) },
                    { label: '建议动作', value: blockingRiskCount > 0 ? '先收口阻塞风险' : '可继续正式链路' },
                    { label: '任务成功率', value: `${Math.round((metrics.job_success_rate ?? 0) * 100)}%` },
                    { label: '剧集就绪率', value: `${Math.round((metrics.episode_ready_rate ?? 0) * 100)}%` },
                    { label: '当前结论', value: reviewAlertMessage },
                  ]}
                  minColumnWidth={120}
                />
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={14}>
            <SummaryCard
              title="来源报告"
              source={data?.source_reports}
            />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={12} md={8} xl={4}><MetricCard title="任务成功率" value={Math.round((metrics.job_success_rate ?? 0) * 100)} suffix="%" /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="剧集就绪率" value={Math.round((metrics.episode_ready_rate ?? 0) * 100)} suffix="%" /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="手工导入率" value={Math.round((metrics.manual_import_rate ?? 0) * 100)} suffix="%" /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="重试率" value={Math.round((metrics.retry_rate ?? 0) * 100)} suffix="%" /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="服务商预演率" value={Math.round((metrics.provider_dry_run_rate ?? 0) * 100)} suffix="%" /></Col>
          <Col xs={12} md={8} xl={4}><MetricCard title="告警数" value={riskFlags.length} /></Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} md={8}>
            <SummaryCard
              title="执行计数"
              source={{
                jobs_count: counts.jobs_count,
                succeeded_jobs: counts.succeeded_jobs,
                episodes_count: counts.episodes_count,
                ready_episode_count: counts.ready_episode_count,
                provider_request_count: counts.provider_request_count,
              }}
            />
          </Col>
          <Col xs={24} md={8}>
            <SummaryCard
              title="生产口径"
              source={{
                provider_readiness_status: counts.provider_readiness_status,
                production_risk_register_status: counts.production_risk_register_status,
                production_risk_blocking_count: counts.production_risk_blocking_count,
                production_risk_warning_count: counts.production_risk_warning_count,
                production_fallback_ready: counts.production_fallback_ready,
              }}
            />
          </Col>
          <Col xs={24} md={8}>
            <SummaryCard
              title="本地服务商"
              source={{
                local_dry_run_count: counts.local_dry_run_count,
                local_ready_count: counts.local_ready_count,
                production_local_provider_ready: counts.production_local_provider_ready,
                production_local_video_ready: counts.production_local_video_ready,
                production_live_provider_ready: counts.production_live_provider_ready,
              }}
            />
          </Col>
        </Row>

        {riskFlags.length ? (
          <Row gutter={[12, 12]}>
            <Col xs={24} xl={8}>
              <ProCard title="风险项" bordered className="aicomic-compact-card">
                <List
                  size="small"
                  dataSource={riskFlags}
                  renderItem={(item) => (
                    <List.Item>
                      <List.Item.Meta
                        title={<><Tag color={item.level === 'high' ? 'red' : item.level === 'info' ? 'blue' : 'gold'}>{displayStatus(item.level)}</Tag>{displayText(item.name)}</>}
                        description={displayText(item.detail)}
                      />
                    </List.Item>
                  )}
                />
              </ProCard>
            </Col>
            <Col xs={24} xl={16}>
              <ProCard title="建议" bordered className="aicomic-compact-card">
                <CompactFactGrid
                  items={[
                    { label: '当前建议数', value: recommendations.length },
                    { label: '阻塞风险', value: blockingRiskCount },
                    { label: '真实服务商', value: displayBoolean(liveProviderReady) },
                    { label: '建议主线', value: blockingRiskCount > 0 ? '先补风险闸门' : '进入正式渲染与发布包' },
                    { label: '回退就绪', value: displayBoolean(fallbackReady) },
                    { label: '首条建议', value: displayText(recommendations[0] ?? '当前没有建议') },
                  ]}
                  minColumnWidth={140}
                />
                <List
                  size="small"
                  dataSource={recommendations.slice(1)}
                  locale={{ emptyText: '当前没有建议' }}
                  renderItem={(item) => <List.Item>{displayText(item)}</List.Item>}
                />
              </ProCard>
            </Col>
          </Row>
        ) : (
          <Row gutter={[12, 12]}>
            <Col xs={24} xl={12}>
              <ProCard title="复盘结论" bordered className="aicomic-compact-card">
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color="green">当前没有阻塞风险项</Tag>
                    <Tag color="green">任务成功率 {Math.round((metrics.job_success_rate ?? 0) * 100)}%</Tag>
                    <Tag color="green">剧集就绪率 {Math.round((metrics.episode_ready_rate ?? 0) * 100)}%</Tag>
                  </Space>
                  <Text type="secondary">
                    本地服务商、任务成功率和回退口径已达到继续推进条件，本轮复盘未发现需要暂停生产的阻塞项。
                  </Text>
                </Space>
              </ProCard>
            </Col>
            <Col xs={24} xl={12}>
              <ProCard title="下一步动作" bordered className="aicomic-compact-card">
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color={localProviderReady ? 'green' : 'gold'}>本地服务商 {displayBoolean(localProviderReady)}</Tag>
                    <Tag color={liveProviderReady ? 'green' : 'default'}>真实服务商 {displayBoolean(liveProviderReady)}</Tag>
                    <Tag color={fallbackReady ? 'green' : 'gold'}>回退就绪 {displayBoolean(fallbackReady)}</Tag>
                  </Space>
                  <Text type="secondary">
                    当前可以进入正式版渲染和发布包阶段；真实服务商仍可按单独验收节奏继续补齐。
                  </Text>
                </Space>
              </ProCard>
            </Col>
          </Row>
        )}
      </Space>
      )}
    </PageContainer>
  );
}
