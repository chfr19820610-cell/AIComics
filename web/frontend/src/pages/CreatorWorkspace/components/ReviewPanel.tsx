import { ProCard } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Descriptions,
  Image,
  Input,
  List,
  Row,
  Col,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';

import CompactFactGrid from '@/components/CompactFactGrid';
import type {
  CreatorSampleReviewPayload,
  CreatorWorkspacePayload,
} from '@/types/api';
import {
  displayStatus,
  displayText,
} from '@/utils/display';

const { Text } = Typography;

function reviewStatusColor(status: string): string {
  if (status === 'approved') return 'green';
  if (status === 'changes_requested') return 'red';
  return 'gold';
}

type ReviewPanelProps = {
  activeEpisode?: CreatorWorkspacePayload['episodes'][number];
  sampleReview?: CreatorSampleReviewPayload;
  sampleReviewLoading: boolean;
  sampleReviewSaving: boolean;
  sampleReviewDraft: { decision_summary: string; review_notes: string };
  onDraftChange: (draft: { decision_summary: string; review_notes: string }) => void;
  onSaveReview: (reviewStatus: string) => Promise<void>;
  reviewBlockingCount: number;
  reviewRequiredCount: number;
  candidateReady: boolean;
  assetErrorCount: number;
  contactSheetItems: Array<{
    label: string;
    path: string;
    relative_path: string;
    url: string;
    exists: boolean;
    resolvedUrl: string;
  }>;
  releaseVideoUrl: string;
  onAssetError: (key: string) => void;
};

export default function ReviewPanel({
  activeEpisode,
  sampleReview,
  sampleReviewLoading,
  sampleReviewSaving,
  sampleReviewDraft,
  onDraftChange,
  onSaveReview,
  reviewBlockingCount,
  reviewRequiredCount,
  candidateReady,
  assetErrorCount,
  contactSheetItems,
  releaseVideoUrl,
  onAssetError,
}: ReviewPanelProps) {
  return (
    <ProCard title="样片审核与放行" bordered className="aicomic-compact-card">
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <CompactFactGrid
          items={[
            { label: '当前剧集', value: activeEpisode?.episode_code || '-' },
            { label: '镜头数', value: activeEpisode?.shot_count ?? 0 },
            { label: '总时长', value: `${activeEpisode?.total_duration_seconds ?? 0} 秒` },
            { label: '正式版', value: activeEpisode?.release_exists ? '已生成' : '未生成' },
            { label: '发布包', value: activeEpisode?.publish_pack_exists ? '已生成' : '未生成' },
            { label: '待处理任务', value: activeEpisode?.job_status_distribution?.manual_required ?? 0 },
          ]}
          minColumnWidth={160}
        />
        <Space wrap>
          <Tag color={(activeEpisode?.shot_count ?? 0) >= 40 ? 'green' : 'gold'}>40-60 镜头</Tag>
          <Tag color={(activeEpisode?.total_duration_seconds ?? 0) >= 300 ? 'green' : 'gold'}>5-10 分钟</Tag>
          <Tag color={activeEpisode?.release_exists ? 'green' : 'default'}>正式版视频</Tag>
          <Tag color={activeEpisode?.publish_pack_exists ? 'green' : 'default'}>发布包</Tag>
          <Tag color={reviewStatusColor(sampleReview?.review_status ?? 'pending')}>
            审核 {displayStatus(sampleReview?.review_status ?? 'pending')}
          </Tag>
        </Space>
        <CompactFactGrid
          items={[
            { label: '阻塞问题', value: reviewBlockingCount },
            { label: '待复核问题', value: reviewRequiredCount },
            { label: '审核状态', value: displayStatus(sampleReview?.review_status ?? 'pending') },
            {
              label: '放行结论',
              value: reviewBlockingCount > 0
                ? '先清空阻塞问题'
                : reviewRequiredCount > 0
                  ? '先处理待复核问题'
                  : '可继续放行确认',
            },
          ]}
          minColumnWidth={150}
        />
        {assetErrorCount > 0 ? (
          <CompactFactGrid
            items={[
              { label: '资产加载失败', value: assetErrorCount },
              { label: '建议动作', value: '先检查本地服务和生成产物' },
            ]}
            minColumnWidth={180}
          />
        ) : null}
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={12}>
            <ProCard title="正式版预览" bordered loading={sampleReviewLoading} className="aicomic-compact-card">
              {sampleReview?.release_video.exists && releaseVideoUrl ? (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <video
                    controls
                    preload="metadata"
                    src={releaseVideoUrl}
                    aria-label="正式版视频预览"
                    onError={() => onAssetError('release_video')}
                    style={{ width: '100%', maxHeight: 320, background: '#000' }}
                  />
                  <CompactFactGrid
                    items={[
                      { label: '镜头数', value: sampleReview.release_video.shot_count },
                      { label: '占位镜头', value: sampleReview.release_video.used_placeholder_count },
                      { label: '图片', value: sampleReview.quality_summary.image_count },
                      { label: '音频', value: sampleReview.quality_summary.audio_count },
                      { label: '视频', value: sampleReview.quality_summary.video_count },
                      { label: '待重生成', value: sampleReview.provider_summary.queue_count },
                      { label: '建议动作', value: reviewBlockingCount > 0 ? '先修阻塞问题' : '可继续放行确认' },
                    ]}
                    minColumnWidth={120}
                  />
                </Space>
              ) : (
                <CompactFactGrid
                  items={[
                    { label: '正式版视频', value: '未生成' },
                    { label: '镜头数', value: sampleReview?.release_video.shot_count ?? activeEpisode?.shot_count ?? 0 },
                    { label: '待处理任务', value: activeEpisode?.job_status_distribution?.manual_required ?? 0 },
                    { label: '建议动作', value: activeEpisode?.release_exists ? '检查本地播放链路' : '先生成正式版视频' },
                  ]}
                  minColumnWidth={140}
                />
              )}
            </ProCard>
          </Col>
          <Col xs={24} xl={12}>
            <ProCard title="发布闸门" bordered loading={sampleReviewLoading} className="aicomic-compact-card">
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={sampleReview?.provider_summary.manual_required_count ? 'red' : 'green'}>
                    人工处理 {sampleReview?.provider_summary.manual_required_count ?? 0}
                  </Tag>
                  <Tag color={sampleReview?.provider_summary.queue_count ? 'gold' : 'green'}>
                    重生成队列 {sampleReview?.provider_summary.queue_count ?? 0}
                  </Tag>
                  <Tag color={reviewStatusColor(sampleReview?.review_status ?? 'pending')}>
                    {displayStatus(sampleReview?.review_status ?? 'pending')}
                  </Tag>
                  <Tag color={sampleReview?.export_gate.approved_for_export ? 'green' : 'red'}>
                    发布闸门 {sampleReview?.export_gate.approved_for_export ? '已放行' : '未放行'}
                  </Tag>
                  <Tag color={candidateReady ? 'green' : 'default'}>
                    候选片 {candidateReady ? '已就绪' : '未就绪'}
                  </Tag>
                </Space>
                {sampleReview?.export_gate.blockers?.length ? (
                  <Alert
                    type="warning"
                    showIcon
                    message="当前不能导出发布包"
                    description={sampleReview.export_gate.blockers.join('；')}
                  />
                ) : null}
                <CompactFactGrid
                  items={[
                    { label: '人工处理', value: sampleReview?.provider_summary.manual_required_count ?? 0 },
                    { label: '重生成队列', value: sampleReview?.provider_summary.queue_count ?? 0 },
                    { label: '当前发布版本', value: sampleReview?.export_audit.current_publish_version || '-' },
                    { label: '最后导出编号', value: sampleReview?.export_audit.last_export_run_id || '-' },
                    { label: '候选片时间', value: sampleReview?.candidate_release.candidate_created_at || '-' },
                    { label: '最后确认发布', value: sampleReview?.export_audit.last_confirmed_publish_at || '-' },
                  ]}
                  minColumnWidth={150}
                />
                <div>
                  <Text strong>审核结论</Text>
                  <Input.TextArea
                    rows={2}
                    placeholder="写当前样片是否可过审、还差什么。"
                    value={sampleReviewDraft.decision_summary}
                    onChange={(event) =>
                      onDraftChange({
                        ...sampleReviewDraft,
                        decision_summary: event.target.value,
                      })
                    }
                    style={{ marginTop: 8 }}
                  />
                </div>
                <div>
                  <Text strong>审核备注</Text>
                  <Input.TextArea
                    rows={4}
                    placeholder="记录镜头、节奏、文本残留、封面文案等问题。"
                    value={sampleReviewDraft.review_notes}
                    onChange={(event) =>
                      onDraftChange({
                        ...sampleReviewDraft,
                        review_notes: event.target.value,
                      })
                    }
                    style={{ marginTop: 8 }}
                  />
                </div>
                <Space wrap>
                  <Button loading={sampleReviewSaving} onClick={() => void onSaveReview('pending')}>
                    保存草稿
                  </Button>
                  <Button danger loading={sampleReviewSaving} onClick={() => void onSaveReview('changes_requested')}>
                    退回修改
                  </Button>
                  <Button type="primary" loading={sampleReviewSaving} onClick={() => void onSaveReview('approved')}>
                    审核通过
                  </Button>
                </Space>
                {sampleReview?.publish_pack.publish_title ? (
                  <Descriptions column={1} size="small" bordered>
                    <Descriptions.Item label="发布标题">{sampleReview.publish_pack.publish_title}</Descriptions.Item>
                    <Descriptions.Item label="封面文案">{sampleReview.publish_pack.cover_text || '-'}</Descriptions.Item>
                    <Descriptions.Item label="评论钩子">{sampleReview.publish_pack.comment_seed || '-'}</Descriptions.Item>
                    <Descriptions.Item label="最后导出时间">{sampleReview.export_audit.last_exported_at || '-'}</Descriptions.Item>
                  </Descriptions>
                ) : null}
              </Space>
            </ProCard>
          </Col>
        </Row>
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={10}>
            <ProCard title={`问题清单（${sampleReview?.issues.length ?? 0}）`} bordered loading={sampleReviewLoading} className="aicomic-compact-card">
              <List
                className="aicomic-tight-list"
                size="small"
                locale={{ emptyText: '当前没有审核问题' }}
                dataSource={sampleReview?.issues ?? []}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Space wrap>
                        <Tag color={item.severity === 'blocking' ? 'red' : 'gold'}>{displayStatus(item.severity)}</Tag>
                        <Tag>{displayText(item.category)}</Tag>
                        {item.shot_id ? <Tag color="blue">{item.shot_id}</Tag> : null}
                        <Tag color={item.status === 'resolved' ? 'green' : 'default'}>{displayStatus(item.status)}</Tag>
                      </Space>
                      <Text>{displayText(item.detail)}</Text>
                      {item.resolution_note ? <Text type="secondary">{displayText(item.resolution_note)}</Text> : null}
                    </Space>
                  </List.Item>
                )}
              />
            </ProCard>
          </Col>
          <Col xs={24} xl={14}>
            <ProCard title={`镜头总览（${sampleReview?.contact_sheets.length ?? 0}）`} bordered loading={sampleReviewLoading} className="aicomic-compact-card">
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {contactSheetItems.map((item) => (
                  <Space key={item.path} direction="vertical" size={6} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag color={item.exists ? 'green' : 'default'}>{item.exists ? '已生成' : '缺失'}</Tag>
                      <Text strong>{displayText(item.label)}</Text>
                    </Space>
                    {item.resolvedUrl ? (
                      <Image
                        src={item.resolvedUrl}
                        alt={item.label}
                        style={{ width: '100%' }}
                        onError={() => onAssetError(item.relative_path || item.path)}
                      />
                    ) : (
                      <Text type="secondary">{item.path}</Text>
                    )}
                  </Space>
                ))}
              </Space>
            </ProCard>
          </Col>
        </Row>
        {sampleReview?.recommendations?.length ? (
          <List
            className="aicomic-tight-list"
            size="small"
            header={<Text strong>审核建议</Text>}
            dataSource={sampleReview.recommendations}
            renderItem={(item) => <List.Item>{displayText(item)}</List.Item>}
          />
        ) : null}
      </Space>
    </ProCard>
  );
}
