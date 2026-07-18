import { PageContainer, ProCard, ProTable } from '@ant-design/pro-components';
import { Alert, Button, Col, Row, Skeleton, Space, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useMemo, useState } from 'react';

import MetricCard from '@/components/MetricCard';
import CompactSummaryCard from '@/components/CompactSummaryCard';
import { getProviderExecutions } from '@/services/api';
import type { ProviderExecutionRecord } from '@/types/api';
import { displayBoolean } from '@/utils/display';

const { Text } = Typography;

export default function ProviderPage() {
  const [data, setData] = useState<{ items: ProviderExecutionRecord[]; count: number }>();
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getProviderExecutions();
      setData(result);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const items = data?.items ?? [];
  const totalRequests = items.reduce((sum, item) => sum + item.request_count, 0);
  const totalSuccess = items.reduce((sum, item) => sum + item.success_count, 0);
  const totalFailed = items.reduce((sum, item) => sum + item.failed_count, 0);
  const totalBlocked = items.reduce((sum, item) => sum + item.blocked_count, 0);
  const totalDryRun = items.reduce((sum, item) => sum + item.dry_run_count, 0);
  const confirmLiveCount = items.filter((item) => item.confirm_live).length;
  const successRate = totalRequests > 0 ? Math.round((totalSuccess / totalRequests) * 100) : 0;
  const blockedRate = totalRequests > 0 ? Math.round((totalBlocked / totalRequests) * 100) : 0;
  const topFailures = useMemo(
    () => [...items].sort((left, right) => right.failed_count - left.failed_count).slice(0, 6),
    [items],
  );

  return (
    <PageContainer
      title="服务商执行"
      subTitle="查看执行口径、失败分布与真实执行保护状态"
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
          <Col xs={24} xl={15}>
            <CompactSummaryCard
              title="真实联网执行保护"
              tags={(
                <>
                  <Tag color={confirmLiveCount > 0 ? 'red' : 'default'}>真实确认 {confirmLiveCount}</Tag>
                  <Tag color={totalBlocked > 0 ? 'orange' : 'green'}>已阻止 {totalBlocked}</Tag>
                  <Tag color={totalFailed > 0 ? 'red' : 'green'}>失败 {totalFailed}</Tag>
                  <Tag color="blue">预演优先</Tag>
                </>
              )}
              facts={[
                { label: '累计请求', value: totalRequests },
                { label: '成功率', value: `${successRate}%` },
                { label: '预演请求', value: totalDryRun },
                { label: '当前模式', value: confirmLiveCount > 0 ? '含真实确认' : '仅预演' },
              ]}
              notes={[
                '默认不开放真实联网执行；只有在显式确认、失败阈值和回滚口径都满足后，才允许进入小流量真实调用。',
                '这张卡优先回答当前是否还在预演态、是否已经出现真实确认，以及是否有必要继续停留在保护状态。',
                '只要真实确认仍为 0，就应把重点放在失败分布、阻止策略和报告覆盖率，而不是直接推进真实调用。',
              ]}
            >
              <Alert
                message="真实调用必须晚于预演收口"
                description="先把失败分布、阻止策略和回滚口径压稳，再决定是否进入真实流量验收。"
                type="warning"
                showIcon
                className="aicomic-compact-banner"
              />
            </CompactSummaryCard>
          </Col>
          <Col xs={24} xl={9}>
            <CompactSummaryCard
              title="真实执行门槛"
              tags={(
                <>
                  <Tag color={confirmLiveCount > 0 ? 'red' : 'default'}>confirm-live</Tag>
                  <Tag color={totalBlocked > 0 ? 'orange' : 'green'}>阻止策略</Tag>
                  <Tag color={totalFailed > 0 ? 'red' : 'green'}>失败阈值</Tag>
                  <Tag color="blue">回滚口径</Tag>
                </>
              )}
              facts={[
                { label: '真实确认', value: confirmLiveCount },
                { label: '已阻止', value: totalBlocked },
                { label: '失败数', value: totalFailed },
              ]}
              notes={[
                '当前仍应先在预演态收口，再决定是否放开真实调用。',
                '门槛区只保留 confirm-live、阻止策略、失败阈值和回滚口径四个判断点，用来快速判断是否具备放量资格。',
                '只要这四项里有一项不稳定，就不应把当前 Provider 报告视为可直接进入真实生产流量。',
                '当真实确认仍为 0 且阻止策略仍在触发时，默认结论就应该是继续预演而不是尝试放开真实调用。',
              ]}
            />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={14}>
            <CompactSummaryCard
              title="执行摘要"
              tags={(
                <>
                  <Tag color="blue">报告 {data?.count ?? 0}</Tag>
                  <Tag color="green">成功率 {successRate}%</Tag>
                  <Tag color={confirmLiveCount > 0 ? 'red' : 'default'}>真实执行确认 {confirmLiveCount}</Tag>
                  <Tag color={totalBlocked > 0 ? 'orange' : 'green'}>已阻止 {totalBlocked}</Tag>
                </>
              )}
              facts={[
                { label: '累计请求', value: totalRequests },
                { label: '成功数', value: totalSuccess },
                { label: '预演请求', value: totalDryRun },
                { label: '阻止率', value: `${blockedRate}%` },
                { label: '失败报告', value: topFailures.filter((item) => item.failed_count > 0).length },
                { label: '当前模式', value: confirmLiveCount > 0 ? '含真实确认' : '以预演为主' },
              ]}
              notes={[
                '当前优先看真实执行确认、阻止策略和失败是否集中在少数报告，避免未收口前直接放开真实流量。',
                `当前共有 ${data?.count ?? 0} 份报告，主要围绕本地预演、外部模型预演和安全阻止口径展开。`,
                '只有当真实确认、失败阈值和回滚口径三项同时稳定后，才建议从当前摘要进一步进入小流量真实执行。',
              ]}
            />
          </Col>
          <Col xs={24} xl={10}>
            <CompactSummaryCard
              title="失败较高的报告"
              facts={[
                { label: '高失败样本', value: topFailures.length },
                { label: '总失败数', value: totalFailed },
                { label: '总阻止数', value: totalBlocked },
              ]}
              notes={[
                '按失败数倒序展示最需要关注的报告；若失败为 0 但阻止或预演很多，说明当前更多是保护阈值在生效。',
                '这个区域只用于判断问题是否集中在少数报告，后续再回到表格查看具体路径和确认口径。',
              ]}
            >
              <Space wrap>
                {topFailures.length ? (
                  topFailures.map((item) => (
                    <Tag key={item.name} color={item.failed_count > 0 ? 'red' : 'default'}>
                      {item.name} 失败 {item.failed_count}
                    </Tag>
                  ))
                ) : (
                  <Tag>暂无数据</Tag>
                )}
              </Space>
            </CompactSummaryCard>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="报告数" value={data?.count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="请求数" value={totalRequests} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="成功率" value={successRate} suffix="%" />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="失败数" value={totalFailed} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="预演数" value={totalDryRun} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <MetricCard title="已阻止" value={totalBlocked} />
          </Col>
        </Row>

        <ProCard title={`服务商报告（${data?.count ?? 0}）`} bordered className="aicomic-compact-card">
          <Text type="secondary" className="aicomic-console-table-note" style={{ marginBottom: 8 }}>
            报告表保留请求、成功率、失败、预演、阻止和真实执行确认几个核心字段，便于快速判断当前是“可继续预演”、还是“可以进入小流量真实执行”。
          </Text>
          {items.length ? (
            <ProTable<ProviderExecutionRecord>
              size="small"
              scroll={{ x: 'max-content' }}
              rowKey="name"
              search={false}
              options={false}
              loading={loading}
              pagination={items.length > 10 ? { pageSize: 10, showSizeChanger: true } : false}
              dataSource={items}
              columns={[
                { title: '报告', dataIndex: 'name', width: 200, ellipsis: true },
                { title: '请求数', dataIndex: 'request_count', width: 90 },
                {
                  title: '成功率',
                  width: 110,
                  render: (_, record) => {
                    const rate = record.request_count > 0 ? Math.round((record.success_count / record.request_count) * 100) : 0;
                    return `${rate}%`;
                  },
                },
                { title: '失败', dataIndex: 'failed_count', width: 80 },
                { title: '预演', dataIndex: 'dry_run_count', width: 80 },
                { title: '已阻止', dataIndex: 'blocked_count', width: 80 },
                {
                  title: '真实执行确认',
                  dataIndex: 'confirm_live',
                  width: 120,
                  render: (_, record) => (
                    <Tag color={record.confirm_live ? 'red' : 'purple'}>{displayBoolean(record.confirm_live)}</Tag>
                  ),
                },
                { title: '路径', dataIndex: 'path', ellipsis: true },
              ]}
            />
          ) : (
            <Alert
              type="info"
              showIcon
              message="当前暂无服务商执行报告"
              description="执行预演、真实确认或导出报告后，这里会展示请求、成功率、失败数与路径。"
            />
          )}
        </ProCard>
      </Space>
      )}
    </PageContainer>
  );
}
