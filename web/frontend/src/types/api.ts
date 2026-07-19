export type ListPayload<T> = {
  items: T[];
  count: number;
  [key: string]: unknown;
};

export type HealthPayload = {
  status: string;
  project_root: string;
  host: string;
  port: number;
  auth_enabled: boolean;
  edition_name: string;
  edition_display_name: string;
};

export type EditionPolicyPayload = {
  edition_name: string;
  display_name: string;
  creator_only: boolean;
  auth_enabled: boolean;
  batch_enabled: boolean;
  auth_reason: string;
  creator_only_reason: string;
};

export type EditionCapabilityPayload = {
  edition_name: string;
  display_name: string;
  capabilities: {
    edition_name: string;
    display_name: string;
    single_user_mode: boolean;
    multi_user_enabled: boolean;
    auth_enabled: boolean;
    oidc_enabled: boolean;
    rbac_enabled: boolean;
    audit_enabled: boolean;
    batch_enabled: boolean;
    distributed_queue_enabled: boolean;
    enterprise_storage_enabled: boolean;
    cost_control_enabled: boolean;
    default_database: string;
    default_storage: string;
    deployment_mode: string;
    default_entry: string;
    capability_count: number;
  };
  policy?: EditionPolicyPayload;
  source: string;
  preset_options: string[];
};

export type DashboardPayload = {
  title?: string;
  status?: string;
  overview?: Record<string, number>;
  batch?: Record<string, unknown>;
  season?: Record<string, unknown>;
  provider?: Record<string, unknown>;
  manual_import?: Record<string, unknown>;
  retry?: Record<string, unknown>;
  source_reports?: Record<string, string>;
  episode_states?: Record<string, {
    episode_code?: string;
    status?: string;
    completed_jobs?: number;
    total_jobs?: number;
  }>;
  job_status_by_episode?: Record<string, Record<string, number>>;
  next_actions?: string[];
};

export type CreatorProjectRecord = {
  project_id: string;
  project_name: string;
  genre: string;
  style_profile: string;
  status: string;
  logline: string;
  protagonist_name: string;
  target_audience: string;
  tone: string;
  season_hook: string;
  target_platforms: string[];
  project_root: string;
  source: string;
  episode_count: number;
  planned_episode_count: number;
  shot_count: number;
  total_duration_seconds: number;
  preview_ready_count: number;
  publish_ready_count: number;
  completion_rate: number;
  has_story_bible: boolean;
  has_character_bible: boolean;
  has_style_bible: boolean;
  owner_user_id?: string;
};

export type CreatorRevisionSummary = {
  project_manifest_revision_id?: string;
  season_manifest_revision_id?: string;
  episode_manifest_revision_id?: string;
};

export type ShotRecord = {
  shot_id: string;
  duration: number;
  scene: string;
  characters: string[];
  visual: string;
  action: string;
  dialogue: string;
  emotion: string;
  camera: string;
  ai_video: boolean;
  priority: string;
  act_id?: string;
  horror_beat?: string;
  continuity_anchor?: string;
  avoidance_strategy?: string;
  sound_cue?: string;
  regeneration_reason?: string;
};

export type EpisodeRecord = {
  episode_code: string;
  title: string;
  status: string;
  completed_jobs: number;
  total_jobs: number;
  shot_count: number;
  total_duration_seconds: number;
  publish_title: string;
  cover_text: string;
  preview_exists: boolean;
  release_exists: boolean;
  publish_pack_exists: boolean;
  ai_video_shot_count: number;
  static_shot_count: number;
};

export type CreatorStepRecord = {
  key: string;
  title: string;
  status: string;
  detail: string;
};

export type CreatorDeliverableRecord = {
  key: string;
  label: string;
  path: string;
  exists: boolean;
  stage: string;
};

export type CreatorActionCatalogItem = {
  key: string;
  label: string;
  description: string;
  requires_review_approval?: boolean;
};

export type CreatorActionRunResult = {
  action: string;
  label: string;
  project_id: string;
  project_root: string;
  episode_code: string;
  status: string;
  run_id?: string;
  run_status?: string;
  current_step_key?: string;
  step_count?: number;
  completed_step_count?: number;
  submitted_at?: string;
  started_at?: string;
  completed_at?: string;
  error_code?: string;
  error_detail?: string;
  revision_summary?: CreatorRevisionSummary;
  artifacts?: Array<{
    artifact_id: string;
    artifact_key: string;
    artifact_type: string;
    artifact_role: string;
    artifact_status: string;
    output_path: string;
    created_at: string;
  }>;
  output_path?: string;
  report_output_path?: string;
  validation_report_path?: string;
  dashboard_path?: string;
  review_metrics_path?: string;
  job_count?: number;
  request_count?: number;
  ready_count?: number;
  blocked_count?: number;
  shot_count?: number;
  target_seconds?: number;
  total_duration_seconds?: number;
  used_placeholder_count?: number;
  title_candidate_count?: number;
  missing_required_count?: number;
  missing_optional_count?: number;
  ready_for_preview?: boolean;
  success_count?: number;
  failed_count?: number;
  skipped_count?: number;
  limit?: number;
  queue_count?: number;
  high_priority_count?: number;
  manual_required_count?: number;
  changed_count?: number;
  succeeded_count?: number;
  decision?: string;
  reasons?: string[];
  quality_score?: number;
  selected_job_ids?: string[];
  selected_shot_ids?: string[];
  repair_cycle_count?: number;
  candidate_status?: string;
  release_output_path?: string;
  publish_pack_output_path?: string;
  export_audit?: {
    export_count: number;
    current_publish_version: string;
    last_exported_at: string;
    last_export_run_id: string;
    last_exported_by_user_id: string;
    last_release_output_path: string;
    last_publish_pack_output_path: string;
    last_candidate_run_id?: string;
    last_candidate_created_at?: string;
    last_confirmed_publish_at?: string;
    last_confirmed_by_user_id?: string;
  };
};

export type CreatorSampleReviewIssue = {
  issue_id: string;
  severity: string;
  category: string;
  shot_id: string;
  detail: string;
  status: string;
  resolution_note: string;
};

export type CreatorAutoReviewDecision = {
  decision: string;
  reasons: string[];
  policy_version: string;
  measured_metrics: Record<string, unknown>;
  next_action: string;
};

export type CreatorSampleReviewPayload = {
  project_id: string;
  episode_code: string;
  review_status: string;
  decision_summary: string;
  review_notes: string;
  reviewer_user_id: string;
  created_at: string;
  updated_at: string;
  review_file_path: string;
  release_video: {
    path: string;
    relative_path: string;
    url: string;
    exists: boolean;
    shot_count: number;
    used_placeholder_count: number;
    render_mode: string;
  };
  publish_pack: {
    title: string;
    publish_title: string;
    cover_text: string;
    description: string;
    hashtags: string[];
    comment_seed: string;
  };
  provider_summary: {
    request_count: number;
    job_count: number;
    succeeded_count: number;
    manual_required_count: number;
    changed_count: number;
    queue_count: number;
    high_priority_count: number;
  };
  quality_summary: {
    image_count: number;
    audio_count: number;
    video_count: number;
    valid_image_count: number;
    valid_audio_count: number;
    valid_video_count: number;
    blocking_findings: number;
    review_required_findings: number;
  };
  contact_sheets: Array<{
    label: string;
    path: string;
    relative_path: string;
    url: string;
    exists: boolean;
  }>;
  issues: CreatorSampleReviewIssue[];
  recommendations: string[];
  export_gate: {
    review_status: string;
    approved_for_export: boolean;
    blockers: string[];
  };
  auto_review_decision: CreatorAutoReviewDecision;
  autopilot_state: {
    autopilot_status: string;
    autopilot_run_id: string;
    policy_version: string;
    repair_cycle_count: number;
    max_repair_cycles: number;
    last_decision: string;
    last_decision_at: string;
    last_transition_reason: string;
  };
  candidate_release: {
    candidate_status: string;
    candidate_run_id: string;
    candidate_created_at: string;
    release_output_path: string;
    publish_pack_output_path: string;
    quality_score: number;
    quality_summary: {
      blocking_findings: number;
      review_required_findings: number;
      manual_required_count: number;
      queue_count: number;
    };
  };
  autopilot_audit: {
    total_runtime_seconds: number;
    total_repaired_shots: number;
    repaired_shot_ids: string[];
    last_escalation_reason: string;
    final_route: string;
    last_contact_sheet_path: string;
  };
  export_audit: {
    export_count: number;
    current_publish_version: string;
    last_exported_at: string;
    last_export_run_id: string;
    last_exported_by_user_id: string;
    last_release_output_path: string;
    last_publish_pack_output_path: string;
    last_candidate_run_id: string;
    last_candidate_created_at: string;
    last_confirmed_publish_at: string;
    last_confirmed_by_user_id: string;
  };
};

export type CreatorRunRecord = {
  run_id: string;
  user_id: string;
  project_id: string;
  project_root: string;
  episode_code: string;
  action: string;
  action_label: string;
  status: string;
  current_step_key: string;
  submitted_at: string;
  started_at: string;
  completed_at: string;
  error_code: string;
  error_detail: string;
  step_count: number;
  completed_step_count: number;
  result: Record<string, unknown>;
  artifacts: Array<{
    artifact_id: string;
    artifact_key: string;
    artifact_type: string;
    artifact_role: string;
    artifact_status: string;
    output_path: string;
    created_at: string;
    metadata?: Record<string, unknown>;
  }>;
};

export type CreatorWorkspacePayload = {
  project: CreatorProjectRecord;
  production_summary: {
    episode_count: number;
    planned_episode_count: number;
    shot_count: number;
    total_duration_seconds: number;
    preview_ready_count: number;
    publish_ready_count: number;
    completion_rate: number;
  };
  steps: CreatorStepRecord[];
  episodes: Array<
    EpisodeRecord & {
      creator_goal?: string;
      ending_hook?: string;
      job_status_distribution?: Record<string, number>;
      shots?: ShotRecord[];
    }
  >;
  deliverables: CreatorDeliverableRecord[];
  story_bible_summary: {
    exists: boolean;
    concept_logline: string;
    core_conflict: string;
    tone_keywords: string[];
  };
  character_bible_summary: {
    exists: boolean;
    count: number;
    names: string[];
  };
  style_bible_summary: {
    exists: boolean;
    style_profile: string;
    aspect_ratio: string;
    visual_direction: string[];
  };
  episode_blueprint_summary: {
    exists: boolean;
    episode_target_count: number;
    arc_count: number;
  };
  prompt_pack_summary: {
    exists: boolean;
    image_prompt_template: string;
    video_prompt_template: string;
  };
  release_checklist_exists: boolean;
  next_actions: string[];
  revision_summary: CreatorRevisionSummary;
  recent_runs?: CreatorRunRecord[];
  action_catalog: CreatorActionCatalogItem[];
  source_paths: Record<string, string>;
};

export type ProjectsPayload = ListPayload<CreatorProjectRecord> & {
  active_project_id: string;
  generated_projects_root: string;
};

export type JobRecord = {
  job_id: string;
  episode_code: string;
  shot_id?: string;
  job_type: string;
  provider: string;
  status: string;
};

export type BatchRecord = {
  batch_id: string;
  status: string;
  scope_type: string;
  scope_value: string;
  step_count: number;
  completed_step_count: number;
  step_completion_rate?: number;
  summary_path: string;
  batch_path?: string;
  batch_report_path?: string;
  updated_at?: number;
};

export type BatchRuntimeRiskFlag = {
  level: string;
  name: string;
  detail: string;
};

export type BatchRuntimeQueueRecord = {
  queue_name: string;
  total_count: number;
  active_count: number;
  failed_count: number;
  manual_required_count: number;
};

export type BatchRuntimeQueueTrendRecord = {
  queue_name: string;
  total_count: number;
  retried_count?: number;
  load_bar_width: number;
  backlog_count: number;
  backlog_bar_width: number;
  queue_status: string;
};

export type BatchRuntimeProviderRecord = {
  provider: string;
  queue_name: string;
  total_count: number;
  active_count: number;
  failed_count: number;
};

export type BatchRuntimeEpisodeRecord = {
  episode_code: string;
  total_count: number;
  completed_count: number;
  active_count: number;
  completion_rate: number;
};

export type BatchRuntimeActiveJobRecord = {
  job_id: string;
  episode_code: string;
  job_type: string;
  provider: string;
  queue_name?: string;
  status: string;
};

export type BatchRuntimeStepResult = {
  step_name: string;
  status: string;
  output_path: string;
  message: string;
};

export type BatchRetryHistoryRecord = {
  audit_id: string;
  user_id: string;
  dry_run: boolean;
  retried_count: number;
  episode_code: string;
  provider: string;
  statuses: string[];
  created_at: string;
};

export type BatchRetryTrendRecord = {
  period: string;
  action_count: number;
  retry_count: number;
  retry_bar_width: number;
  dry_run_count: number;
  generated_count: number;
  success_count: number;
  unique_operator_count: number;
  queue_impact_count: number;
  episode_impact_count: number;
  impact_bar_width: number;
};

export type BatchRuntimeRetrySummary = {
  exists: boolean;
  report_path: string;
  retried_count: number;
  scoped_job_count: number;
};

export type BatchExecutionPreviewHistoryRecord = {
  preview_run_id: string;
  user_id: string;
  plan_key: string;
  source_type: string;
  source_key: string;
  title: string;
  priority: string;
  target: string;
  mode: string;
  execution_command: string;
  estimated_step_count: number;
  requires_manual_approval: boolean;
  status: string;
  preview_summary: string;
  created_at: string;
};

export type BatchExecutionQueueHistoryRecord = {
  queue_run_id: string;
  user_id: string;
  plan_key: string;
  source_type: string;
  source_key: string;
  title: string;
  priority: string;
  target: string;
  mode: string;
  execution_command: string;
  estimated_step_count: number;
  requires_manual_approval: boolean;
  queue_status: string;
  execution_status: string;
  queue_summary: string;
  result_note: string;
  completed_at: string;
  created_at: string;
  updated_at: string;
};

export type BatchExecutionStepRecord = {
  order: number;
  step_key: string;
  title: string;
  action: string;
};

export type BatchExecutionQueueSummary = {
  queued_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
  approval_required_count: number;
  priority_counts: Record<string, number>;
  status_counts: Record<string, number>;
  execution_status_counts: Record<string, number>;
  completion_rate: number;
  failure_rate: number;
  latest_queue_run_id: string;
  latest_plan_key: string;
  latest_priority: string;
  latest_queue_status: string;
};

export type BatchExecutionOperationsArchiveRecord = {
  archive_id: string;
  archived_at: string;
  health_status: string;
  top_failure_reason: string;
  metric_count: number;
  file_count: number;
  archive_dir: string;
};

export type BatchExecutionOperationsReport = {
  health_status: string;
  recommendations: string[];
  top_failure_reason: string;
  latest_queue_run_id: string;
  latest_queue_status: string;
  latest_execution_status: string;
};

export type MultiBatchSummary = {
  batch_count: number;
  status_counts: Record<string, number>;
  scope_type_counts: Record<string, number>;
  completed_batch_count: number;
  running_batch_count: number;
  blocked_batch_count: number;
  other_batch_count: number;
  total_step_count: number;
  completed_step_count: number;
  step_completion_rate: number;
  latest_batch_id: string;
  latest_status: string;
  latest_summary_path: string;
  failure_hotspots: Array<{
    batch_id: string;
    scope_type: string;
    scope_value: string;
    status: string;
    failed_step_count: number;
    blocked_step_count: number;
    pending_step_count: number;
    hotspot_score: number;
    hotspot_level: string;
    hotspot_bar_width: number;
    summary_path: string;
  }>;
  failure_hotspot_count: number;
  retry_hotspots: Array<{
    dimension: string;
    name: string;
    retry_count: number;
    current_retry_count: number;
    history_action_count: number;
    dry_run_count: number;
    generated_count: number;
    hotspot_score: number;
    hotspot_level: string;
    hotspot_bar_width: number;
  }>;
  retry_hotspot_count: number;
  priority_actions: Array<{
    priority: string;
    action_type: string;
    target: string;
    reason: string;
    suggested_command: string;
  }>;
  priority_action_count: number;
  auto_disposition_templates: Array<{
    template_key: string;
    title: string;
    priority: string;
    trigger_type: string;
    target: string;
    suggested_command: string;
    checklist: string[];
  }>;
  auto_disposition_template_count: number;
  dispatch_strategy: {
    strategy_key: string;
    strategy_name: string;
    description: string;
    weights: Record<string, number>;
    thresholds: Record<string, number>;
    score_formula: string;
  };
  dispatch_priority_plan: Array<{
    dimension: string;
    target: string;
    dispatch_score: number;
    recommended_priority: string;
    active_count: number;
    failed_count: number;
    manual_required_count: number;
    retried_count: number;
    backlog_count: number;
    dispatch_bar_width: number;
    reason: string;
  }>;
  dispatch_priority_count: number;
  execution_plan_templates: Array<{
    plan_key: string;
    source_type: string;
    source_key: string;
    title: string;
    priority: string;
    target: string;
    mode: string;
    execution_command: string;
    estimated_step_count: number;
    requires_manual_approval: boolean;
    steps: BatchExecutionStepRecord[];
  }>;
  execution_plan_template_count: number;
  execution_preview_history_count: number;
  execution_preview_history: BatchExecutionPreviewHistoryRecord[];
  execution_queue_summary: BatchExecutionQueueSummary;
  execution_operations_report: BatchExecutionOperationsReport;
  execution_failure_breakdown_count: number;
  execution_failure_breakdown: Array<{
    dimension: string;
    name: string;
    failed_count: number;
    share_rate: number;
    priority_count: number;
    target_count: number;
    latest_queue_run_id: string;
  }>;
  execution_queue_history_count: number;
  execution_queue_history: BatchExecutionQueueHistoryRecord[];
};

export type BatchRuntimeMonitor = {
  status: string;
  next_actions: string[];
  job_total_count: number;
  job_completed_count: number;
  job_active_count: number;
  job_failed_count: number;
  job_manual_required_count: number;
  risk_flag_count: number;
  risk_flags: BatchRuntimeRiskFlag[];
  queue_count: number;
  queues: BatchRuntimeQueueRecord[];
  queue_trend_count: number;
  queue_trends: BatchRuntimeQueueTrendRecord[];
  provider_count: number;
  providers: BatchRuntimeProviderRecord[];
  episode_count: number;
  episodes: BatchRuntimeEpisodeRecord[];
  retry_summary: BatchRuntimeRetrySummary;
  retry_history_count: number;
  retry_history: BatchRetryHistoryRecord[];
  retry_trend_count: number;
  retry_trends: BatchRetryTrendRecord[];
  active_job_count: number;
  active_jobs: BatchRuntimeActiveJobRecord[];
  step_result_count: number;
  step_results: BatchRuntimeStepResult[];
};

export type BatchesPayload = ListPayload<BatchRecord> & {
  multi_batch_summary?: MultiBatchSummary;
  runtime_monitor?: BatchRuntimeMonitor;
};

export type BatchRetryHistoryPayload = {
  items: BatchRetryHistoryRecord[];
  count: number;
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type BatchExecutionPreviewHistoryPayload = {
  items: BatchExecutionPreviewHistoryRecord[];
  count: number;
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type BatchExecutionQueueHistoryPayload = {
  items: BatchExecutionQueueHistoryRecord[];
  count: number;
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type BatchRetryGenerateResult = {
  status: string;
  dry_run: boolean;
  retried_count: number;
  scoped_job_count: number;
  report_output_path: string;
  jobs_output_path: string;
  retry_candidates?: BatchRuntimeActiveJobRecord[];
};

export type BatchExecutionPlanPreviewResult = {
  preview_run_id: string;
  plan_key: string;
  target: string;
  mode: string;
  execution_command: string;
  estimated_step_count: number;
  requires_manual_approval: boolean;
  status: string;
  priority: string;
  steps: BatchExecutionStepRecord[];
};

export type BatchExecutionPlanQueueResult = {
  queue_run_id: string;
  plan_key: string;
  target: string;
  mode: string;
  status: string;
  priority: string;
  queue_status: string;
  execution_status: string;
  queue_summary: string;
};

export type BatchExecutionQueueStatusResult = {
  queue_run_id: string;
  queue_status: string;
  execution_status: string;
  result_note?: string;
  status?: string;
};

export type BatchExecutionOperationsExportResult = {
  export_scope: string;
  export_format?: string;
  export_name: string;
  export_path: string;
  export_count: number;
  status?: string;
};

export type BatchExecutionOperationsArchivesPayload = {
  archive_root: string;
  archive_count: number;
  total_count: number;
  archives: BatchExecutionOperationsArchiveRecord[];
  reason?: string;
};

export type BatchExecutionOperationsArchiveCleanupResult = {
  dry_run: boolean;
  archive_root: string;
  eligible_count: number;
  deleted_count: number;
  deleted_archives?: BatchExecutionOperationsArchiveRecord[];
  skipped_archives?: BatchExecutionOperationsArchiveRecord[];
};

export type ProviderExecutionRecord = {
  name: string;
  request_count: number;
  success_count: number;
  failed_count: number;
  dry_run_count: number;
  blocked_count: number;
  confirm_live: boolean;
  path: string;
};

export type ReviewMetricsPayload = {
  title?: string;
  status: string;
  metrics?: {
    job_success_rate?: number;
    episode_ready_rate?: number;
    manual_import_rate?: number;
    retry_rate?: number;
    [key: string]: number | undefined;
  };
  counts?: Record<string, unknown>;
  source_reports?: Record<string, string>;
  risk_flags?: Array<{
    level: string;
    name: string;
    detail: string;
  }>;
  recommendations?: string[];
};

// Shot versioning types
export type ShotVersionRecord = {
  version_id: string;
  episode_code: string;
  shot_id: string;
  version_number: number;
  parent_version_id: string | null;
  label: string;
  description: string;
  snapshot_json: string;
  created_at: string;
};

export type VersionDiffPayload = {
  version_id_a: string;
  version_id_b: string;
  has_changes: boolean;
  fields_changed: Record<string, { old: unknown; new: unknown }>;
  fields_added: Record<string, unknown>;
  fields_removed: string[];
  changed_count: number;
  added_count: number;
  removed_count: number;
};

export type VersionBoardPayload = {
  episode_code: string;
  shots: Record<string, Array<{
    version_id: string;
    version_number: number;
    parent_version_id: string | null;
    label: string;
    description: string;
    created_at: string;
    snapshot: Record<string, unknown>;
    tags: string[];
  }>>;
  shot_count: number;
  total_versions: number;
};

export type VersionRollbackResult = {
  version_id: string;
  episode_code: string;
  shot_id: string;
  version_number: number;
  label: string;
  description: string;
  created_at: string;
};

export type AuthUser = {
  user_id: string;
  username: string;
  display_name: string;
  email: string;
  status: string;
  default_role: string;
  last_login_at: string;
};

export type AuthProviderItem = {
  name: string;
  label: string;
  enabled: boolean;
  mode?: string;
  start_path?: string;
};

export type AuthProvidersPayload = {
  auth_enabled: boolean;
  edition_name?: string;
  items: AuthProviderItem[];
};

export type AuthConfigPayload = {
  auth_enabled: boolean;
  password_login_enabled: boolean;
  edition_name?: string;
  edition_display_name?: string;
  auth_reason?: string;
  creator_only_reason?: string;
  configured_auth_enabled?: boolean;
};

export type AuthSessionPayload = {
  authenticated: boolean;
  auth_enabled?: boolean;
  access_token?: string;
  refresh_token?: string;
  user?: AuthUser | null;
  login_source?: string;
  detail?: string;
};

// ── Video preview types ────────────────────────────────────────────────

export type VideoRecord = {
  filename: string;
  size_bytes: number;
  mtime: number;
  is_symlink: boolean;
  real_filename: string | null;
};

export type VideoListPayload = {
  items: VideoRecord[];
  count: number;
};
