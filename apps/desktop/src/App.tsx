import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  commandRun,
  createGoal,
  createRun,
  getArtifacts,
  getExperimentRun,
  getGoals,
  getHealth,
  getRuns,
  getScores,
  getTimeline,
  getTools,
  getTraces,
  getWorldState,
} from "./api";
import { ScoreChart } from "./components/ScoreChart";
import { usePolling } from "./hooks/usePolling";
import { AgentTrace, EvaluatorScore, ExperimentRun, Goal, ResearchRun, TimelineEvent } from "./types";

type Tab = "Goals" | "Run Workspace" | "Experiments" | "Agent Traces" | "Tools" | "Providers" | "System";

const TABS: Tab[] = ["Goals", "Run Workspace", "Experiments", "Agent Traces", "Tools", "Providers", "System"];

const KEY_BASE_URL = "ailab.baseUrl";
const KEY_TOKEN = "ailab.token";
const KEY_PROVIDER_CFG = "ailab.providerConfig";

function wsUrl(baseUrl: string, path: string) {
  return `${baseUrl.replace("http://", "ws://").replace("https://", "wss://")}${path}`;
}

function toJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

export default function App() {
  const [tab, setTab] = useState<Tab>("Goals");
  const [baseUrl, setBaseUrl] = useState(localStorage.getItem(KEY_BASE_URL) || "http://localhost:8000");
  const [token, setToken] = useState(localStorage.getItem(KEY_TOKEN) || "");
  const [health, setHealth] = useState<{ status: string; db: string; redis: string } | null>(null);
  const [offline, setOffline] = useState(false);
  const [error, setError] = useState("");

  const [goals, setGoals] = useState<Goal[]>([]);
  const [runs, setRuns] = useState<ResearchRun[]>([]);
  const [selectedGoalId, setSelectedGoalId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");

  const [goalTitle, setGoalTitle] = useState("");
  const [goalDescription, setGoalDescription] = useState("");

  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [worldState, setWorldState] = useState<Record<string, unknown> | null>(null);
  const [traces, setTraces] = useState<AgentTrace[]>([]);
  const [scores, setScores] = useState<EvaluatorScore[]>([]);
  const [tools, setTools] = useState<Record<string, unknown>>({});

  const [selectedExperimentRunId, setSelectedExperimentRunId] = useState("");
  const [experimentRun, setExperimentRun] = useState<ExperimentRun | null>(null);
  const [artifacts, setArtifacts] = useState<Record<string, unknown>[]>([]);

  const [stackOutput, setStackOutput] = useState("");
  const [providerConfig, setProviderConfig] = useState(() => {
    const saved = localStorage.getItem(KEY_PROVIDER_CFG);
    if (saved) return JSON.parse(saved);
    return {
      openai_model: "gpt-5-mini",
      anthropic_model: "claude-sonnet-4-5",
      gemini_model: "gemini-2.5-pro",
      local_model: "llama3.1",
      local_base_url: "http://localhost:11434/v1",
    };
  });

  const selectedRun = runs.find((r) => r.id === selectedRunId) || null;

  const experimentRunIds = useMemo(() => {
    const ids = timeline
      .filter((e) => e.payload?.experiment_run_id)
      .map((e) => String(e.payload.experiment_run_id));
    return [...new Set(ids)];
  }, [timeline]);

  useEffect(() => {
    localStorage.setItem(KEY_BASE_URL, baseUrl);
  }, [baseUrl]);

  useEffect(() => {
    localStorage.setItem(KEY_TOKEN, token);
  }, [token]);

  useEffect(() => {
    localStorage.setItem(KEY_PROVIDER_CFG, JSON.stringify(providerConfig));
  }, [providerConfig]);

  usePolling(
    async () => {
      try {
        const [h, gs, rs, ts] = await Promise.all([
          getHealth(baseUrl, token || undefined),
          getGoals(baseUrl, token || undefined),
          getRuns(baseUrl, token || undefined),
          getTools(baseUrl, token || undefined),
        ]);
        setHealth(h);
        setGoals(gs);
        setRuns(rs);
        setTools(ts);
        setOffline(false);
        if (!selectedGoalId && gs[0]) setSelectedGoalId(gs[0].id);
        if (!selectedRunId && rs[0]) setSelectedRunId(rs[0].id);
      } catch (err) {
        setOffline(true);
        setError(err instanceof Error ? err.message : "Unable to reach API");
      }
    },
    4000,
    [baseUrl, token, selectedGoalId, selectedRunId],
  );

  usePolling(
    async () => {
      if (!selectedRunId) return;
      try {
        const [tl, ws, tr, sc] = await Promise.all([
          getTimeline(baseUrl, selectedRunId, token || undefined),
          getWorldState(baseUrl, selectedRunId, token || undefined),
          getTraces(baseUrl, selectedRunId, token || undefined),
          getScores(baseUrl, selectedRunId, token || undefined),
        ]);
        setTimeline(tl);
        setWorldState(ws);
        setTraces(tr);
        setScores(sc);
      } catch {
        // Keep stale state for offline-safe UX.
      }
    },
    3000,
    [baseUrl, token, selectedRunId],
  );

  useEffect(() => {
    if (!selectedRunId) return;

    const eventsSocket = new WebSocket(wsUrl(baseUrl, `/research-runs/${selectedRunId}/events`));
    const statusSocket = new WebSocket(wsUrl(baseUrl, `/research-runs/${selectedRunId}/status`));

    eventsSocket.onmessage = (evt) => {
      const data = JSON.parse(evt.data) as TimelineEvent;
      setTimeline((prev) => {
        if (prev.some((e) => e.event_id === data.event_id)) return prev;
        return [...prev, data];
      });
    };

    statusSocket.onmessage = () => {
      getRuns(baseUrl, token || undefined)
        .then((rs) => setRuns(rs))
        .catch(() => null);
    };

    const ping = setInterval(() => {
      if (eventsSocket.readyState === WebSocket.OPEN) eventsSocket.send("ping");
      if (statusSocket.readyState === WebSocket.OPEN) statusSocket.send("ping");
    }, 8000);

    return () => {
      clearInterval(ping);
      eventsSocket.close();
      statusSocket.close();
    };
  }, [baseUrl, token, selectedRunId]);

  useEffect(() => {
    if (!selectedExperimentRunId) {
      setExperimentRun(null);
      setArtifacts([]);
      return;
    }

    Promise.all([
      getExperimentRun(baseUrl, selectedExperimentRunId, token || undefined),
      getArtifacts(baseUrl, selectedExperimentRunId, token || undefined),
    ])
      .then(([er, art]) => {
        setExperimentRun(er);
        setArtifacts(art);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load experiment"));
  }, [baseUrl, token, selectedExperimentRunId]);

  async function onCreateGoal(event: FormEvent) {
    event.preventDefault();
    if (!goalTitle.trim()) return;
    try {
      const id = await createGoal(baseUrl, goalTitle.trim(), goalDescription.trim(), token || undefined);
      setGoalTitle("");
      setGoalDescription("");
      setSelectedGoalId(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Goal creation failed");
    }
  }

  async function onCreateRun(goalId: string) {
    try {
      const runId = await createRun(baseUrl, goalId, "/workspace", token || undefined);
      setSelectedRunId(runId);
      setTab("Run Workspace");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run creation failed");
    }
  }

  async function onRunCommand(command: "start" | "pause" | "resume" | "cancel") {
    if (!selectedRunId) return;
    try {
      await commandRun(baseUrl, selectedRunId, command, token || undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Command failed");
    }
  }

  async function onStack(command: "start" | "stop" | "status") {
    if (!window.aiLabDesktop) {
      setStackOutput("Desktop bridge unavailable (open in Electron, not browser preview).");
      return;
    }
    try {
      const result =
        command === "start"
          ? await window.aiLabDesktop.startStack()
          : command === "stop"
            ? await window.aiLabDesktop.stopStack()
            : await window.aiLabDesktop.stackStatus();
      setStackOutput([result.stdout, result.stderr].filter(Boolean).join("\n"));
    } catch (err) {
      setStackOutput(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="brand">
          <div className="brand-kicker">AUTONOMOUS RESEARCH</div>
          <h1>AI Lab</h1>
        </div>
        <nav>
          {TABS.map((item) => (
            <button key={item} className={`tab-btn ${item === tab ? "active" : ""}`} onClick={() => setTab(item)}>
              {item}
            </button>
          ))}
        </nav>
        <div className="connection-status">
          <div className={`pulse ${offline ? "offline" : "online"}`} />
          <span>{offline ? "Offline" : "Connected"}</span>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div className="endpoint">
            <label>API</label>
            <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="http://localhost:8000" />
          </div>
          <div className="endpoint token">
            <label>Token (optional)</label>
            <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Bearer token" />
          </div>
          <div className="chip">Health: {health?.status ?? "unknown"}</div>
        </header>

        {error ? <div className="error-banner">{error}</div> : null}

        {tab === "Goals" && (
          <section className="panel-grid">
            <article className="panel">
              <h2>Create Goal</h2>
              <form className="stack" onSubmit={onCreateGoal}>
                <input value={goalTitle} onChange={(e) => setGoalTitle(e.target.value)} placeholder="Goal title" required />
                <textarea
                  value={goalDescription}
                  onChange={(e) => setGoalDescription(e.target.value)}
                  placeholder="What should autonomous agents discover?"
                />
                <button type="submit">Create Goal</button>
              </form>
            </article>

            <article className="panel span-2">
              <h2>Goals</h2>
              <div className="table">
                <div className="row head">
                  <span>Title</span>
                  <span>Status</span>
                  <span>Action</span>
                </div>
                {goals.map((goal) => (
                  <div key={goal.id} className={`row ${selectedGoalId === goal.id ? "selected" : ""}`}>
                    <span>{goal.title}</span>
                    <span>{goal.status}</span>
                    <span className="actions">
                      <button onClick={() => setSelectedGoalId(goal.id)}>Select</button>
                      <button onClick={() => onCreateRun(goal.id)}>Create Run</button>
                    </span>
                  </div>
                ))}
                {!goals.length ? <div className="empty">No goals yet.</div> : null}
              </div>
            </article>

            <article className="panel span-3">
              <h2>Research Runs</h2>
              <div className="table">
                <div className="row head">
                  <span>Run ID</span>
                  <span>Status</span>
                  <span>Goal ID</span>
                  <span>Action</span>
                </div>
                {runs.map((run) => (
                  <div key={run.id} className={`row ${selectedRunId === run.id ? "selected" : ""}`}>
                    <span>{run.id.slice(0, 8)}...</span>
                    <span>{run.status}</span>
                    <span>{run.goal_id.slice(0, 8)}...</span>
                    <span className="actions">
                      <button onClick={() => setSelectedRunId(run.id)}>Focus</button>
                    </span>
                  </div>
                ))}
                {!runs.length ? <div className="empty">No runs yet.</div> : null}
              </div>
            </article>
          </section>
        )}

        {tab === "Run Workspace" && (
          <section className="panel-grid">
            <article className="panel span-3">
              <h2>Run Controls</h2>
              <div className="controls-row">
                <div className="chip strong">Run: {selectedRunId || "none selected"}</div>
                <div className="chip">Status: {selectedRun?.status ?? "n/a"}</div>
                <button onClick={() => onRunCommand("start")} disabled={!selectedRunId}>Start</button>
                <button onClick={() => onRunCommand("pause")} disabled={!selectedRunId}>Pause</button>
                <button onClick={() => onRunCommand("resume")} disabled={!selectedRunId}>Resume</button>
                <button onClick={() => onRunCommand("cancel")} disabled={!selectedRunId}>Cancel</button>
              </div>
            </article>

            <article className="panel span-2">
              <h2>Evaluator Trend</h2>
              <ScoreChart scores={scores} />
            </article>

            <article className="panel span-2">
              <h2>Live Timeline</h2>
              <div className="event-feed">
                {timeline.slice(-30).map((event) => (
                  <div className="event-item" key={event.event_id}>
                    <div className="mono">{event.event_type}</div>
                    <div>{new Date(event.occurred_at).toLocaleString()}</div>
                  </div>
                ))}
                {!timeline.length ? <div className="empty">No events yet.</div> : null}
              </div>
            </article>

            <article className="panel span-1">
              <h2>World State</h2>
              <pre>{worldState ? toJson(worldState) : "No world state yet."}</pre>
            </article>
          </section>
        )}

        {tab === "Experiments" && (
          <section className="panel-grid">
            <article className="panel span-1">
              <h2>Experiment Runs</h2>
              <div className="stack">
                {experimentRunIds.map((id) => (
                  <button key={id} className={selectedExperimentRunId === id ? "active-btn" : ""} onClick={() => setSelectedExperimentRunId(id)}>
                    {id.slice(0, 8)}...
                  </button>
                ))}
                {!experimentRunIds.length ? <div className="empty">No experiment runs in this timeline.</div> : null}
              </div>
            </article>

            <article className="panel span-2">
              <h2>Experiment Inspector</h2>
              {experimentRun ? (
                <div className="stack">
                  <div className="chip">Status: {experimentRun.status}</div>
                  <pre>{toJson(experimentRun)}</pre>
                </div>
              ) : (
                <div className="empty">Select an experiment run.</div>
              )}
            </article>

            <article className="panel span-3">
              <h2>Artifacts</h2>
              <pre>{artifacts.length ? toJson(artifacts) : "No artifacts yet."}</pre>
            </article>
          </section>
        )}

        {tab === "Agent Traces" && (
          <section className="panel-grid">
            <article className="panel span-3">
              <h2>Trace Explorer</h2>
              <div className="trace-list">
                {traces.slice(-80).map((trace) => (
                  <div className="trace-item" key={trace.id}>
                    <div>
                      <strong>{trace.agent_id}</strong>
                      <span className="mono"> {trace.action}</span>
                    </div>
                    <div>{trace.reasoning_summary}</div>
                    <div className="soft">{new Date(trace.created_at).toLocaleString()}</div>
                  </div>
                ))}
                {!traces.length ? <div className="empty">No traces yet.</div> : null}
              </div>
            </article>
          </section>
        )}

        {tab === "Tools" && (
          <section className="panel-grid">
            <article className="panel span-3">
              <h2>Tool Registry & Policy</h2>
              <div className="tool-grid">
                {Object.entries(tools).map(([name, config]) => (
                  <div className="tool-card" key={name}>
                    <h3>{name}</h3>
                    <pre>{toJson(config)}</pre>
                  </div>
                ))}
              </div>
            </article>
          </section>
        )}

        {tab === "Providers" && (
          <section className="panel-grid">
            <article className="panel span-3">
              <h2>Provider Config (Local Profile)</h2>
              <div className="provider-grid">
                {Object.entries(providerConfig).map(([k, v]) => (
                  <label key={k} className="stack">
                    <span>{k}</span>
                    <input
                      value={String(v)}
                      onChange={(e) =>
                        setProviderConfig((prev: Record<string, string>) => ({
                          ...prev,
                          [k]: e.target.value,
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
              <p className="soft">Stored locally in desktop preferences. API keys are never sent from this panel directly.</p>
            </article>
          </section>
        )}

        {tab === "System" && (
          <section className="panel-grid">
            <article className="panel span-1">
              <h2>Service Health</h2>
              <pre>{health ? toJson(health) : "No health data"}</pre>
            </article>
            <article className="panel span-2">
              <h2>Local Stack Controls</h2>
              <div className="controls-row">
                <button onClick={() => onStack("start")}>Start Local Stack</button>
                <button onClick={() => onStack("stop")}>Stop Local Stack</button>
                <button onClick={() => onStack("status")}>Check Status</button>
              </div>
              <pre>{stackOutput || "No command output yet."}</pre>
            </article>
          </section>
        )}
      </main>
    </div>
  );
}
