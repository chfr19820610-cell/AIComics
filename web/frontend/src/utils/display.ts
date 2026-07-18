const STATUS_LABELS: Record<string, string> = {
  unknown: '未知',
  ok: '正常',
  healthy: '健康',
  unhealthy: '异常',
  needs_attention: '需关注',
  ready: '就绪',
  ready_for_production: '可进入生产',
  ready_with_full_local_provider: '本地服务商全部就绪',
  succeeded: '成功',
  success: '成功',
  failed: '失败',
  blocked: '已阻塞',
  pending: '待处理',
  approved: '已通过',
  changes_requested: '退回修改',
  open: '待处理',
  resolved: '已解决',
  running: '运行中',
  active: '执行中',
  completed: '已完成',
  submitted: '已提交',
  queued: '已排队',
  skipped: '已跳过',
  superseded: '已替代',
  dry_run: '预演',
  generated: '已生成',
  previewed: '已预览',
  archived: '已归档',
  manual_required: '需人工处理',
  approval_required: '需审批',
  current: '进行中',
  done: '已完成',
  draft_ready: '初稿就绪',
  candidate_ready: '候选片就绪',
  publish_ready: '发布就绪',
  pass_to_candidate: '转候选片',
  repair_and_retry: '修复后重试',
  human_hold: '人工接管',
  idea: '创意中',
  script_ready: '剧本就绪',
  shotlist_ready: '分镜就绪',
  assets_ready: '素材就绪',
  initialized: '已初始化',
  jobs_ready: '任务就绪',
  critical: '严重',
  warning: '警告',
  high: '高',
  medium: '中',
  low: '低',
  auto: '自动',
  required: '需确认',
  not_configured: '未配置',
  workspace: '当前系统项目',
  template: '模板项目',
  live: '真实执行',
  revision: '修订版本',
};

const FIELD_LABELS: Record<string, string> = {
  action: '动作',
  action_count: '动作数',
  active_count: '执行中',
  active_job_count: '执行中任务',
  active_jobs: '执行中任务',
  archive_dir: '归档目录',
  archive_root: '归档根目录',
  auth_enabled: '鉴权',
  backlog_count: '积压数',
  batch: '批次',
  batch_count: '批次数',
  batch_id: '批次编号',
  blocked_count: '阻塞数',
  blocked_step_count: '阻塞步骤',
  completed_count: '已完成',
  completed_jobs: '已完成任务',
  completed_step_count: '完成步骤',
  completion_rate: '完成率',
  confirm_live: '真实执行确认',
  count: '数量',
  current_retry_count: '当前重试',
  default_entry: '默认入口',
  default_storage: '默认存储',
  deployment_mode: '部署模式',
  dimension: '维度',
  dispatch_score: '调度分',
  dashboard: '总览报告',
  dry_run: '预演',
  dry_run_count: '预演次数',
  episode_code: '剧集编号',
  episode_count: '剧集数',
  episodes_count: '剧集数',
  episode_impact_count: '影响剧集',
  episodes: '剧集数',
  estimated_step_count: '预计步骤',
  execution_command: '执行命令',
  execution_status: '执行状态',
  failed_count: '失败数',
  failed_step_count: '失败步骤',
  failure_rate: '失败率',
  generated_count: '生成次数',
  history_action_count: '历史动作',
  job_id: '任务编号',
  jobs_count: '任务数',
  job_success_rate: '任务成功率',
  jobs: '任务数',
  latest_batch_id: '最新批次',
  latest_execution_status: '最新执行状态',
  latest_plan_key: '最新计划',
  latest_queue_run_id: '最新队列',
  latest_queue_status: '最新队列状态',
  latest_status: '最新状态',
  manual_import: '手工导入',
  manual_import_rate: '手工导入率',
  manual_required_count: '需人工处理',
  mode: '模式',
  multi_user_enabled: '多用户',
  oidc_enabled: '单点登录',
  path: '路径',
  pending_step_count: '待处理步骤',
  planned_episode_count: '规划集数',
  preview_ready_count: '预览完成',
  priority: '优先级',
  provider: '服务商',
  provider_count: '服务商数',
  provider_execution: '服务商执行报告',
  provider_readiness_status: '服务商就绪状态',
  provider_request_count: '服务商请求数',
  queue: '队列',
  queue_count: '队列数',
  queue_impact_count: '影响队列',
  queue_name: '队列',
  queue_status: '队列状态',
  rbac_enabled: '权限控制',
  readiness_blocking_count: '就绪阻塞数',
  readiness_status: '就绪状态',
  ready_episode_count: '就绪剧集数',
  ready_request_count: '就绪请求数',
  reason: '原因',
  request_count: '请求数',
  retry: '重试',
  retry_count: '重试数',
  retry_rate: '重试率',
  retried_count: '已重试',
  retry_batch: '重试批次报告',
  running_count: '运行中',
  scope_type: '范围类型',
  scope_value: '范围值',
  scoped_job_count: '范围内任务',
  share_rate: '占比',
  shot_count: '镜头数',
  single_user_mode: '单用户',
  status: '状态',
  status_counts: '状态统计',
  step_count: '步骤数',
  step_completion_rate: '步骤完成率',
  succeeded_jobs: '成功任务',
  succeeded_after_import: '导入后成功',
  success_count: '成功数',
  target: '目标',
  target_count: '目标数',
  total_count: '总数',
  total_duration_seconds: '总时长',
  total_jobs: '总任务',
  total_step_count: '总步骤',
  unique_operator_count: '操作人数',
  imported_count: '已导入',
  local_dry_run_count: '本地预演次数',
  local_provider_ready_count: '本地服务商就绪数',
  local_ready_count: '本地就绪数',
  manual_required_after_import: '导入后需人工处理',
  missing_count: '缺失数',
  openai_dry_run_count: '外部模型预演次数',
  production_fallback_ready: '生产回退就绪',
  production_live_provider_ready: '真实服务商就绪',
  production_local_provider_ready: '本地服务商就绪',
  production_local_video_ready: '本地视频就绪',
  production_risk_blocking_count: '阻塞风险数',
  production_risk_register_status: '生产风险状态',
  production_risk_warning_count: '警告风险数',
  validation: '验证报告',
};

const EDITION_LABELS: Record<string, string> = {
  unknown: '未知',
  creator: '创作者版',
  studio: '工作室版',
  enterprise: '企业版',
};

const PRIORITY_LABELS: Record<string, string> = {
  P0: 'P0 紧急',
  P1: 'P1 高',
  P2: 'P2 中',
  P3: 'P3 低',
  high: '高',
  medium: '中',
  low: '低',
};

export function displayStatus(value?: string | null): string {
  if (!value) {
    return '未知';
  }
  return STATUS_LABELS[value] ?? value;
}

export function displayPriority(value?: string | null): string {
  if (!value) {
    return '-';
  }
  return PRIORITY_LABELS[value] ?? value;
}

export function displayBoolean(value?: boolean | null): string {
  return value ? '是' : '否';
}

export function displayEnabled(value?: boolean | null): string {
  return value ? '开' : '关';
}

export function displayFieldLabel(value?: string | null): string {
  if (!value) {
    return '-';
  }
  return FIELD_LABELS[value] ?? value;
}

export function displayEditionName(value?: string | null): string {
  if (!value) {
    return '未知';
  }
  return EDITION_LABELS[value] ?? value.replace(/Creator/g, '创作者').replace(/creator/g, '创作者');
}

export function displaySelectOptions(values: string[]): Array<{ label: string; value: string }> {
  return values.map((value) => ({ label: displayStatus(value), value }));
}

const DISPLAY_PATTERNS: Array<[RegExp, string]> = [
  [/\bmanual_required\b/g, '需人工处理'],
  [/\breview_required\b/g, '待复核'],
  [/\bvisual_text\b/g, '画面文字'],
  [/\bblocking\b/g, '阻塞'],
  [/\bwarning\b/g, '警告'],
  [/\bcritical\b/g, '严重'],
  [/\bfailed\b/g, '失败'],
  [/\brunning\b/g, '运行中'],
  [/\bcompleted\b/g, '已完成'],
  [/\bready\b/g, '就绪'],
  [/\bensure_jobs\b/g, '确保任务包'],
  [/\bbuild_jobs\b/g, '生成任务包'],
  [/\bbuild_provider_requests\b/g, '生成 Provider 请求包'],
  [/\bscan_assets\b/g, '扫描素材状态'],
  [/\brender_preview\b/g, '渲染预览'],
  [/\bbuild_publish_pack\b/g, '生成发布包'],
  [/\bexport_approved_release\b/g, '过审后一键导出'],
  [/\brefresh_creator_reports\b/g, '刷新 Creator 报告'],
  [/\bContact Sheet\b/g, '镜头总览'],
  [/\bRun\b/g, '运行编号'],
  [/\bprovider\b/gi, '服务商'],
  [/\bCreator\b/g, '创作者'],
  [/\bcreator\b/g, '创作者'],
  [/\bPrompt\b/g, '提示词'],
  [/\bprompt\b/g, '提示词'],
  [/\bworkspace\b/gi, '当前系统项目'],
  [/\btemplate\b/gi, '模板项目'],
  [/\blive\b/gi, '真实执行'],
  [/\brevision\b/gi, '修订版本'],
  [/\bdouyin\b/gi, '抖音'],
  [/\bkuaishou\b/gi, '快手'],
  [/\bbilibili\b/gi, 'B站'],
  [/\bOpenAI\b/g, '外部模型服务'],
  [/\bComfyUI\b/g, '本地图像服务'],
  [/\bPiper\b/g, '本地语音服务'],
  [/\bCreator\b/g, '创作者'],
];

export function displayText(value?: string | null): string {
  if (!value) {
    return '';
  }
  let result = value;
  for (const [pattern, replacement] of DISPLAY_PATTERNS) {
    result = result.replace(pattern, replacement);
  }
  return result;
}
