import { PageContainer, ProCard } from '@ant-design/pro-components';
import { Alert, Button, Col, Empty, Form, Input, InputNumber, List, Modal, Progress, Row, Space, Tag, Typography, message } from 'antd';
import { useEffect, useState } from 'react';

import { history } from '@umijs/max';

import CompactFactGrid from '@/components/CompactFactGrid';
import MetricCard from '@/components/MetricCard';
import { createCreatorProject, getProjects } from '@/services/api';
import type { CreatorProjectRecord, ProjectsPayload } from '@/types/api';
import { displayStatus, displayText } from '@/utils/display';

const { Paragraph, Text, Title } = Typography;

function renderProjectTags(item: CreatorProjectRecord) {
  return (
    <Space wrap size={[8, 8]}>
      <Tag color="blue">{item.genre || '未设题材'}</Tag>
      <Tag color="purple">{item.style_profile || '未设风格'}</Tag>
      <Tag color={item.has_story_bible ? 'green' : 'default'}>故事设定 {item.has_story_bible ? '已建' : '待补'}</Tag>
      <Tag color={item.has_character_bible ? 'green' : 'default'}>角色卡 {item.has_character_bible ? '已建' : '待补'}</Tag>
      <Tag color={item.has_style_bible ? 'green' : 'default'}>风格模板 {item.has_style_bible ? '已建' : '待补'}</Tag>
    </Space>
  );
}

export default function ProjectsPage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [data, setData] = useState<ProjectsPayload>();
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [createDraft, setCreateDraft] = useState<Record<string, unknown>>({});
  const [createSubmitting, setCreateSubmitting] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      setData(await getProjects());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const items = data?.items ?? [];
  const totalPlannedEpisodes = items.reduce((sum, item) => sum + item.planned_episode_count, 0);
  const totalEpisodeCount = items.reduce((sum, item) => sum + item.episode_count, 0);
  const totalShots = items.reduce((sum, item) => sum + item.shot_count, 0);
  const totalPreviewReady = items.reduce((sum, item) => sum + item.preview_ready_count, 0);
  const totalPublishReady = items.reduce((sum, item) => sum + item.publish_ready_count, 0);
  const workspaceProjects = items.filter((item) => item.source === 'workspace').length;
  const templateProjects = items.filter((item) => item.source !== 'workspace').length;
  const storyBibleCount = items.filter((item) => item.has_story_bible).length;
  const characterBibleCount = items.filter((item) => item.has_character_bible).length;
  const styleBibleCount = items.filter((item) => item.has_style_bible).length;
  const completedProjects = items.filter((item) => item.completion_rate >= 100).length;
  const fullyConfiguredProjects = items.filter(
    (item) => item.has_story_bible && item.has_character_bible && item.has_style_bible,
  ).length;
  const projectsMissingSettings = items.length - fullyConfiguredProjects;

  return (
    <PageContainer
      title="项目队列"
      subTitle="先挑当前最值得推进的项目"
      loading={loading}
      className="aicomic-compact-page"
      extra={[
        <Button
          key="create"
          type="primary"
          onClick={() => {
            setCreateDraft({
              genre: '现代都市短剧',
              style_profile: '动漫漫剧',
              protagonist_name: '女主',
              target_audience: '短剧用户 / 二次元短视频观众',
              tone: '强钩子',
              season_hook: '结尾必须留下身份、关系或真相反转。',
              episode_target_count: 12,
            });
            setCreateOpen(true);
          }}
        >
          新建创作者项目
        </Button>,
      ]}
    >
      {contextHolder}
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={15}>
            <ProCard title="当前项目池" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="blue">项目 {data?.count ?? 0}</Tag>
                  <Tag color={workspaceProjects > 0 ? 'gold' : 'default'}>系统项目 {workspaceProjects}</Tag>
                  <Tag color={templateProjects > 0 ? 'purple' : 'default'}>模板项目 {templateProjects}</Tag>
                  <Tag color={completedProjects === items.length && items.length > 0 ? 'green' : 'blue'}>
                    已完成 {completedProjects}/{items.length || 0}
                  </Tag>
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '规划集数', value: totalPlannedEpisodes },
                    { label: '已生成剧集', value: totalEpisodeCount },
                    { label: '已拆镜头', value: totalShots },
                    { label: '预览完成', value: totalPreviewReady },
                    { label: '发布包', value: totalPublishReady },
                    { label: '项目目录', value: data?.generated_projects_root ?? 'generated_projects' },
                  ]}
                />
                <Text type="secondary">先看哪个项目资产齐、阻塞少、最适合现在继续推进。</Text>
                <Text type="secondary">如果设定资产还没补齐，不要急着进 Creator 页，先在这里识别风险。</Text>
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={9}>
            <ProCard title="进入前风险" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={storyBibleCount > 0 ? 'green' : 'default'}>故事设定 {storyBibleCount}</Tag>
                  <Tag color={characterBibleCount > 0 ? 'green' : 'default'}>角色卡 {characterBibleCount}</Tag>
                  <Tag color={styleBibleCount > 0 ? 'green' : 'default'}>风格模板 {styleBibleCount}</Tag>
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '预览完成', value: totalPreviewReady },
                    { label: '发布包完成', value: totalPublishReady },
                    { label: '项目完成数', value: completedProjects },
                    { label: '设定齐备', value: fullyConfiguredProjects },
                    { label: '待补资产项目', value: projectsMissingSettings },
                    { label: '建议动作', value: projectsMissingSettings > 0 ? '先补设定资产' : '可直接进 Creator 页' },
                  ]}
                  minColumnWidth={140}
                />
                <Text type="secondary">这里只回答现在进去会不会返工。</Text>
              </Space>
            </ProCard>
          </Col>
        </Row>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}>
            <MetricCard title="项目数" value={data?.count ?? 0} />
          </Col>
          <Col xs={12} md={6}>
            <MetricCard
              title="规划集数"
              value={totalPlannedEpisodes}
            />
          </Col>
          <Col xs={12} md={6}>
            <MetricCard
              title="已拆镜头"
              value={totalShots}
            />
          </Col>
          <Col xs={12} md={6}>
            <MetricCard
              title="预览完成"
              value={totalPreviewReady}
            />
          </Col>
        </Row>
        <ProCard bordered title={`项目清单（${data?.count ?? 0}）`} className="aicomic-compact-card">
          {items.length ? (
            <List
              className="aicomic-tight-list"
              split
              dataSource={items}
              renderItem={(item) => (
                <List.Item
                  actions={[
                    <Button
                      key="open"
                      type="link"
                      href={`/creator?project_id=${encodeURIComponent(item.project_id)}`}
                    >
                      继续推进
                    </Button>,
                  ]}
                >
                  <div style={{ width: '100%' }}>
                    <Space direction="vertical" size={8} style={{ width: '100%' }}>
                      <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
                        <Space wrap>
                          <Title level={5} style={{ margin: 0 }}>{displayText(item.project_name)}</Title>
                          <Tag color={item.source === 'workspace' ? 'gold' : 'default'}>
                            {item.source === 'workspace' ? '当前系统项目' : '模板项目'}
                          </Tag>
                          <Tag color="default">{displayStatus(item.status)}</Tag>
                        </Space>
                        <Text type="secondary">项目 {item.project_id}</Text>
                      </Space>
                      {renderProjectTags(item)}
                      <Paragraph style={{ marginBottom: 0 }} ellipsis={{ rows: 2, tooltip: item.logline || '-' }}>
                        {item.logline || '还没有补充项目一句话设定。'}
                      </Paragraph>
                      <CompactFactGrid
                        items={[
                          { label: '主角 / 受众', value: `${item.protagonist_name || '-'} / ${item.target_audience || '-'}` },
                          { label: '目标平台', value: displayText(item.target_platforms.join(' / ')) || '-' },
                          { label: '剧集进度', value: `${item.episode_count}/${item.planned_episode_count}` },
                          { label: '镜头 / 预览 / 发布包', value: `${item.shot_count} / ${item.preview_ready_count} / ${item.publish_ready_count}` },
                        ]}
                        minColumnWidth={180}
                      />
                      <Progress
                        percent={item.completion_rate}
                        size="small"
                        status={item.completion_rate >= 100 ? 'success' : 'active'}
                        format={(percent) => `推进度 ${percent ?? 0}%`}
                      />
                      <Space size={6} wrap>
                        <Text type="secondary">项目目录</Text>
                        <Text type="secondary">{item.project_root}</Text>
                      </Space>
                    </Space>
                  </div>
                </List.Item>
              )}
            />
          ) : (
            <Empty description="还没有发现创作者项目。" />
          )}
        </ProCard>
      </Space>
      <Modal
        open={createOpen}
        title="新建创作者项目"
        width={760}
        onCancel={() => setCreateOpen(false)}
        okButtonProps={{ form: 'create-creator-project-form', htmlType: 'submit', disabled: createSubmitting }}
        confirmLoading={createSubmitting}
      >
        <Form
          id="create-creator-project-form"
          key={JSON.stringify(createDraft)}
          layout="vertical"
          initialValues={createDraft}
          onFinish={async (values) => {
            setCreateSubmitting(true);
            try {
              const result = await createCreatorProject(values);
              messageApi.success('创作者项目已创建');
              setCreateOpen(false);
              await refresh();
              const projectId = String(result.project_id ?? '');
              if (projectId) {
                history.push(`/creator?project_id=${encodeURIComponent(projectId)}`);
              }
            } finally {
              setCreateSubmitting(false);
            }
          }}
        >
          <Row gutter={12}>
            <Col span={12}><Form.Item name="project_name" label="项目名" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="project_id" label="项目编号"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="genre" label="题材" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="style_profile" label="风格" rules={[{ required: true }]}><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="protagonist_name" label="主角"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="target_audience" label="受众"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="logline" label="一句话设定"><Input.TextArea rows={3} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="tone" label="调性"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="episode_target_count" label="目标集数"><InputNumber min={1} max={24} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="season_hook" label="本季钩子"><Input.TextArea rows={3} /></Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
}
