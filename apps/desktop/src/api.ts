import { AgentTrace, EvaluatorScore, ExperimentRun, Goal, ResearchRun, TimelineEvent } from "./types";

function headers(token?: string): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getHealth(baseUrl: string, token?: string) {
  const res = await fetch(`${baseUrl}/health`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getGoals(baseUrl: string, token?: string): Promise<Goal[]> {
  const res = await fetch(`${baseUrl}/goals`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createGoal(baseUrl: string, title: string, description: string, token?: string): Promise<string> {
  const res = await fetch(`${baseUrl}/goals`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers(token) },
    body: JSON.stringify({ title, description }),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()).goal_id;
}

export async function getRuns(baseUrl: string, token?: string): Promise<ResearchRun[]> {
  const res = await fetch(`${baseUrl}/research-runs`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function createRun(
  baseUrl: string,
  goalId: string,
  workspaceRoot = "/workspace",
  token?: string,
): Promise<string> {
  const res = await fetch(`${baseUrl}/research-runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers(token) },
    body: JSON.stringify({
      goal_id: goalId,
      workspace_root: workspaceRoot,
      config: { max_experiments: 10 },
      budget: { max_experiments: 100 },
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()).run_id;
}

export async function commandRun(baseUrl: string, runId: string, command: "start" | "pause" | "resume" | "cancel", token?: string) {
  const res = await fetch(`${baseUrl}/research-runs/${runId}/${command}`, {
    method: "POST",
    headers: headers(token),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTimeline(baseUrl: string, runId: string, token?: string): Promise<TimelineEvent[]> {
  const res = await fetch(`${baseUrl}/research-runs/${runId}/timeline`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getWorldState(baseUrl: string, runId: string, token?: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${baseUrl}/research-runs/${runId}/world-state`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getExperimentRun(baseUrl: string, experimentRunId: string, token?: string): Promise<ExperimentRun> {
  const res = await fetch(`${baseUrl}/experiment-runs/${experimentRunId}`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getArtifacts(baseUrl: string, experimentRunId: string, token?: string): Promise<Record<string, unknown>[]> {
  const res = await fetch(`${baseUrl}/experiment-runs/${experimentRunId}/artifacts`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTraces(baseUrl: string, runId: string, token?: string): Promise<AgentTrace[]> {
  const res = await fetch(`${baseUrl}/agent-traces/${runId}`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getScores(baseUrl: string, runId: string, token?: string): Promise<EvaluatorScore[]> {
  const res = await fetch(`${baseUrl}/evaluator-scores/${runId}`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTools(baseUrl: string, token?: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${baseUrl}/tools/registry`, { headers: headers(token) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
