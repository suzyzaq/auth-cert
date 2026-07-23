import type { Risk } from "../types.js";

const labels: Record<Risk, string> = {
  CRITICAL: "严重",
  HIGH: "高风险",
  MEDIUM: "待复核",
  LOW: "正常",
};

export function StatusBadge({ risk }: { risk: Risk }) {
  return (
    <span
      className={`status-badge status-${risk.toLowerCase()}`}
      aria-label={`风险等级：${labels[risk]}`}
    >
      <span aria-hidden="true" className="status-dot" />
      {labels[risk]}
    </span>
  );
}
