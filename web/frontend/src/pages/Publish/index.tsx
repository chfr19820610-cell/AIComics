import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Badge, Space, Statistic, Row, Col, message } from 'antd';
import { getPublishStatus, getAnalyticsSummary } from '@/services/api';
import type { PublishStatus, AnalyticsSummary } from '@/services/api';

export default function PublishPage() {
  const [status, setStatus] = useState<PublishStatus | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [s, a] = await Promise.all([
        getPublishStatus(),
        getAnalyticsSummary(),
      ]);
      setStatus(s);
      setAnalytics(a);
    } catch (e) {
      message.error('加载发布数据失败');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  const platformColumns = [
    { title: '平台', dataIndex: 'platform', key: 'platform' },
    {
      title: '状态', key: 'enabled',
      render: (_: unknown, r: { enabled: boolean }) =>
        r.enabled ? <Badge status="success" text="已启用" /> : <Badge status="default" text="未启用" />,
    },
    {
      title: '就绪', key: 'ready',
      render: (_: unknown, r: { ready: boolean }) =>
        r.ready ? <Tag color="green">就绪</Tag> : <Tag color="red">未就绪</Tag>,
    },
  ];

  const platformData = status?.platforms
    ? Object.entries(status.platforms).map(([platform, info]) => ({
        platform,
        key: platform,
        enabled: (info as { enabled: boolean }).enabled,
        ready: (info as { ready: boolean }).ready,
      }))
    : [];

  return (
    <div>
      {analytics && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}><Card><Statistic title="总视频" value={analytics.total_videos} /></Card></Col>
          <Col span={5}><Card><Statistic title="总播放" value={analytics.total_views} /></Card></Col>
          <Col span={5}><Card><Statistic title="总点赞" value={analytics.total_likes} /></Card></Col>
          <Col span={5}><Card><Statistic title="总评论" value={analytics.total_comments} /></Card></Col>
          <Col span={5}><Card><Statistic title="总分享" value={analytics.total_shares} /></Card></Col>
        </Row>
      )}

      <Card title="发布平台状态" extra={<Button onClick={loadData} loading={loading}>刷新</Button>}>
        <Table
          dataSource={platformData}
          columns={platformColumns}
          rowKey="platform"
          loading={loading}
          pagination={false}
        />
      </Card>
    </div>
  );
}
