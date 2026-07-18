import { PageContainer, ProCard, ProTable } from '@ant-design/pro-components';
import {
  Alert,
  Button,
  Col,
  Descriptions,
  Drawer,
  Form,
  Image,
  Input,
  InputNumber,
  List,
  Modal,
  Popconfirm,
  Progress,
  Row,
  Select,
  Space,
  Steps,
  Switch,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { useEffect, useMemo, useState } from 'react';

import CompactFactGrid from '@/components/CompactFactGrid';
import MetricCard from '@/components/MetricCard';
import EpisodeTable from './components/EpisodeTable';
import ShotList from './components/ShotList';
import ReviewPanel from './components/ReviewPanel';
import {
  buildCreatorAssetUrl,
  deleteCreatorShot,
  getCreatorSampleReview,
  getCreatorWorkspace,
  getProjects,
  runCreatorAction,
  saveCreatorEpisode,
  saveCreatorProjectProfile,
  saveCreatorSampleReview,
  saveCreatorShot,
} from '@/services/api';
import type {
  CreatorActionCatalogItem,
  CreatorActionRunResult,
  CreatorDeliverableRecord,
  CreatorRunRecord,
  CreatorSampleReviewPayload,
  CreatorStepRecord,
  CreatorWorkspacePayload,
  EpisodeRecord,
  ProjectsPayload,
  ShotRecord,
} from '@/types/api';
import { displayFieldLabel, displayPriority, displaySelectOptions, displayStatus, displayText } from '@/utils/display';

const { Paragraph, Text, Title } = Typography;

type CreatorEpisode = CreatorWorkspacePayload['episodes'][number];

const episodeStatusOptions = displaySelectOptions(['idea', 'script_ready', 'shotlist_ready', 'assets_ready']);
const shotPriorityOptions = displaySelectOptions(['high', 'medium', 'low']);

function currentProjectId(): string {
  if (typeof window === 'undefined') {
    return '';
  }
  return new URLSearchParams(window.location.search).get('project_id') ?? '';
}

function updateProjectQuery(projectId: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  const url = new URL(window.location.href);
  if (projectId) {
    url.searchParams.set('project_id', projectId);
  } else {
    url.searchParams.delete('project_id');
  }
  window.history.replaceState({}, '', url.toString());
}

function stepStatus(status: string): 'finish' | 'process' | 'wait' {
  if (status === 'done') {
    return 'finish';
  }
  if (status === 'current') {
    return 'process';
  }
  return 'wait';
}

function deliverableColor(item: CreatorDeliverableRecord): string {
  return item.exists ? 'green' : 'default';
}

function reviewStatusColor(status: string): string {
  if (status === 'approved') {
    return 'green';
  }
  if (status === 'changes_requested') {
    return 'red';
  }
  return 'gold';
}

function mapShotToFormValues(shot?: ShotRecord) {
  return {
    shot_id: shot?.shot_id ?? '',
    duration: shot?.duration ?? 3,
    scene: shot?.scene ?? '',
    characters: shot?.characters?.join(', ') ?? '',
    visual: shot?.visual ?? '',
    action: shot?.action ?? '',
    dialogue: shot?.dialogue ?? '',
    emotion: shot?.emotion ?? '',
    camera: shot?.camera ?? '',
    ai_video: shot?.ai_video ?? false,
    priority: shot?.priority ?? 'medium',
  };
}

function resolveErrorMessage(error: unknown, fallback: string): string {
  const messageText = (error as Error | undefined)?.message;
  if (typeof messageText === 'string' && messageText.trim()) {
    return messageText.trim();
  }
  return fallback;
}

function isRevisionConflictMessage(messageText: string): boolean {
  return messageText.includes('修订版本') || messageText.includes('expected revision') || messageText.includes('revision');
}

export default function CreatorWorkspacePage() {
  const [messageApi, contextHolder] = message.useMessage();
  const [projects, setProjects] = useState<ProjectsPayload>();
  const [workspace, setWorkspace] = useState<CreatorWorkspacePayload>();
  const [selectedProjectId, setSelectedProjectId] = useState(currentProjectId());
  const [selectedEpisodeCode, setSelectedEpisodeCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [episodeModalOpen, setEpisodeModalOpen] = useState(false);
  const [shotDrawerOpen, setShotDrawerOpen] = useState(false);
  const [editingEpisode, setEditingEpisode] = useState<CreatorEpisode | null>(null);
  const [editingShot, setEditingShot] = useState<ShotRecord | null>(null);
  const [actionResult, setActionResult] = useState<CreatorActionRunResult | null>(null);
  const [sampleReview, setSampleReview] = useState<CreatorSampleReviewPayload>();
  const [sampleReviewLoading, setSampleReviewLoading] = useState(false);
  const [sampleReviewSaving, setSampleReviewSaving] = useState(false);
  const [assetLoadErrors, setAssetLoadErrors] = useState<Record<string, boolean>>({});
  const [sampleReviewDraft, setSampleReviewDraft] = useState({
    decision_summary: '',
    review_notes: '',
  });
  const [projectDraft, setProjectDraft] = useState<Record<string, unknown>>({});
  const [episodeDraft, setEpisodeDraft] = useState<Record<string, unknown>>({});
  const [shotDraft, setShotDraft] = useState<Record<string, unknown>>({});

  const refreshAll = async (projectId: string) => {
    setLoading(true);
    try {
      const [projectsPayload, workspacePayload] = await Promise.all([
        getProjects(),
        getCreatorWorkspace(projectId || undefined),
      ]);
      setProjects(projectsPayload);
      setWorkspace(workspacePayload);
      const activeProjectId = projectId || workspacePayload.project.project_id || projectsPayload.active_project_id;
      setSelectedProjectId(activeProjectId);
      updateProjectQuery(activeProjectId);
      const activeEpisodeCode = workspacePayload.episodes[0]?.episode_code ?? '';
      setSelectedEpisodeCode((current) => {
        if (current && workspacePayload.episodes.some((item) => item.episode_code === current)) {
          return current;
        }
        return activeEpisodeCode;
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshAll(currentProjectId());
  }, []);

  const projectOptions = useMemo(
    () => (projects?.items ?? []).map((item) => ({ label: item.project_name, value: item.project_id })),
    [projects],
  );

  const project = workspace?.project;
  const summary = workspace?.production_summary;
  const activeEpisode = workspace?.episodes.find((item) => item.episode_code === selectedEpisodeCode) ?? workspace?.episodes[0];
  useEffect(() => {
    if (!selectedProjectId || !activeEpisode?.episode_code) {
      setSampleReview(undefined);
      setSampleReviewDraft({
        decision_summary: '',
        review_notes: '',
      });
      return;
    }
    let cancelled = false;
    setSampleReviewLoading(true);
    void getCreatorSampleReview(selectedProjectId, activeEpisode.episode_code)
      .then((payload) => {
        if (cancelled) return;
        setSampleReview(payload);
        setSampleReviewDraft({
          decision_summary: payload.decision_summary,
          review_notes: payload.review_notes,
        });
      })
      .catch((error) => {
        if (cancelled) return;
        void handleRequestError(error, '加载样片审核失败', selectedProjectId);
      })
      .finally(() => {
        if (!cancelled) setSampleReviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeEpisode?.episode_code, selectedProjectId]);
  useEffect(() => {
    setAssetLoadErrors({});
  }, [selectedProjectId, activeEpisode?.episode_code, sampleReview?.updated_at]);
  const deliverables = workspace?.deliverables ?? [];
  const recentRuns = workspace?.recent_runs ?? [];
  const readyDeliverableCount = deliverables.filter((item) => item.exists).length;
  const nextActions = workspace?.next_actions ?? [];
  const readyEpisodeCount = (workspace?.episodes ?? []).filter(
    (item) => item.preview_exists || item.release_exists || item.publish_pack_exists,
  ).length;
  const previewReadyEpisodeCount = (workspace?.episodes ?? []).filter((item) => item.preview_exists).length;
  const publishReadyEpisodeCount = (workspace?.episodes ?? []).filter((item) => item.publish_pack_exists).length;
  const configuredAssetCount = [
    workspace?.story_bible_summary.exists,
    workspace?.character_bible_summary.exists,
    workspace?.style_bible_summary.exists,
    workspace?.prompt_pack_summary.exists,
  ].filter(Boolean).length;
  const activeEpisodeProgress = activeEpisode?.total_jobs
    ? Math.round(((activeEpisode.completed_jobs ?? 0) / activeEpisode.total_jobs) * 100)
    : 0;
  const reviewBlockingCount = sampleReview?.quality_summary.blocking_findings ?? 0;
  const reviewRequiredCount = sampleReview?.quality_summary.review_required_findings ?? 0;
  const autopilotStatus = sampleReview?.autopilot_state.autopilot_status ?? 'draft_ready';
  const candidateReady = sampleReview?.candidate_release.candidate_status === 'ready';
  const autopilotDecision = sampleReview?.auto_review_decision.decision ?? '';
  const autopilotReasons = sampleReview?.auto_review_decision.reasons ?? [];
  const releaseVideoUrl =
    selectedProjectId && sampleReview?.release_video.relative_path
      ? buildCreatorAssetUrl(selectedProjectId, sampleReview.release_video.relative_path)
      : '';
  const contactSheetItems = (sampleReview?.contact_sheets ?? []).map((item) => ({
    ...item,
    resolvedUrl:
      selectedProjectId && item.relative_path
        ? buildCreatorAssetUrl(selectedProjectId, item.relative_path)
        : '',
  }));
  const assetErrorCount = Object.values(assetLoadErrors).filter(Boolean).length;
  const recentRunSucceededCount = recentRuns.filter((item) => item.status === 'succeeded').length;
  const recentRunFailedCount = recentRuns.filter((item) => item.status === 'failed').length;

  const handleSaveSampleReview = async (reviewStatus: string) => {
    if (!selectedProjectId || !activeEpisode?.episode_code || !sampleReview) {
      return;
    }
    try {
      setSampleReviewSaving(true);
      const payload = await saveCreatorSampleReview({
        project_id: selectedProjectId,
        episode_code: activeEpisode.episode_code,
        review_status: reviewStatus,
        decision_summary: sampleReviewDraft.decision_summary,
        review_notes: sampleReviewDraft.review_notes,
        issues: sampleReview.issues,
      });
      setSampleReview(payload);
      setSampleReviewDraft({
        decision_summary: payload.decision_summary,
        review_notes: payload.review_notes,
      });
      messageApi.success('样片审核已保存');
      await refreshAll(selectedProjectId);
    } catch (error) {
      await handleRequestError(error, '保存样片审核失败', selectedProjectId);
    } finally {
      setSampleReviewSaving(false);
    }
  };

  const openProjectEditor = () => {
    if (!project) return;
    setProjectDraft({
      project_id: project.project_id,
      project_name: project.project_name,
      genre: project.genre,
      style_profile: project.style_profile,
      protagonist_name: project.protagonist_name,
      target_audience: project.target_audience,
      tone: project.tone,
      logline: project.logline,
      season_hook: project.season_hook,
      episode_target_count: project.planned_episode_count,
      target_platforms: project.target_platforms,
    });
    setProjectModalOpen(true);
  };

  const openEpisodeEditor = (episode: CreatorEpisode) => {
    setEditingEpisode(episode);
    setEpisodeDraft({
      project_id: workspace?.project.project_id,
      episode_code: episode.episode_code,
      title: episode.title,
      status: episode.status,
      publish_title: episode.publish_title,
      cover_text: episode.cover_text,
      creator_goal: episode.creator_goal,
      ending_hook: episode.ending_hook,
    });
    setEpisodeModalOpen(true);
  };

  const openShotEditor = (shot?: ShotRecord) => {
    setEditingShot(shot ?? null);
    setShotDraft({
      episode_code: activeEpisode?.episode_code,
      ...mapShotToFormValues(shot),
    });
    setShotDrawerOpen(true);
  };

  const handleRequestError = async (error: unknown, fallback: string, projectId?: string) => {
    const detail = resolveErrorMessage(error, fallback);
    messageApi.error(detail);
    if (projectId && isRevisionConflictMessage(detail)) {
      await refreshAll(projectId);
    }
    return detail;
  };

  const handleRunAction = async (action: CreatorActionCatalogItem) => {
    if (!workspace?.project.project_id) {
      return;
    }
    setLoading(true);
    try {
      const result = await runCreatorAction({
        project_id: workspace.project.project_id,
        action: action.key,
        episode_code: activeEpisode?.episode_code,
      });
      setActionResult(result);
      if (result.status === 'completed') {
        messageApi.success(`${displayText(action.label)} 已完成`);
      } else {
        messageApi.error(result.error_detail ? displayText(result.error_detail) : `${displayText(action.label)} 执行失败`);
      }
      await refreshAll(workspace.project.project_id);
    } catch (error) {
      console.error(error);
      const detail = await handleRequestError(error, `${displayText(action.label)} 执行失败`, workspace.project.project_id);
      setActionResult({
        action: action.key,
        label: action.label,
        project_id: workspace.project.project_id,
        project_root: workspace.project.project_root,
        episode_code: activeEpisode?.episode_code ?? '',
        status: 'failed',
        error_code: 'RequestError',
        error_detail: detail,
      });
    } finally {
      setLoading(false);
    }
  };

  const renderActionButton = (action: CreatorActionCatalogItem) => {
    const requiresApproval = Boolean(action.requires_review_approval);
    const blockedByReview = requiresApproval && !sampleReview?.export_gate.approved_for_export;
    const blockedByCandidate = action.key === 'confirm_candidate_publish' && !candidateReady;
    const disabledReason = blockedByReview
      ? sampleReview?.export_gate.blockers?.join('；') || '当前样片还没有通过发布闸门。'
      : blockedByCandidate
        ? '当前还没有已就绪的候选片。'
        : '';
    const primaryActions = new Set(['autopilot_candidate_release', 'confirm_candidate_publish', 'export_approved_release']);
    const button = (
      <Button
        key={action.key}
        type={primaryActions.has(action.key) ? 'primary' : 'default'}
        onClick={() => void handleRunAction(action)}
        disabled={blockedByReview || blockedByCandidate}
      >
        {displayText(action.label)}
      </Button>
    );
    return disabledReason ? (
      <Tooltip key={action.key} title={disabledReason}>
        <span>{button}</span>
      </Tooltip>
    ) : (
      button
    );
  };

  return (
    <PageContainer
      title="项目驾驶舱"
      subTitle="看状态、判风险、执行下一步"
      loading={loading}
      className="aicomic-compact-page"
      extra={[
        <Select
          key="project"
          style={{ minWidth: 220 }}
          placeholder="选择项目"
          options={projectOptions}
          value={selectedProjectId || projects?.active_project_id}
          onChange={(value) => {
            void refreshAll(value);
          }}
        />,
        <Button key="projects" href="/projects">
          查看项目列表
        </Button>,
      ]}
    >
      {contextHolder}
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        <Row gutter={[12, 12]}>
          <Col xs={24} xl={15}>
            <ProCard title="当前项目状态" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="blue">{project?.project_name || '未选择项目'}</Tag>
                  <Tag color="purple">{displayStatus(project?.status || 'idea')}</Tag>
                  {activeEpisode ? <Tag color="gold">当前剧集 {activeEpisode.episode_code}</Tag> : null}
                  <Tag color={summary?.completion_rate === 100 ? 'green' : 'blue'}>
                    完成度 {summary?.completion_rate ?? 0}%
                  </Tag>
                  <Tag color={readyDeliverableCount === deliverables.length && deliverables.length > 0 ? 'green' : 'default'}>
                    产物 {readyDeliverableCount}/{deliverables.length || 0}
                  </Tag>
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '规划集数', value: summary?.planned_episode_count ?? 0 },
                    { label: '当前剧集数', value: workspace?.episodes.length ?? 0 },
                    { label: '已拆镜头', value: summary?.shot_count ?? 0 },
                    { label: '总时长', value: `${summary?.total_duration_seconds ?? 0} 秒` },
                    { label: '预览就绪', value: `${previewReadyEpisodeCount}/${workspace?.episodes.length ?? 0}` },
                    { label: '发布包就绪', value: `${publishReadyEpisodeCount}/${workspace?.episodes.length ?? 0}` },
                    { label: '最近动作', value: displayText(nextActions[0] ?? '从项目设定开始，逐步完成镜头、素材、预览和发布包。') },
                    { label: '建议动作', value: reviewBlockingCount > 0 ? '先处理阻塞问题' : displayText(nextActions[0] ?? '继续推进当前剧集') },
                  ]}
                  minColumnWidth={150}
                />
                <Text type="secondary">先看项目、当前集、完成度和建议动作。</Text>
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={9}>
            <ProCard title="项目身份与版本" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color="blue">项目修订 {workspace?.revision_summary.project_manifest_revision_id || '-'}</Tag>
                  <Tag color="purple">季修订 {workspace?.revision_summary.season_manifest_revision_id || '-'}</Tag>
                  <Tag color="gold">剧集修订 {workspace?.revision_summary.episode_manifest_revision_id || '-'}</Tag>
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '项目编号', value: project?.project_id || '-' },
                    { label: '题材', value: project?.genre || '-' },
                    { label: '风格', value: project?.style_profile || '-' },
                    { label: '目标平台', value: displayText(project?.target_platforms.join(' / ') || '-') },
                    { label: '项目目录', value: project?.project_root || '-' },
                  ]}
                  minColumnWidth={150}
                />
                <Text type="secondary">这里只回答这是谁、哪个版本、发到哪。</Text>
              </Space>
            </ProCard>
          </Col>
        </Row>
        <Row gutter={[12, 12]}>
          <Col xs={12} md={6}><MetricCard title="规划集数" value={summary?.planned_episode_count ?? 0} /></Col>
          <Col xs={12} md={6}><MetricCard title="已拆镜头" value={summary?.shot_count ?? 0} /></Col>
          <Col xs={12} md={6}><MetricCard title="总时长" value={summary?.total_duration_seconds ?? 0} suffix="秒" /></Col>
          <Col xs={12} md={6}><MetricCard title="完成度" value={summary?.completion_rate ?? 0} suffix="%" /></Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={8}>
            <ProCard title="可执行动作" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Space wrap size={[8, 8]}>
                  {(workspace?.action_catalog ?? []).map(renderActionButton)}
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '动作数', value: workspace?.action_catalog.length ?? 0 },
                    { label: '当前剧集', value: activeEpisode?.episode_code || '-' },
                    { label: '已就绪产物', value: `${readyDeliverableCount}/${deliverables.length || 0}` },
                    { label: '下一动作', value: displayText(nextActions[0] ?? '先执行首个创作者动作，开始产生日志与产物。') },
                    { label: '放行状态', value: sampleReview?.export_gate.approved_for_export ? '可导出' : '待审核' },
                  ]}
                  minColumnWidth={140}
                />
                <Text type="secondary">这里只放当前可执行入口。</Text>
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={8}>
            <ProCard title="候选片状态" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={autopilotStatus === 'candidate_ready' ? 'green' : autopilotStatus === 'human_hold' ? 'red' : 'blue'}>
                    自动驾驶 {displayStatus(autopilotStatus)}
                  </Tag>
                  <Tag color={candidateReady ? 'green' : 'default'}>
                    候选片 {candidateReady ? '已就绪' : '未就绪'}
                  </Tag>
                  <Tag color={autopilotDecision === 'pass_to_candidate' ? 'green' : autopilotDecision === 'repair_and_retry' ? 'gold' : 'default'}>
                    审片决策 {displayText(autopilotDecision || '-')}
                  </Tag>
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '当前轮次', value: sampleReview?.autopilot_state.repair_cycle_count ?? 0 },
                    { label: '最大轮次', value: sampleReview?.autopilot_state.max_repair_cycles ?? 0 },
                    { label: '已修镜头', value: sampleReview?.autopilot_audit.total_repaired_shots ?? 0 },
                    { label: '质量分', value: sampleReview?.candidate_release.quality_score ?? 0 },
                    { label: '当前运行编号', value: sampleReview?.autopilot_state.autopilot_run_id || '-' },
                    { label: '候选片时间', value: sampleReview?.candidate_release.candidate_created_at || '-' },
                    { label: '放行状态', value: sampleReview?.export_gate.approved_for_export ? '已放行' : '未放行' },
                    { label: '建议动作', value: candidateReady ? '可确认发布' : '先继续自动修或审核' },
                  ]}
                  minColumnWidth={140}
                />
                {autopilotReasons.length ? (
                  <Alert
                    type={autopilotDecision === 'pass_to_candidate' ? 'success' : autopilotDecision === 'repair_and_retry' ? 'warning' : 'error'}
                    showIcon
                    message="自动审片结论"
                    description={autopilotReasons.join('；')}
                  />
                ) : (
                  <Text type="secondary">当前没有新增审片原因，按上方状态继续推进。</Text>
                )}
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={8}>
            <ProCard title="当前阶段" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <Steps
                  responsive
                  items={(workspace?.steps ?? []).map((item: CreatorStepRecord) => ({
                    title: displayText(item.title),
                    description: displayText(item.detail),
                    status: stepStatus(item.status),
                  }))}
                />
                <Text type="secondary">这里只回答现在走到哪、下一步干什么。</Text>
              </Space>
            </ProCard>
          </Col>
        </Row>

        <ProCard title="最近运行" bordered className="aicomic-compact-card">
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <CompactFactGrid
                  items={[
                    { label: '运行记录', value: recentRuns.length },
                    { label: '当前项目', value: project?.project_name || '-' },
                    { label: '就绪剧集', value: `${readyEpisodeCount}/${workspace?.episodes.length || 0}` },
                    { label: '成功运行', value: recentRunSucceededCount },
                    { label: '失败运行', value: recentRunFailedCount },
                    { label: '最新运行编号', value: recentRuns[0]?.run_id || '-' },
                    { label: '下一建议动作', value: displayText(nextActions[0] ?? '先执行一项创作者动作，生成最初的运行记录。') },
                  ]}
                  minColumnWidth={180}
                />
            {recentRuns.length > 0 ? (
              <List
                className="aicomic-tight-list"
                size="small"
                dataSource={recentRuns}
                renderItem={(item: CreatorRunRecord) => (
                  <List.Item>
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                      <Space wrap>
                        <Text strong>{displayText(item.action_label)}</Text>
                        <Tag color={item.status === 'succeeded' ? 'green' : item.status === 'failed' ? 'red' : 'blue'}>
                          {displayStatus(item.status)}
                        </Tag>
                        <Text type="secondary">{item.run_id}</Text>
                      </Space>
                      <Text type="secondary">
                        {item.episode_code} · 步骤 {item.completed_step_count}/{item.step_count}
                        {item.current_step_key ? ` · 当前 ${displayText(item.current_step_key)}` : ''}
                      </Text>
                      {item.error_detail ? <Text type="danger">{displayText(item.error_detail)}</Text> : null}
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <CompactFactGrid
                  items={[
                    { label: '运行记录', value: 0 },
                    { label: '当前项目', value: project?.project_name || '-' },
                    { label: '就绪剧集', value: `${readyEpisodeCount}/${workspace?.episodes.length || 0}` },
                    { label: '成功运行', value: 0 },
                    { label: '失败运行', value: 0 },
                    { label: '下一建议动作', value: displayText(nextActions[0] ?? '先执行第一个创作者动作，生成最初的运行记录。') },
                  ]}
                />
                <Text type="secondary">当前还没有运行记录，先执行一项创作者动作。</Text>
              </Space>
            )}
          </Space>
        </ProCard>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={12}>
            <ProCard title="项目设定" bordered extra={<Button onClick={openProjectEditor}>编辑项目</Button>} className="aicomic-compact-card">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <CompactFactGrid
                  items={[
                    { label: '题材', value: project?.genre || '-' },
                    { label: '风格', value: project?.style_profile || '-' },
                    { label: '主角', value: project?.protagonist_name || '-' },
                    { label: '受众', value: project?.target_audience || '-' },
                    { label: '调性', value: project?.tone || '-' },
                    { label: '平台', value: displayText(project?.target_platforms.join(' / ') || '-') },
                    { label: '项目状态', value: displayStatus(project?.status || 'idea') },
                    { label: '规划集数', value: project?.planned_episode_count ?? 0 },
                    { label: '当前剧集数', value: workspace?.episodes.length ?? 0 },
                    { label: '已就绪产物', value: `${readyDeliverableCount}/${deliverables.length || 0}` },
                    { label: '当前剧集', value: activeEpisode?.episode_code || '-' },
                    { label: '一句话设定', value: project?.logline || '待补' },
                    { label: '本季钩子', value: project?.season_hook || '待补' },
                    { label: '建议动作', value: configuredAssetCount < 4 ? '先补设定资产' : '可继续剧集推进' },
                  ]}
                />
              </Space>
            </ProCard>
          </Col>
          <Col xs={24} xl={12}>
            <ProCard title="设定资产" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                <Space wrap>
                  <Tag color={workspace?.story_bible_summary.exists ? 'green' : 'default'}>故事圣经</Tag>
                  <Tag color={workspace?.character_bible_summary.exists ? 'green' : 'default'}>角色卡 {workspace?.character_bible_summary.count ?? 0}</Tag>
                  <Tag color={workspace?.style_bible_summary.exists ? 'green' : 'default'}>风格模板 {workspace?.style_bible_summary.aspect_ratio || '9:16'}</Tag>
                  <Tag color={workspace?.prompt_pack_summary.exists ? 'green' : 'default'}>提示词模板</Tag>
                </Space>
                <CompactFactGrid
                  items={[
                    { label: '故事设定', value: workspace?.story_bible_summary.exists ? '已建立' : '待补' },
                    { label: '故事钩子', value: workspace?.story_bible_summary.concept_logline || '待补故事设定' },
                    { label: '角色卡', value: workspace?.character_bible_summary.count ?? 0 },
                    { label: '风格模板', value: workspace?.style_bible_summary.exists ? '已建立' : '待补' },
                    { label: '提示词模板', value: workspace?.prompt_pack_summary.exists ? '已建立' : '待补' },
                    { label: '已就绪资产', value: `${configuredAssetCount}/4` },
                    { label: '角色名称', value: workspace?.character_bible_summary.names.join(' / ') || '待补角色名称' },
                    { label: '画幅', value: workspace?.style_bible_summary.aspect_ratio || '9:16' },
                    { label: '视觉方向', value: workspace?.style_bible_summary.visual_direction.join(' / ') || '待补视觉指令' },
                    { label: '提示词摘要', value: workspace?.prompt_pack_summary.image_prompt_template || '待补提示词模板' },
                    { label: '建议动作', value: configuredAssetCount < 4 ? '先补齐设定资产' : '可继续镜头与素材执行' },
                  ]}
                  minColumnWidth={140}
                />
              </Space>
            </ProCard>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={16}>
            <EpisodeTable
              episodes={workspace?.episodes ?? []}
              activeEpisode={activeEpisode}
              onSelectEpisode={setSelectedEpisodeCode}
              onEditEpisode={openEpisodeEditor}
              previewReadyEpisodeCount={previewReadyEpisodeCount}
              publishReadyEpisodeCount={publishReadyEpisodeCount}
            />
          </Col>
          <Col xs={24} xl={8}>
            <ProCard title="当前剧集详情" bordered className="aicomic-compact-card">
              {activeEpisode ? (
                <Space direction="vertical" size={8} style={{ width: '100%' }}>
                  <Space wrap>
                    <Tag color="blue">{activeEpisode.episode_code}</Tag>
                    <Tag color="purple">{displayStatus(activeEpisode.status)}</Tag>
                    <Tag color={activeEpisode.preview_exists ? 'green' : 'default'}>预览</Tag>
                    <Tag color={activeEpisode.release_exists ? 'green' : 'default'}>正式版</Tag>
                    <Tag color={activeEpisode.publish_pack_exists ? 'green' : 'default'}>发布包</Tag>
                  </Space>
                  <CompactFactGrid
                    items={[
                      { label: '标题', value: activeEpisode.title || '-' },
                      { label: '发布标题', value: activeEpisode.publish_title || '-' },
                      { label: '本集目标', value: activeEpisode.creator_goal || '-' },
                      { label: '封面文案', value: activeEpisode.cover_text || '-' },
                      { label: '镜头 / 时长', value: `${activeEpisode.shot_count} / ${activeEpisode.total_duration_seconds} 秒` },
                      { label: '完成度', value: `${activeEpisode.completed_jobs}/${activeEpisode.total_jobs} (${activeEpisodeProgress}%)` },
                      { label: 'AI 视频 / 静态', value: `${activeEpisode.ai_video_shot_count} / ${activeEpisode.static_shot_count}` },
                      { label: '结尾钩子', value: activeEpisode.ending_hook || '-' },
                    ]}
                    minColumnWidth={150}
                  />
                  <List
                    className="aicomic-tight-list"
                    size="small"
                    dataSource={nextActions.slice(0, 3)}
                    locale={{ emptyText: '当前没有待执行动作' }}
                    renderItem={(item) => (
                      <List.Item>
                        <Tag color="blue">动作</Tag>
                        <Text>{displayText(item)}</Text>
                      </List.Item>
                    )}
                  />
                  <Text type="secondary">这里只保留当前标题、完成度、镜头结构和下一步动作。</Text>
                </Space>
              ) : (
                <Text type="secondary">先选择一个剧集。</Text>
              )}
            </ProCard>
          </Col>
        </Row>

        <Row gutter={[12, 12]}>
          <Col xs={24} xl={14}>
            <ShotList
              activeEpisode={activeEpisode}
              workspace={workspace}
              onOpenShotEditor={openShotEditor}
              onDeleteShot={async (shot) => {
                if (!workspace?.project.project_id || !activeEpisode) return;
                try {
                  await deleteCreatorShot({
                    project_id: workspace.project.project_id,
                    episode_code: activeEpisode.episode_code,
                    shot_id: shot.shot_id,
                    expected_episode_manifest_revision_id: workspace?.revision_summary.episode_manifest_revision_id,
                  });
                  messageApi.success(`已删除镜头 ${shot.shot_id}`);
                  await refreshAll(workspace.project.project_id);
                } catch (error) {
                  await handleRequestError(error, `删除镜头 ${shot.shot_id} 失败`, workspace.project.project_id);
                }
              }}
            />
          </Col>
          <Col xs={24} xl={10}>
            <ProCard title="可交付产物" bordered className="aicomic-compact-card">
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                <CompactFactGrid
                  items={[
                    { label: '已就绪产物', value: `${readyDeliverableCount}/${deliverables.length || 0}` },
                    { label: '当前剧集', value: activeEpisode?.episode_code || '-' },
                  ]}
                  minColumnWidth={150}
                />
                <List
                  className="aicomic-tight-list"
                  size="small"
                  dataSource={deliverables}
                  renderItem={(item: CreatorDeliverableRecord) => (
                    <List.Item>
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space wrap>
                          <Tag color={deliverableColor(item)}>{displayStatus(item.stage)}</Tag>
                          <Text strong>{displayText(item.label)}</Text>
                        </Space>
                        <Text type="secondary">{item.path}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </Space>
            </ProCard>
          </Col>
        </Row>

        <ReviewPanel
          activeEpisode={activeEpisode}
          sampleReview={sampleReview}
          sampleReviewLoading={sampleReviewLoading}
          sampleReviewSaving={sampleReviewSaving}
          sampleReviewDraft={sampleReviewDraft}
          onDraftChange={(draft) => setSampleReviewDraft(draft)}
          onSaveReview={handleSaveSampleReview}
          reviewBlockingCount={reviewBlockingCount}
          reviewRequiredCount={reviewRequiredCount}
          candidateReady={candidateReady}
          assetErrorCount={assetErrorCount}
          contactSheetItems={contactSheetItems}
          releaseVideoUrl={releaseVideoUrl}
          onAssetError={(key) => {
            setAssetLoadErrors((current) => ({
              ...current,
              [key]: true,
            }));
          }}
        />

        <ProCard title="工程文件路径" bordered className="aicomic-compact-card">
          <List
            className="aicomic-tight-list"
            size="small"
            dataSource={Object.entries(workspace?.source_paths ?? {})}
            renderItem={([key, value]) => (
              <List.Item>
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Text strong>{displayFieldLabel(key)}</Text>
                  <Text type="secondary">{value}</Text>
                </Space>
              </List.Item>
            )}
          />
        </ProCard>
      </Space>

      <Modal
        open={projectModalOpen}
        title="编辑项目设定"
        width={760}
        onCancel={() => setProjectModalOpen(false)}
        okButtonProps={{ form: 'creator-project-form', htmlType: 'submit' }}
      >
        <Form
          id="creator-project-form"
          key={JSON.stringify(projectDraft)}
          layout="vertical"
          initialValues={projectDraft}
          onFinish={async (values) => {
            try {
              await saveCreatorProjectProfile({
                ...values,
                expected_project_manifest_revision_id: workspace?.revision_summary.project_manifest_revision_id,
                expected_season_manifest_revision_id: workspace?.revision_summary.season_manifest_revision_id,
              });
              messageApi.success('项目设定已保存');
              setProjectModalOpen(false);
              await refreshAll(String(values.project_id || selectedProjectId));
            } catch (error) {
              await handleRequestError(error, '保存项目设定失败', String(values.project_id || selectedProjectId));
            }
          }}
        >
          <Form.Item name="project_id" hidden><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="project_name" label="项目名" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="genre" label="题材" rules={[{ required: true }]}><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="style_profile" label="风格" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="protagonist_name" label="主角"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="target_audience" label="受众"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="tone" label="调性"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="logline" label="一句话设定"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="season_hook" label="本季钩子"><Input.TextArea rows={3} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="episode_target_count" label="目标集数"><InputNumber min={1} max={24} style={{ width: '100%' }} /></Form.Item></Col>
            <Col span={12}>
              <Form.Item name="target_platforms" label="目标平台">
                <Select
                  mode="tags"
                  options={['抖音', '快手', '视频号', '小红书', 'B站短视频'].map((item) => ({ label: item, value: item }))}
                />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      <Modal
        open={episodeModalOpen}
        title="编辑剧集"
        width={680}
        onCancel={() => setEpisodeModalOpen(false)}
        okButtonProps={{ form: 'creator-episode-form', htmlType: 'submit' }}
      >
        <Form
          id="creator-episode-form"
          key={JSON.stringify(episodeDraft)}
          layout="vertical"
          initialValues={episodeDraft}
          onFinish={async (values) => {
            try {
              await saveCreatorEpisode({
                ...values,
                expected_episode_manifest_revision_id: workspace?.revision_summary.episode_manifest_revision_id,
              });
              messageApi.success('剧集已保存');
              setEpisodeModalOpen(false);
              await refreshAll(String(values.project_id || selectedProjectId));
            } catch (error) {
              await handleRequestError(error, '保存剧集失败', String(values.project_id || selectedProjectId));
            }
          }}
        >
          <Form.Item name="project_id" initialValue={workspace?.project.project_id} hidden><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="episode_code" label="剧集编号" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}>
              <Form.Item name="status" label="状态">
                <Select options={episodeStatusOptions} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="creator_goal" label="本集目标"><Input.TextArea rows={2} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="publish_title" label="发布标题"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="cover_text" label="封面文案"><Input /></Form.Item></Col>
          </Row>
          <Form.Item name="ending_hook" label="结尾钩子"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Drawer
        open={shotDrawerOpen}
        title={editingShot ? `编辑镜头 ${editingShot.shot_id}` : '新增镜头'}
        width={720}
        onClose={() => setShotDrawerOpen(false)}
        extra={
          <Button type="primary" htmlType="submit" form="creator-shot-form">
            保存
          </Button>
        }
      >
        <Form
          id="creator-shot-form"
          key={JSON.stringify(shotDraft)}
          layout="vertical"
          initialValues={shotDraft}
          onFinish={async (values) => {
            if (!workspace?.project.project_id) return;
            try {
              await saveCreatorShot({
                project_id: workspace.project.project_id,
                episode_code: values.episode_code,
                shot_id: values.shot_id,
                duration: values.duration,
                scene: values.scene,
                characters: String(values.characters || '')
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean),
                visual: values.visual,
                action: values.action,
                dialogue: values.dialogue,
                emotion: values.emotion,
                camera: values.camera,
                ai_video: values.ai_video,
                priority: values.priority,
                expected_episode_manifest_revision_id: workspace?.revision_summary.episode_manifest_revision_id,
              });
              messageApi.success('镜头已保存');
              setShotDrawerOpen(false);
              await refreshAll(workspace.project.project_id);
            } catch (error) {
              await handleRequestError(error, '保存镜头失败', workspace.project.project_id);
            }
          }}
        >
          <Form.Item name="episode_code" initialValue={activeEpisode?.episode_code} hidden><Input /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="shot_id" label="镜头编号" rules={[{ required: true }]}><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="duration" label="时长(秒)" rules={[{ required: true }]}><InputNumber min={1} max={12} style={{ width: '100%' }} /></Form.Item></Col>
          </Row>
          <Form.Item name="scene" label="场景"><Input /></Form.Item>
          <Form.Item name="characters" label="角色（逗号分隔）"><Input /></Form.Item>
          <Form.Item name="visual" label="画面描述"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="action" label="动作描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="dialogue" label="台词"><Input.TextArea rows={2} /></Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="emotion" label="情绪"><Input /></Form.Item></Col>
            <Col span={12}><Form.Item name="camera" label="运镜"><Input /></Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="priority" label="优先级">
                <Select options={shotPriorityOptions} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="ai_video" label="是否智能视频镜头" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Drawer>

      <Modal
        open={Boolean(actionResult)}
        title="最近一次创作者动作结果"
        footer={null}
        onCancel={() => setActionResult(null)}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="动作">{displayText(actionResult?.label)}</Descriptions.Item>
            <Descriptions.Item label="状态">{displayStatus(actionResult?.status)}</Descriptions.Item>
            <Descriptions.Item label="剧集">{actionResult?.episode_code || '-'}</Descriptions.Item>
            <Descriptions.Item label="运行编号">{actionResult?.run_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="运行状态">{displayStatus(actionResult?.run_status || actionResult?.status)}</Descriptions.Item>
            <Descriptions.Item label="步骤进度">
              {actionResult?.step_count !== undefined ? `${actionResult.completed_step_count ?? 0}/${actionResult.step_count}` : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="当前步骤">
              {actionResult?.current_step_key ? displayText(actionResult.current_step_key) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="输出">{actionResult?.output_path || actionResult?.dashboard_path || '-'}</Descriptions.Item>
            <Descriptions.Item label="错误代码">{actionResult?.error_code || '-'}</Descriptions.Item>
            <Descriptions.Item label="错误详情">
              {actionResult?.error_detail ? displayText(actionResult.error_detail) : '-'}
            </Descriptions.Item>
          </Descriptions>
          {actionResult?.revision_summary ? (
            <Space wrap>
              <Tag color="blue">项目修订 {actionResult.revision_summary.project_manifest_revision_id || '-'}</Tag>
              <Tag color="purple">季修订 {actionResult.revision_summary.season_manifest_revision_id || '-'}</Tag>
              <Tag color="gold">剧集修订 {actionResult.revision_summary.episode_manifest_revision_id || '-'}</Tag>
            </Space>
          ) : null}
          {actionResult?.job_count !== undefined ? <Text>任务数：{actionResult.job_count}</Text> : null}
          {actionResult?.request_count !== undefined ? <Text>请求数：{actionResult.request_count} / 就绪 {actionResult.ready_count ?? 0}</Text> : null}
          {actionResult?.shot_count !== undefined ? <Text>镜头数：{actionResult.shot_count}</Text> : null}
          {actionResult?.title_candidate_count !== undefined ? <Text>标题候选：{actionResult.title_candidate_count}</Text> : null}
          {actionResult?.missing_required_count !== undefined ? <Text>缺失必需素材：{actionResult.missing_required_count}</Text> : null}
          {actionResult?.artifacts?.length ? (
            <List
              size="small"
              header={<Text strong>本次产物</Text>}
              dataSource={actionResult.artifacts}
              renderItem={(item) => (
                <List.Item>
                  <Space direction="vertical" size={2} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag>{displayText(item.artifact_role)}</Tag>
                      <Text>{item.output_path}</Text>
                    </Space>
                  </Space>
                </List.Item>
              )}
            />
          ) : null}
        </Space>
      </Modal>
    </PageContainer>
  );
}
