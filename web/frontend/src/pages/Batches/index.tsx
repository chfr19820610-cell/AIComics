import { PageContainer, ProCard, ProTable } from '@ant-design/pro-components';
import { Alert, Button, Col, Descriptions, Input, Popconfirm, Progress, Row, Skeleton, Space, Tabs, Tag, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { useCallback, useEffect, useState } from 'react';
import { usePagination } from '@/hooks/usePagination';

import MetricCard from '@/components/MetricCard';
import {
  cleanupBatchExecutionArchives,
  exportBatchExecutionOperationsReport,
  generateBatchRetryPackage,
  getBatchExecutionArchives,
  getBatchExecutionPreviewHistoryPage,
  getBatchExecutionQueueHistoryPage,
  getBatchRetryHistoryPage,
  getBatchSummary,
  previewBatchExecutionPlan,
  queueBatchExecutionPlan,
  updateBatchExecutionQueueStatus,
} from '@/services/api';
import type {
  BatchExecutionOperationsArchiveCleanupResult,
  BatchExecutionOperationsArchivesPayload,
  BatchExecutionOperationsExportResult,
  BatchExecutionPlanPreviewResult,
  BatchExecutionPlanQueueResult,
  BatchExecutionPreviewHistoryPayload,
  BatchExecutionPreviewHistoryRecord,
  BatchExecutionQueueHistoryPayload,
  BatchExecutionQueueHistoryRecord,
  BatchRecord,
  BatchRetryGenerateResult,
  BatchRetryHistoryPayload,
  BatchRetryHistoryRecord,
  BatchRetryTrendRecord,
  BatchRuntimeActiveJobRecord,
  BatchRuntimeEpisodeRecord,
  BatchRuntimeProviderRecord,
  BatchRuntimeQueueRecord,
  BatchRuntimeQueueTrendRecord,
  BatchRuntimeStepResult,
  BatchesPayload,
} from '@/types/api';
import { displayBoolean, displayFieldLabel, displayPriority, displayStatus, displayText } from '@/utils/display';

const { Text } = Typography;

/** Extracted type aliases for deeply nested generics (T-3) */
type BatchExecutionPlanTemplate = NonNullable<BatchesPayload['multi_batch_summary']>['execution_plan_templates'][number];
type BatchExecutionFailureBreakdown = NonNullable<BatchesPayload['multi_batch_summary']>['execution_failure_breakdown'][number];
type BatchArchiveRecord = NonNullable<BatchExecutionOperationsArchivesPayload['archives']>[number];
type BatchFailureHotspot = NonNullable<BatchesPayload['multi_batch_summary']>['failure_hotspots'][number];
type BatchRetryHotspot = NonNullable<BatchesPayload['multi_batch_summary']>['retry_hotspots'][number];
type BatchAutoDispositionTemplate = NonNullable<BatchesPayload['multi_batch_summary']>['auto_disposition_templates'][number];
type BatchDispatchPriorityPlanItem = NonNullable<BatchesPayload['multi_batch_summary']>['dispatch_priority_plan'][number];
type BatchPriorityAction = NonNullable<BatchesPayload['multi_batch_summary']>['priority_actions'][number];

function statusTag(value: string, color: string) {
  return <Tag color={color}>{displayStatus(value)}</Tag>;
}

function statusColor(value?: string) {
  if (value === 'completed' || value === 'succeeded' || value === 'healthy' || value === 'ready') {
    return 'green';
  }
  if (value === 'failed' || value === 'blocked' || value === 'critical') {
    return 'red';
  }
  if (value === 'running' || value === 'active') {
    return 'blue';
  }
  if (value === 'warning' || value === 'manual_required') {
    return 'orange';
  }
  return 'default';
}

function priorityColor(value?: string) {
  if (value === 'P0') {
    return 'red';
  }
  if (value === 'P1') {
    return 'orange';
  }
  if (value === 'P2') {
    return 'blue';
  }
  return 'default';
}

function bar(color: string, width: number) {
  return (
    <div style={{ height: 8, width: '100%', background: '#f0f0f0', borderRadius: 4 }}>
      <div style={{ height: 8, width: `${width}%`, background: color, borderRadius: 4 }} />
    </div>
  );
}

function formatSummaryValue(value: unknown, key?: string): string {
  if (value === undefined || value === null || value === '') {
    return '-';
  }
  if (typeof value === 'boolean') {
    return displayBoolean(value);
  }
  if (typeof value === 'number') {
    return String(value);
  }
  if (typeof value === 'string') {
    if (key?.includes('status')) {
      return displayStatus(value);
    }
    if (key?.includes('priority')) {
      return displayPriority(value);
    }
    return displayText(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => displayText(String(item))).join(' / ') || '-';
  }
  return JSON.stringify(value);
}

function SummaryCard({
  title,
  source,
  maxItems = 6,
}: {
  title: string;
  source?: Record<string, unknown>;
  maxItems?: number;
}) {
  const entries = Object.entries(source ?? {})
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .slice(0, maxItems);

  return (
    <ProCard title={title} bordered className="aicomic-compact-card">
      {entries.length ? (
        <Descriptions size="small" column={1} colon>
          {entries.map(([key, value]) => (
            <Descriptions.Item key={key} label={displayFieldLabel(key)}>
              <Text ellipsis={{ tooltip: formatSummaryValue(value, key) }}>
                {formatSummaryValue(value, key)}
              </Text>
            </Descriptions.Item>
          ))}
        </Descriptions>
      ) : (
        <Text type="secondary">暂无数据</Text>
      )}
    </ProCard>
  );
}

export default function BatchesPage() {
  const defaultHistoryPageSize = 5;
  const [messageApi, contextHolder] = message.useMessage();
  const [data, setData] = useState<BatchesPayload>();
  const [loading, setLoading] = useState(true);
  const [retryEpisodeCode, setRetryEpisodeCode] = useState('');
  const [retryProvider, setRetryProvider] = useState('');
  const [retryResult, setRetryResult] = useState<BatchRetryGenerateResult>();
  const [executionPreviewResult, setExecutionPreviewResult] = useState<BatchExecutionPlanPreviewResult>();
  const [executionQueueResult, setExecutionQueueResult] = useState<BatchExecutionPlanQueueResult>();
  const [executionArchiveData, setExecutionArchiveData] = useState<BatchExecutionOperationsArchivesPayload>();
  const [executionExportResult, setExecutionExportResult] = useState<BatchExecutionOperationsExportResult>();
  const [executionArchiveCleanupResult, setExecutionArchiveCleanupResult] = useState<BatchExecutionOperationsArchiveCleanupResult>();
  const [archiveRetentionDays, setArchiveRetentionDays] = useState('30');
  const retryHistoryPagination = usePagination(defaultHistoryPageSize);
  const executionPreviewHistoryPagination = usePagination(defaultHistoryPageSize);
  const executionQueueHistoryPagination = usePagination(defaultHistoryPageSize);
  const [retryHistoryData, setRetryHistoryData] = useState<BatchRetryHistoryPayload>();
  const [executionPreviewHistoryData, setExecutionPreviewHistoryData] = useState<BatchExecutionPreviewHistoryPayload>();
  const [executionQueueHistoryData, setExecutionQueueHistoryData] = useState<BatchExecutionQueueHistoryPayload>();

  const multiBatchSummary = data?.multi_batch_summary;
  const runtimeMonitor = data?.runtime_monitor;
  const executionQueueSummary = multiBatchSummary?.execution_queue_summary;
  const executionOperationsReport = multiBatchSummary?.execution_operations_report;
  const retryHistoryCount = retryHistoryData?.total_count ?? runtimeMonitor?.retry_history_count ?? 0;
  const retryTrendCount = runtimeMonitor?.retry_trend_count ?? 0;
  const riskFlagCount = runtimeMonitor?.risk_flag_count ?? 0;
  const executionPreviewHistoryTotal =
    executionPreviewHistoryData?.total_count ?? multiBatchSummary?.execution_preview_history_count ?? 0;
  const executionQueueHistoryTotal =
    executionQueueHistoryData?.total_count ?? multiBatchSummary?.execution_queue_history_count ?? 0;

  const loadData = async () => {
    setLoading(true);
    try {
      const [payload, archivesPayload, retryHistoryPayload, executionPreviewPayload, executionQueuePayload] =
        await Promise.all([
          getBatchSummary(),
          getBatchExecutionArchives(20),
          getBatchRetryHistoryPage(retryHistoryPagination.page, retryHistoryPagination.pageSize),
          getBatchExecutionPreviewHistoryPage(executionPreviewHistoryPagination.page, executionPreviewHistoryPagination.pageSize),
          getBatchExecutionQueueHistoryPage(executionQueueHistoryPagination.page, executionQueueHistoryPagination.pageSize),
        ]);
      setData(payload);
      setExecutionArchiveData(archivesPayload);
      setRetryHistoryData(retryHistoryPayload);
      setExecutionPreviewHistoryData(executionPreviewPayload);
      setExecutionQueueHistoryData(executionQueuePayload);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [
    retryHistoryPagination.page,
    retryHistoryPagination.pageSize,
    executionPreviewHistoryPagination.page,
    executionPreviewHistoryPagination.pageSize,
    executionQueueHistoryPagination.page,
    executionQueueHistoryPagination.pageSize,
  ]);

  const handleRetryBatchGenerate = async (dryRun: boolean) => {
    try {
      const result = await generateBatchRetryPackage({
        statuses: ['failed', 'manual_required'],
        episode_code: retryEpisodeCode,
        provider: retryProvider,
        dry_run: dryRun,
      });
      setRetryResult(result);
      messageApi.success(
        dryRun ? `预览已生成：${result.retried_count} 个可重试任务` : `重试包已生成：${result.retried_count} 个任务`,
      );
      await loadData();
    } catch (error) {
      console.error(error);
      messageApi.error('生成重试包失败');
    }
  };

  const handleExecutionPreview = async (planKey: string, target: string) => {
    try {
      const result = await previewBatchExecutionPlan({
        plan_key: planKey,
        target,
        mode: 'dry_run',
      });
      setExecutionPreviewResult(result);
      messageApi.success(`执行预览已生成：${result.plan_key}`);
      await loadData();
    } catch (error) {
      console.error(error);
      messageApi.error('生成执行预览失败');
    }
  };

  const handleExecutionQueue = async (planKey: string, target: string) => {
    try {
      const result = await queueBatchExecutionPlan({
        plan_key: planKey,
        target,
        mode: 'queued',
      });
      setExecutionQueueResult(result);
      messageApi.success(`执行已入队：${result.queue_run_id}`);
      await loadData();
    } catch (error) {
      console.error(error);
      messageApi.error('执行计划入队失败');
    }
  };

  const handleQueueStatusUpdate = async (
    queueRunId: string,
    queueStatus: string,
    executionStatus: string,
    resultNote: string,
  ) => {
    try {
      const result = await updateBatchExecutionQueueStatus({
        queue_run_id: queueRunId,
        queue_status: queueStatus,
        execution_status: executionStatus,
        result_note: resultNote,
      });
      messageApi.success(`队列已更新为${displayStatus(result.queue_status)}：${result.queue_run_id}`);
      await loadData();
    } catch (error) {
      console.error(error);
      messageApi.error('更新执行队列状态失败');
    }
  };

  const handleExecutionExport = async (exportFormat: string, exportScope: string) => {
    try {
      const result = await exportBatchExecutionOperationsReport({
        export_format: exportFormat,
        export_scope: exportScope,
      });
      setExecutionExportResult(result);
      messageApi.success(`执行运维导出已生成：${result.export_name}`);
      await loadData();
    } catch (error) {
      console.error(error);
      messageApi.error('导出执行运维报告失败');
    }
  };

  const handleArchiveCleanup = async (dryRun: boolean) => {
    try {
      const result = await cleanupBatchExecutionArchives({
        retention_days: Number(archiveRetentionDays || '30'),
        dry_run: dryRun,
      });
      setExecutionArchiveCleanupResult(result);
      messageApi.success(dryRun ? '归档清理预览已生成' : '归档清理已完成');
      await loadData();
    } catch (error) {
      console.error(error);
      messageApi.error('清理执行归档失败');
    }
  };

  const diagnosticsCount =
    (multiBatchSummary?.failure_hotspot_count ?? 0) +
    (multiBatchSummary?.retry_hotspot_count ?? 0) +
    (multiBatchSummary?.dispatch_priority_count ?? 0);
  const hasBatchData =
    (data?.count ?? 0) > 0 ||
    (multiBatchSummary?.batch_count ?? 0) > 0 ||
    (runtimeMonitor?.queue_count ?? 0) > 0 ||
    (runtimeMonitor?.active_job_count ?? 0) > 0 ||
    (retryHistoryData?.total_count ?? 0) > 0 ||
    (executionArchiveData?.archive_count ?? 0) > 0 ||
    (multiBatchSummary?.execution_plan_template_count ?? 0) > 0;

  return (
    <PageContainer
      title="批次监控"
      subTitle="聚焦执行状态、编排与归档"
      className="aicomic-compact-page"
      extra={[
        <Button key="refresh" size="small" icon={<ReloadOutlined />} onClick={() => void loadData()}>刷新</Button>,
      ]}
    >
      {contextHolder}
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : (
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <ProCard title="运行状态" bordered className="aicomic-compact-card">
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <Space wrap>
              <Tag color={statusColor(runtimeMonitor?.status)}>{displayStatus(runtimeMonitor?.status ?? 'unknown')}</Tag>
              <Tag color={statusColor(multiBatchSummary?.latest_status)}>
                最新批次 {multiBatchSummary?.latest_batch_id || '-'}
              </Tag>
              <Tag color={riskFlagCount > 0 ? 'orange' : 'green'}>风险项 {riskFlagCount}</Tag>
              <Tag color={(runtimeMonitor?.active_job_count ?? 0) > 0 ? 'blue' : 'green'}>
                执行中任务 {runtimeMonitor?.active_job_count ?? 0}
              </Tag>
              <Tag>队列 {runtimeMonitor?.queue_count ?? 0}</Tag>
              <Tag>服务商 {runtimeMonitor?.provider_count ?? 0}</Tag>
              <Tag>剧集 {runtimeMonitor?.episode_count ?? 0}</Tag>
              <Tag>重试 {retryHistoryCount}</Tag>
            </Space>
            <Space wrap size={[24, 8]}>
              <Text>批次数 {multiBatchSummary?.batch_count ?? 0}</Text>
              <Text>运行批次 {multiBatchSummary?.running_batch_count ?? 0}</Text>
              <Text>阻塞批次 {multiBatchSummary?.blocked_batch_count ?? 0}</Text>
              <Text>步骤完成率 {multiBatchSummary?.step_completion_rate ?? 0}%</Text>
              <Text>任务总数 {runtimeMonitor?.job_total_count ?? 0}</Text>
              <Text>队列数 {runtimeMonitor?.queue_count ?? 0}</Text>
              <Text>服务商 {runtimeMonitor?.provider_count ?? 0}</Text>
              <Text>剧集 {runtimeMonitor?.episode_count ?? 0}</Text>
              <Text>失败/人工 {(runtimeMonitor?.job_failed_count ?? 0) + (runtimeMonitor?.job_manual_required_count ?? 0)}</Text>
            </Space>
            <Text type="secondary">
              {(runtimeMonitor?.next_actions ?? []).map(displayText).join(' / ') || '当前无额外操作建议。'}
            </Text>
            <Text type="secondary">
              当前运行口径覆盖批次、任务、队列、服务商与剧集分布，便于在单页内判断是否需要切到执行编排、归档历史或热点诊断继续处理。
            </Text>
          </Space>
        </ProCard>

        <Row gutter={[12, 12]}>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="任务总数" value={runtimeMonitor?.job_total_count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="已完成" value={runtimeMonitor?.job_completed_count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="执行中" value={runtimeMonitor?.job_active_count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard
              title="失败/人工"
              value={(runtimeMonitor?.job_failed_count ?? 0) + (runtimeMonitor?.job_manual_required_count ?? 0)}
            />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="批次数" value={multiBatchSummary?.batch_count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="运行批次" value={multiBatchSummary?.running_batch_count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="阻塞批次" value={multiBatchSummary?.blocked_batch_count ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={3}>
            <MetricCard title="步骤完成率" value={multiBatchSummary?.step_completion_rate ?? 0} suffix="%" />
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24}>
            <ProCard title="重试与运维操作" bordered className="aicomic-compact-card">
              <Row gutter={[16, 12]}>
                <Col xs={24} xl={14}>
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Text strong>重试批次</Text>
                    <Space wrap>
                      <Input
                        style={{ width: 180 }}
                        placeholder="剧集筛选，例如 E01"
                        value={retryEpisodeCode}
                        onChange={(event) => setRetryEpisodeCode(event.target.value)}
                      />
                      <Input
                        style={{ width: 180 }}
                        placeholder="服务商筛选，例如 manual_web"
                        value={retryProvider}
                        onChange={(event) => setRetryProvider(event.target.value)}
                      />
                      <Button onClick={() => void handleRetryBatchGenerate(true)}>预览重试</Button>
                      <Popconfirm
                        title="生成重试包？"
                        description="会写入重试报告和已重试任务清单。"
                        onConfirm={() => void handleRetryBatchGenerate(false)}
                      >
                        <Button type="primary">生成重试包</Button>
                      </Popconfirm>
                    </Space>

                    {retryResult ? (
                      <>
                        <Alert
                          type={retryResult.dry_run ? 'info' : 'success'}
                          showIcon
                          message={`状态：${displayStatus(retryResult.status)} · 已重试 ${retryResult.retried_count} · 范围内 ${retryResult.scoped_job_count}`}
                          description={`报告路径：${retryResult.report_output_path} / 任务路径：${retryResult.jobs_output_path}`}
                        />
                        <ProTable<BatchRuntimeActiveJobRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="job_id"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={retryResult.retry_candidates ?? []}
                          columns={[
                            { title: '任务编号', dataIndex: 'job_id', ellipsis: true },
                            { title: '剧集', dataIndex: 'episode_code', width: 90 },
                            { title: '类型', dataIndex: 'job_type', width: 90 },
                            { title: '服务商', dataIndex: 'provider', width: 120 },
                            {
                              title: '状态',
                              dataIndex: 'status',
                              width: 120,
                              render: (_, record) => statusTag(record.status, record.status === 'failed' ? 'red' : 'orange'),
                            },
                          ]}
                        />
                      </>
                    ) : (
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <Text type="secondary">按剧集或服务商筛选后，可直接在当前页生成重试预览或正式重试包。</Text>
                        <Alert
                          type={runtimeMonitor?.retry_summary.exists ? 'info' : 'success'}
                          showIcon
                          message={`当前重试包：${runtimeMonitor?.retry_summary.retried_count ?? 0}/${runtimeMonitor?.retry_summary.scoped_job_count ?? 0}`}
                          description={`报告路径：${runtimeMonitor?.retry_summary.report_path || '-'}`}
                        />
                      </Space>
                    )}
                  </Space>
                </Col>

                <Col xs={24} xl={10}>
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Text strong>运维导出与清理</Text>
                    <Space wrap>
                      <Button onClick={() => void handleExecutionExport('json', 'operations_report')}>导出 JSON</Button>
                      <Button onClick={() => void handleExecutionExport('csv', 'operations_report')}>导出 CSV</Button>
                      <Button onClick={() => void handleExecutionExport('json', 'report_archive')}>归档报告</Button>
                    </Space>
                    <Space wrap>
                      <Input
                        style={{ width: 140 }}
                        value={archiveRetentionDays}
                        onChange={(event) => setArchiveRetentionDays(event.target.value)}
                        placeholder="保留天数"
                      />
                      <Button onClick={() => void handleArchiveCleanup(true)}>清理预演</Button>
                      <Popconfirm
                        title="清理归档报告？"
                        description="可能会移除旧的执行运维归档报告。"
                        onConfirm={() => void handleArchiveCleanup(false)}
                      >
                        <Button danger>执行清理</Button>
                      </Popconfirm>
                    </Space>
                    {executionExportResult ? (
                      <Alert
                        showIcon
                        type="success"
                        message={`${displayFieldLabel(executionExportResult.export_scope)}：${executionExportResult.export_name}`}
                        description={`路径：${executionExportResult.export_path} / 数量：${executionExportResult.export_count}`}
                      />
                    ) : (
                      <Text type="secondary">支持直接导出执行运维报告，并在当前页完成归档清理预演与执行。</Text>
                    )}
                    {executionArchiveCleanupResult ? (
                      <Alert
                        showIcon
                        type={executionArchiveCleanupResult.dry_run ? 'info' : 'warning'}
                        message={`归档清理：可清理 ${executionArchiveCleanupResult.eligible_count}，已删除 ${executionArchiveCleanupResult.deleted_count}`}
                        description={`根目录：${executionArchiveCleanupResult.archive_root}`}
                      />
                    ) : null}
                  </Space>
                </Col>
              </Row>
              <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                该区聚合了重试预览、正式重试、执行运维导出和归档清理，适合在一次批次复盘中直接完成补救动作，不需要来回切页。
              </Text>
            </ProCard>
          </Col>
        </Row>

        {hasBatchData ? (
          <>
            <Row gutter={[12, 12]}>
              <Col xs={24} xl={16}>
                <ProCard title={`批次摘要（${data?.count ?? 0}）`} bordered className="aicomic-compact-card">
                  <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                    当前批次视图直接汇总范围、状态、步骤完成率和摘要路径，用于快速判断本轮批处理是否已经达到可复盘或可重新入队的状态。
                  </Text>
                  <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                    当批次数量较少时，保留同页摘要比分页切换更高效；当批次数量增大时，页面会自动恢复分页，避免历史数据拉长首屏。
                  </Text>
                  <ProTable<BatchRecord>
                    size="small"
                    scroll={{ x: 'max-content' }}
                    rowKey="batch_id"
                    search={false}
                    options={false}
                    pagination={(data?.count ?? 0) > 6 ? { pageSize: 6, showSizeChanger: false } : false}
                    dataSource={data?.items ?? []}
                    columns={[
                      { title: '批次编号', dataIndex: 'batch_id', copyable: true, width: 220, ellipsis: true },
                      { title: '范围类型', dataIndex: 'scope_type', width: 120 },
                      { title: '范围值', dataIndex: 'scope_value', width: 120 },
                      {
                        title: '状态',
                        dataIndex: 'status',
                        width: 110,
                        render: (_, record) => statusTag(record.status, statusColor(record.status)),
                      },
                      {
                        title: '步骤进度',
                        width: 180,
                        render: (_, record) => {
                          const percent =
                            record.step_count > 0 ? Math.round((record.completed_step_count / record.step_count) * 100) : 0;
                          return <Progress percent={percent} size="small" />;
                        },
                      },
                      {
                        title: '摘要路径',
                        dataIndex: 'summary_path',
                        ellipsis: true,
                      },
                    ]}
                  />
                </ProCard>
              </Col>
              <Col xs={24} xl={8}>
                <ProCard title="多批次概览与风险" bordered className="aicomic-compact-card">
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag color="blue">最新 {multiBatchSummary?.latest_batch_id || '-'}</Tag>
                      <Tag color={statusColor(multiBatchSummary?.latest_status)}>
                        {displayStatus(multiBatchSummary?.latest_status || 'unknown')}
                      </Tag>
                      <Tag color={riskFlagCount > 0 ? 'orange' : 'green'}>风险项 {riskFlagCount}</Tag>
                    </Space>
                    <Descriptions size="small" column={1} colon>
                      <Descriptions.Item label="摘要路径">
                        <Text ellipsis={{ tooltip: multiBatchSummary?.latest_summary_path || '-' }}>
                          {multiBatchSummary?.latest_summary_path || '-'}
                        </Text>
                      </Descriptions.Item>
                      <Descriptions.Item label="建议动作">
                        <Text ellipsis={{ tooltip: (runtimeMonitor?.next_actions ?? []).map(displayText).join(' / ') || '暂无建议' }}>
                          {(runtimeMonitor?.next_actions ?? []).map(displayText).join(' / ') || '暂无建议'}
                        </Text>
                      </Descriptions.Item>
                    </Descriptions>
                    <Space wrap>
                      {Object.entries(multiBatchSummary?.status_counts ?? {}).map(([key, value]) => (
                        <Tag key={key} color="blue">
                          {displayStatus(key)}：{String(value)}
                        </Tag>
                      ))}
                      {Object.entries(multiBatchSummary?.scope_type_counts ?? {}).map(([key, value]) => (
                        <Tag key={key}>{displayFieldLabel(key)}：{String(value)}</Tag>
                      ))}
                    </Space>
                    <Space wrap style={{ width: '100%' }}>
                      {(runtimeMonitor?.risk_flags ?? []).length ? (
                        (runtimeMonitor?.risk_flags ?? []).map((item) => (
                          <Tag key={`${item.level}_${item.name}`} color={statusColor(item.level)}>
                            {displayText(item.name)}：{displayText(item.detail)}
                          </Tag>
                        ))
                      ) : (
                        <Tag color="green">暂无运行风险</Tag>
                      )}
                    </Space>
                  </Space>
                </ProCard>
              </Col>
            </Row>

            <Tabs
              size="small"
              items={[
            {
              key: 'runtime',
              label: `运行监控`,
              children: (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={8}>
                      <ProCard title={`队列监控（${runtimeMonitor?.queue_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchRuntimeQueueRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="queue_name"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={runtimeMonitor?.queues ?? []}
                          columns={[
                            { title: '队列', dataIndex: 'queue_name' },
                            { title: '总数', dataIndex: 'total_count', width: 70 },
                            { title: '执行中', dataIndex: 'active_count', width: 70 },
                            { title: '失败', dataIndex: 'failed_count', width: 70 },
                            { title: '人工', dataIndex: 'manual_required_count', width: 70 },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={8}>
                      <ProCard title={`队列趋势（${runtimeMonitor?.queue_trend_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchRuntimeQueueTrendRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="queue_name"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={runtimeMonitor?.queue_trends ?? []}
                          columns={[
                            { title: '队列', dataIndex: 'queue_name', width: 110 },
                            {
                              title: '负载',
                              dataIndex: 'total_count',
                              render: (_, record) => (
                                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                  <span>{record.total_count} / 已重试 {record.retried_count ?? 0}</span>
                                  {bar('#1677ff', record.load_bar_width)}
                                </Space>
                              ),
                            },
                            {
                              title: '积压',
                              dataIndex: 'backlog_count',
                              render: (_, record) => (
                                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                  <span>{record.backlog_count}</span>
                                  {bar('#cf1322', record.backlog_bar_width)}
                                </Space>
                              ),
                            },
                            {
                              title: '状态',
                              dataIndex: 'queue_status',
                              width: 100,
                              render: (_, record) => statusTag(record.queue_status, statusColor(record.queue_status)),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={8}>
                      <ProCard title={`服务商负载（${runtimeMonitor?.provider_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchRuntimeProviderRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="provider"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={runtimeMonitor?.providers ?? []}
                          columns={[
                            { title: '服务商', dataIndex: 'provider' },
                            { title: '队列', dataIndex: 'queue_name', width: 100 },
                            { title: '总数', dataIndex: 'total_count', width: 70 },
                            { title: '执行中', dataIndex: 'active_count', width: 70 },
                            { title: '失败', dataIndex: 'failed_count', width: 70 },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>

                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={12}>
                      <ProCard title={`剧集进度（${runtimeMonitor?.episode_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                          当前剧集进度聚焦每集任务总数、完成数与执行中数量，帮助定位积压集中在哪一集，是否需要回到剧集页或批次重试入口继续处理。
                        </Text>
                        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                          若某一集长时间停留在执行中而完成率不升，通常意味着该集素材回填、Provider 结果回收或后续步骤切换存在等待点。
                        </Text>
                        <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
                          当同一集同时存在较多执行中任务和较低完成率时，优先检查该集是否卡在少数镜头或少数 Provider，而不是直接对整季做大范围重试。
                        </Text>
                        <ProTable<BatchRuntimeEpisodeRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="episode_code"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={runtimeMonitor?.episodes ?? []}
                          columns={[
                            { title: '剧集', dataIndex: 'episode_code', width: 90 },
                            { title: '总数', dataIndex: 'total_count', width: 70 },
                            { title: '完成', dataIndex: 'completed_count', width: 70 },
                            { title: '执行中', dataIndex: 'active_count', width: 70 },
                            { title: '完成率', dataIndex: 'completion_rate', width: 90, render: (_, record) => `${record.completion_rate}%` },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={12}>
                      <ProCard title={`执行中任务（${runtimeMonitor?.active_job_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchRuntimeActiveJobRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="job_id"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={runtimeMonitor?.active_jobs ?? []}
                          columns={[
                            { title: '任务编号', dataIndex: 'job_id', ellipsis: true },
                            { title: '剧集', dataIndex: 'episode_code', width: 90 },
                            { title: '类型', dataIndex: 'job_type', width: 90 },
                            { title: '服务商', dataIndex: 'provider', width: 120 },
                            { title: '队列', dataIndex: 'queue_name', width: 100 },
                            {
                              title: '状态',
                              dataIndex: 'status',
                              width: 110,
                              render: (_, record) => statusTag(record.status, statusColor(record.status)),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>

                  <Row gutter={[12, 12]}>
                    {retryHistoryCount > 0 ? (
                      <Col xs={24} xl={12}>
                        <ProCard
                          title={`重试历史（${retryHistoryCount}）`}
                          bordered
                          className="aicomic-compact-card"
                        >
                          <Alert
                            style={{ marginBottom: 12 }}
                            type={runtimeMonitor?.retry_summary.exists ? 'info' : 'warning'}
                            showIcon
                            message={`当前重试包：${runtimeMonitor?.retry_summary.retried_count ?? 0}/${runtimeMonitor?.retry_summary.scoped_job_count ?? 0}`}
                            description={`报告路径：${runtimeMonitor?.retry_summary.report_path || '-'}`}
                          />
                          <ProTable<BatchRetryHistoryRecord>
                            size="small"
                            scroll={{ x: 'max-content' }}
                            rowKey="audit_id"
                            search={false}
                            options={false}
                            pagination={
                              retryHistoryCount > (retryHistoryData?.page_size ?? retryHistoryPagination.pageSize)
                                ? {
                                    current: retryHistoryData?.page ?? retryHistoryPagination.page,
                                    pageSize: retryHistoryData?.page_size ?? retryHistoryPagination.pageSize,
                                    total: retryHistoryCount,
                                    showSizeChanger: true,
                                    onChange: retryHistoryPagination.onChange,
                                  }
                                : false
                            }
                            dataSource={retryHistoryData?.items ?? runtimeMonitor?.retry_history ?? []}
                            columns={[
                              { title: '时间', dataIndex: 'created_at', width: 180 },
                              { title: '用户', dataIndex: 'user_id', width: 140, ellipsis: true },
                              {
                                title: '预演',
                                dataIndex: 'dry_run',
                                width: 90,
                                render: (_, record) => <Tag color={record.dry_run ? 'blue' : 'green'}>{displayBoolean(record.dry_run)}</Tag>,
                              },
                              { title: '已重试', dataIndex: 'retried_count', width: 80 },
                              { title: '剧集', dataIndex: 'episode_code', width: 90 },
                              { title: '服务商', dataIndex: 'provider', width: 120, ellipsis: true },
                              { title: '状态', dataIndex: 'statuses', render: (_, record) => (record.statuses ?? []).map(displayStatus).join('，') || '-' },
                            ]}
                          />
                        </ProCard>
                      </Col>
                    ) : null}
                    <Col xs={24} xl={retryHistoryCount > 0 ? 12 : 24}>
                      <ProCard title={`步骤结果（${runtimeMonitor?.step_result_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchRuntimeStepResult>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="step_name"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={runtimeMonitor?.step_results ?? []}
                          columns={[
                            { title: '步骤', dataIndex: 'step_name', width: 180 },
                            { title: '状态', dataIndex: 'status', width: 100, render: (_, record) => <Tag color="purple">{displayStatus(record.status)}</Tag> },
                            { title: '输出', dataIndex: 'output_path', ellipsis: true },
                            { title: '消息', dataIndex: 'message', ellipsis: true },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>

                  {retryTrendCount > 0 ? (
                    <ProCard title={`重试趋势（${retryTrendCount}）`} bordered className="aicomic-compact-card">
                      <ProTable<BatchRetryTrendRecord>
                        size="small"
                        scroll={{ x: 'max-content' }}
                        rowKey="period"
                        search={false}
                        options={false}
                        pagination={false}
                        dataSource={runtimeMonitor?.retry_trends ?? []}
                        columns={[
                          { title: '周期', dataIndex: 'period', width: 120 },
                          { title: '动作数', dataIndex: 'action_count', width: 80 },
                          {
                            title: '重试数',
                            dataIndex: 'retry_count',
                            render: (_, record) => (
                              <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                <span>{record.retry_count}</span>
                                {bar('#722ed1', record.retry_bar_width)}
                              </Space>
                            ),
                          },
                          { title: '预演', dataIndex: 'dry_run_count', width: 90 },
                          { title: '已生成', dataIndex: 'generated_count', width: 90 },
                          { title: '成功', dataIndex: 'success_count', width: 80 },
                          { title: '操作人数', dataIndex: 'unique_operator_count', width: 90 },
                          {
                            title: '影响范围',
                            dataIndex: 'queue_impact_count',
                            render: (_, record) => (
                              <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                <span>{`队列 ${record.queue_impact_count} / 剧集 ${record.episode_impact_count}`}</span>
                                {bar('#fa8c16', record.impact_bar_width)}
                              </Space>
                            ),
                          },
                        ]}
                      />
                    </ProCard>
                  ) : null}
                </Space>
              ),
            },
            {
              key: 'execution',
              label: '执行编排',
              children: (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={16}>
                      <ProCard title={`执行计划模板（${multiBatchSummary?.execution_plan_template_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchExecutionPlanTemplate>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="plan_key"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={multiBatchSummary?.execution_plan_templates ?? []}
                          columns={[
                            {
                              title: '优先级',
                              dataIndex: 'priority',
                              width: 90,
                              render: (_, record) => <Tag color={priorityColor(record.priority)}>{displayPriority(record.priority)}</Tag>,
                            },
                            { title: '标题', dataIndex: 'title', width: 220 },
                            { title: '来源', dataIndex: 'source_type', width: 170 },
                            { title: '目标', dataIndex: 'target', width: 170, ellipsis: true },
                            { title: '模式', dataIndex: 'mode', width: 90, render: (_, record) => displayStatus(record.mode) },
                            { title: '步骤', dataIndex: 'estimated_step_count', width: 80 },
                            {
                              title: '审批',
                              dataIndex: 'requires_manual_approval',
                              width: 100,
                              render: (_, record) =>
                                record.requires_manual_approval ? <Tag color="orange">需人工确认</Tag> : <Tag color="green">自动</Tag>,
                            },
                            { title: '命令', dataIndex: 'execution_command', ellipsis: true },
                            {
                              title: '操作',
                              width: 170,
                              render: (_, record) => (
                                <Space>
                                  <Button size="small" onClick={() => void handleExecutionPreview(record.plan_key, record.target)}>
                                    预览
                                  </Button>
                                  <Button size="small" type="primary" onClick={() => void handleExecutionQueue(record.plan_key, record.target)}>
                                    入队
                                  </Button>
                                </Space>
                              ),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={8}>
                      <SummaryCard
                        title={multiBatchSummary?.dispatch_strategy?.strategy_name ?? '调度策略'}
                        source={{
                          strategy_key: multiBatchSummary?.dispatch_strategy?.strategy_key,
                          description: multiBatchSummary?.dispatch_strategy?.description,
                          weights: multiBatchSummary?.dispatch_strategy?.weights,
                          thresholds: multiBatchSummary?.dispatch_strategy?.thresholds,
                          score_formula: multiBatchSummary?.dispatch_strategy?.score_formula,
                        }}
                        maxItems={5}
                      />
                    </Col>
                  </Row>

                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={8}>
                      <SummaryCard
                        title="执行队列摘要"
                        source={{
                          queued_count: executionQueueSummary?.queued_count,
                          running_count: executionQueueSummary?.running_count,
                          completed_count: executionQueueSummary?.completed_count,
                          failed_count: executionQueueSummary?.failed_count,
                          approval_required_count: executionQueueSummary?.approval_required_count,
                          completion_rate: executionQueueSummary?.completion_rate,
                        }}
                      />
                    </Col>
                    <Col xs={24} xl={8}>
                      <SummaryCard
                        title="执行运维报告"
                        source={{
                          health_status: executionOperationsReport?.health_status,
                          top_failure_reason: executionOperationsReport?.top_failure_reason,
                          latest_queue_run_id: executionOperationsReport?.latest_queue_run_id,
                          latest_queue_status: executionOperationsReport?.latest_queue_status,
                          latest_execution_status: executionOperationsReport?.latest_execution_status,
                        }}
                      />
                    </Col>
                    <Col xs={24} xl={8}>
                      <ProCard title="执行队列结果" bordered className="aicomic-compact-card">
                        {executionQueueResult ? (
                          <Alert
                            showIcon
                            type="success"
                            message={`${displayStatus(executionQueueResult.status)}：${executionQueueResult.plan_key}`}
                            description={`${executionQueueResult.queue_summary} / 队列编号：${executionQueueResult.queue_run_id}`}
                          />
                        ) : (
                          <Alert showIcon type="info" message="还没有执行入队记录。" />
                        )}
                      </ProCard>
                    </Col>
                  </Row>

                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={12}>
                      <ProCard title="执行预览结果" bordered className="aicomic-compact-card">
                        {executionPreviewResult ? (
                          <Space direction="vertical" size={10} style={{ width: '100%' }}>
                            <Alert
                              showIcon
                              type="info"
                              message={`${displayStatus(executionPreviewResult.status)}：${executionPreviewResult.plan_key}`}
                              description={`${executionPreviewResult.execution_command} / 预览编号：${executionPreviewResult.preview_run_id}`}
                            />
                            <ProTable<NonNullable<BatchExecutionPlanPreviewResult['steps']>[number]>
                              size="small"
                              scroll={{ x: 'max-content' }}
                              rowKey="step_key"
                              search={false}
                              options={false}
                              pagination={false}
                              dataSource={executionPreviewResult.steps ?? []}
                              columns={[
                                { title: '顺序', dataIndex: 'order', width: 70 },
                                { title: '步骤', dataIndex: 'title', width: 180 },
                                { title: '动作', dataIndex: 'action' },
                              ]}
                            />
                          </Space>
                        ) : (
                          <Alert showIcon type="info" message="还没有执行预览。" />
                        )}
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={12}>
                      <ProCard
                        title={`执行预览历史（${executionPreviewHistoryData?.total_count ?? multiBatchSummary?.execution_preview_history_count ?? 0}）`}
                        bordered
                        className="aicomic-compact-card"
                      >
                        <ProTable<BatchExecutionPreviewHistoryRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="preview_run_id"
                          search={false}
                          options={false}
                          pagination={
                            executionPreviewHistoryTotal >
                            (executionPreviewHistoryData?.page_size ?? executionPreviewHistoryPagination.pageSize)
                              ? {
                                  current: executionPreviewHistoryData?.page ?? executionPreviewHistoryPagination.page,
                                  pageSize: executionPreviewHistoryData?.page_size ?? executionPreviewHistoryPagination.pageSize,
                                  total: executionPreviewHistoryTotal,
                                  showSizeChanger: true,
                                  onChange: executionPreviewHistoryPagination.onChange,
                                }
                              : false
                          }
                          dataSource={executionPreviewHistoryData?.items ?? multiBatchSummary?.execution_preview_history ?? []}
                          columns={[
                            {
                              title: '优先级',
                              dataIndex: 'priority',
                              width: 90,
                              render: (_, record) => <Tag color={priorityColor(record.priority)}>{displayPriority(record.priority)}</Tag>,
                            },
                            { title: '计划键', dataIndex: 'plan_key', width: 160, ellipsis: true },
                            { title: '目标', dataIndex: 'target', width: 160, ellipsis: true },
                            { title: '状态', dataIndex: 'status', width: 110, render: (_, record) => displayStatus(record.status) },
                            { title: '摘要', dataIndex: 'preview_summary', ellipsis: true },
                            { title: '创建时间', dataIndex: 'created_at', width: 180, ellipsis: true },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>

                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={12}>
                      <ProCard
                        title={`执行失败拆解（${multiBatchSummary?.execution_failure_breakdown_count ?? 0}）`}
                        bordered
                        className="aicomic-compact-card"
                      >
                        <ProTable<BatchExecutionFailureBreakdown>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey={(record) => `${record.dimension}_${record.name}`}
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={multiBatchSummary?.execution_failure_breakdown ?? []}
                          columns={[
                            { title: '原因', dataIndex: 'name', width: 220, ellipsis: true },
                            { title: '失败', dataIndex: 'failed_count', width: 80 },
                            { title: '占比', dataIndex: 'share_rate', width: 90, render: (_, record) => `${record.share_rate}%` },
                            { title: '优先级数', dataIndex: 'priority_count', width: 110 },
                            { title: '目标数', dataIndex: 'target_count', width: 100 },
                            { title: '最近运行', dataIndex: 'latest_queue_run_id', ellipsis: true },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={12}>
                      <ProCard
                        title={`执行队列历史（${executionQueueHistoryData?.total_count ?? multiBatchSummary?.execution_queue_history_count ?? 0}）`}
                        bordered
                        className="aicomic-compact-card"
                      >
                        <ProTable<BatchExecutionQueueHistoryRecord>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="queue_run_id"
                          search={false}
                          options={false}
                          pagination={
                            executionQueueHistoryTotal >
                            (executionQueueHistoryData?.page_size ?? executionQueueHistoryPagination.pageSize)
                              ? {
                                  current: executionQueueHistoryData?.page ?? executionQueueHistoryPagination.page,
                                  pageSize: executionQueueHistoryData?.page_size ?? executionQueueHistoryPagination.pageSize,
                                  total: executionQueueHistoryTotal,
                                  showSizeChanger: true,
                                  onChange: executionQueueHistoryPagination.onChange,
                                }
                              : false
                          }
                          dataSource={executionQueueHistoryData?.items ?? multiBatchSummary?.execution_queue_history ?? []}
                          columns={[
                            {
                              title: '优先级',
                              dataIndex: 'priority',
                              width: 90,
                              render: (_, record) => <Tag color={priorityColor(record.priority)}>{displayPriority(record.priority)}</Tag>,
                            },
                            { title: '计划键', dataIndex: 'plan_key', width: 160, ellipsis: true },
                            { title: '队列', dataIndex: 'queue_status', width: 90, render: (_, record) => displayStatus(record.queue_status) },
                            { title: '执行', dataIndex: 'execution_status', width: 140, render: (_, record) => displayStatus(record.execution_status) },
                            { title: '摘要', dataIndex: 'queue_summary', ellipsis: true },
                            {
                              title: '操作',
                              width: 210,
                              render: (_, record) => (
                                <Space>
                                  <Button
                                    size="small"
                                    onClick={() => void handleQueueStatusUpdate(record.queue_run_id, 'running', 'running', '从页面标记为开始')}
                                  >
                                    开始
                                  </Button>
                                  <Button
                                    size="small"
                                    type="primary"
                                    onClick={() => void handleQueueStatusUpdate(record.queue_run_id, 'completed', 'completed', '从页面标记为完成')}
                                  >
                                    完成
                                  </Button>
                                  <Button
                                    size="small"
                                    danger
                                    onClick={() => void handleQueueStatusUpdate(record.queue_run_id, 'failed', 'failed', '从页面标记为失败')}
                                  >
                                    失败
                                  </Button>
                                </Space>
                              ),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>
                </Space>
              ),
            },
            {
              key: 'archives',
              label: '归档历史',
              children: (
                <ProCard
                  title={`执行归档（${executionArchiveData?.archive_count ?? 0}/${executionArchiveData?.total_count ?? 0}）`}
                  extra={`根目录：${executionArchiveData?.archive_root || '-'}`}
                  bordered
                  className="aicomic-compact-card"
                >
                  <ProTable<BatchArchiveRecord>
                    size="small"
                    scroll={{ x: 'max-content' }}
                    rowKey="archive_id"
                    search={false}
                    options={false}
                    pagination={(executionArchiveData?.archives?.length ?? 0) > 8 ? { pageSize: 8, showSizeChanger: false } : false}
                    dataSource={executionArchiveData?.archives ?? []}
                    columns={[
                      { title: '归档时间', dataIndex: 'archived_at', width: 200 },
                      { title: '健康状态', dataIndex: 'health_status', width: 100, render: (_, record) => displayStatus(record.health_status) },
                      { title: '首要失败原因', dataIndex: 'top_failure_reason', width: 180, ellipsis: true },
                      { title: '指标数', dataIndex: 'metric_count', width: 90 },
                      { title: '文件数', dataIndex: 'file_count', width: 70 },
                      { title: '归档目录', dataIndex: 'archive_dir', ellipsis: true },
                    ]}
                  />
                </ProCard>
              ),
            },
            {
              key: 'diagnostics',
              label: `热点诊断`,
              children: (
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={12}>
                      <ProCard
                        title={`故障热点（${multiBatchSummary?.failure_hotspot_count ?? 0}）`}
                        extra={<Tag color={diagnosticsCount > 0 ? 'orange' : 'green'}>诊断项 {diagnosticsCount}</Tag>}
                        bordered
                        className="aicomic-compact-card"
                      >
                        <ProTable<BatchFailureHotspot>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="batch_id"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={multiBatchSummary?.failure_hotspots ?? []}
                          columns={[
                            { title: '批次编号', dataIndex: 'batch_id', width: 180, ellipsis: true },
                            { title: '范围', render: (_, record) => `${displayFieldLabel(record.scope_type)}：${record.scope_value}`, width: 140 },
                            {
                              title: '级别',
                              dataIndex: 'hotspot_level',
                              width: 100,
                              render: (_, record) => <Tag color={statusColor(record.hotspot_level)}>{displayStatus(record.hotspot_level)}</Tag>,
                            },
                            { title: '失败', dataIndex: 'failed_step_count', width: 80 },
                            { title: '阻塞', dataIndex: 'blocked_step_count', width: 80 },
                            { title: '待处理', dataIndex: 'pending_step_count', width: 80 },
                            {
                              title: '热点分',
                              dataIndex: 'hotspot_score',
                              render: (_, record) => (
                                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                  <span>{record.hotspot_score}</span>
                                  {bar('#cf1322', record.hotspot_bar_width)}
                                </Space>
                              ),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={12}>
                      <ProCard title={`重试热点（${multiBatchSummary?.retry_hotspot_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchRetryHotspot>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey={(record) => `${record.dimension}:${record.name}`}
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={multiBatchSummary?.retry_hotspots ?? []}
                          columns={[
                            { title: '维度', dataIndex: 'dimension', width: 100, render: (_, record) => displayFieldLabel(record.dimension) },
                            { title: '名称', dataIndex: 'name', width: 160, ellipsis: true },
                            {
                              title: '级别',
                              dataIndex: 'hotspot_level',
                              width: 100,
                              render: (_, record) => <Tag color={statusColor(record.hotspot_level)}>{displayStatus(record.hotspot_level)}</Tag>,
                            },
                            { title: '重试', dataIndex: 'retry_count', width: 70 },
                            { title: '当前', dataIndex: 'current_retry_count', width: 70 },
                            { title: '历史', dataIndex: 'history_action_count', width: 70 },
                            {
                              title: '分数',
                              dataIndex: 'hotspot_score',
                              render: (_, record) => (
                                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                  <span>{record.hotspot_score}</span>
                                  {bar('#722ed1', record.hotspot_bar_width)}
                                </Space>
                              ),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>

                  <Row gutter={[12, 12]}>
                    <Col xs={24} xl={12}>
                      <ProCard title={`自动处置模板（${multiBatchSummary?.auto_disposition_template_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchAutoDispositionTemplate>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="template_key"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={multiBatchSummary?.auto_disposition_templates ?? []}
                          columns={[
                            {
                              title: '优先级',
                              dataIndex: 'priority',
                              width: 90,
                              render: (_, record) => <Tag color={priorityColor(record.priority)}>{displayPriority(record.priority)}</Tag>,
                            },
                            { title: '模板', dataIndex: 'title', width: 180 },
                            { title: '触发条件', dataIndex: 'trigger_type', width: 120 },
                            { title: '目标', dataIndex: 'target', width: 170, ellipsis: true },
                            { title: '建议命令', dataIndex: 'suggested_command', width: 150 },
                            { title: '检查清单', render: (_, record) => (record.checklist ?? []).map(displayText).join(' / ') || '-' },
                          ]}
                        />
                      </ProCard>
                    </Col>
                    <Col xs={24} xl={12}>
                      <ProCard title={`调度优先级计划（${multiBatchSummary?.dispatch_priority_count ?? 0}）`} bordered className="aicomic-compact-card">
                        <ProTable<BatchDispatchPriorityPlanItem>
                          size="small"
                          scroll={{ x: 'max-content' }}
                          rowKey="target"
                          search={false}
                          options={false}
                          pagination={false}
                          dataSource={multiBatchSummary?.dispatch_priority_plan ?? []}
                          columns={[
                            {
                              title: '优先级',
                              dataIndex: 'recommended_priority',
                              width: 90,
                              render: (_, record) => (
                                <Tag color={priorityColor(record.recommended_priority)}>{displayPriority(record.recommended_priority)}</Tag>
                              ),
                            },
                            { title: '维度', dataIndex: 'dimension', width: 100, render: (_, record) => displayFieldLabel(record.dimension) },
                            { title: '目标', dataIndex: 'target', width: 170, ellipsis: true },
                            { title: '积压', dataIndex: 'backlog_count', width: 80 },
                            { title: '失败', dataIndex: 'failed_count', width: 70 },
                            { title: '人工处理', dataIndex: 'manual_required_count', width: 80 },
                            {
                              title: '分数',
                              dataIndex: 'dispatch_score',
                              render: (_, record) => (
                                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                                  <span>{record.dispatch_score}</span>
                                  {bar('#1677ff', record.dispatch_bar_width)}
                                </Space>
                              ),
                            },
                          ]}
                        />
                      </ProCard>
                    </Col>
                  </Row>

                  <ProCard title={`优先处理动作（${multiBatchSummary?.priority_action_count ?? 0}）`} bordered className="aicomic-compact-card">
                    <ProTable<BatchPriorityAction>
                      size="small"
                      scroll={{ x: 'max-content' }}
                      rowKey={(record) => `${record.priority}_${record.action_type}_${record.target}`}
                      search={false}
                      options={false}
                      pagination={false}
                      dataSource={multiBatchSummary?.priority_actions ?? []}
                      columns={[
                        {
                          title: '优先级',
                          dataIndex: 'priority',
                          width: 90,
                          render: (_, record) => <Tag color={priorityColor(record.priority)}>{displayPriority(record.priority)}</Tag>,
                        },
                        { title: '动作', dataIndex: 'action_type', width: 170 },
                        { title: '目标', dataIndex: 'target', width: 170, ellipsis: true },
                        { title: '原因', dataIndex: 'reason', ellipsis: true, render: (_, record) => displayText(record.reason) },
                        { title: '建议命令', dataIndex: 'suggested_command', width: 140 },
                      ]}
                    />
                  </ProCard>
                </Space>
              ),
            },
              ]}
            />
          </>
        ) : (
          <ProCard title="当前暂无批次运行数据" bordered className="aicomic-compact-card">
            <Alert
              type="info"
              showIcon
              message="暂无批次数据"
              description="生成任务包、创建批次或产生执行历史后，这里会自动展开批次摘要、运行监控、执行编排与归档历史。"
            />
          </ProCard>
        )}
      </Space>
      )}
    </PageContainer>
  );
}
