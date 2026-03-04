export type Goal = {
  id: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
};

export type ResearchRun = {
  id: string;
  goal_id: string;
  status: string;
  config: Record<string, unknown>;
  budget: Record<string, unknown>;
  workspace_root: string;
  started_at?: string;
  ended_at?: string;
  failure_reason?: string;
};

export type TimelineEvent = {
  event_id: string;
  stream_id: string;
  event_type: string;
  occurred_at: string;
  payload: Record<string, unknown>;
};

export type ExperimentRun = {
  id: string;
  experiment_id: string;
  research_run_id: string;
  status: string;
  parameters: Record<string, unknown>;
  logs: Record<string, unknown>;
  result_summary?: string;
  metrics: Record<string, unknown>;
  started_at?: string;
  ended_at?: string;
};

export type AgentTrace = {
  id: string;
  research_run_id: string;
  agent_id: string;
  reasoning_summary: string;
  action: string;
  tool_used?: string;
  tokens_used: number;
  created_at: string;
};

export type EvaluatorScore = {
  id: string;
  research_run_id: string;
  experiment_run_id: string;
  goal_progress: number;
  experiment_quality: number;
  novelty: number;
  confidence: number;
  recommendation: "continue" | "pivot" | "stop";
  rationale: string;
  created_at: string;
};
