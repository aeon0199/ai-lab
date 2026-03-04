import { EvaluatorScore } from "../types";

type Props = {
  scores: EvaluatorScore[];
};

export function ScoreChart({ scores }: Props) {
  if (!scores.length) {
    return <div className="empty">No evaluator data yet.</div>;
  }

  const width = 480;
  const height = 180;
  const pad = 20;
  const points = scores.map((score, i) => {
    const x = pad + (i / Math.max(1, scores.length - 1)) * (width - pad * 2);
    const y = height - pad - score.goal_progress * (height - pad * 2);
    return { x, y };
  });

  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");

  return (
    <div className="chart-shell">
      <svg viewBox={`0 0 ${width} ${height}`} className="chart-svg" role="img" aria-label="Goal progress over time">
        <defs>
          <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#14b8a6" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width={width} height={height} rx="12" fill="rgba(255,255,255,0.02)" />
        <path d={d} stroke="url(#lineGrad)" strokeWidth="3" fill="none" />
      </svg>
    </div>
  );
}
