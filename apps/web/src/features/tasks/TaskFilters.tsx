import type { Risk } from "../../types.js";

export type RiskFilter = Risk | "ALL";

const riskOptions: Array<{ value: RiskFilter; label: string; count: number }> = [
  { value: "ALL", label: "全部任务", count: 286 },
  { value: "CRITICAL", label: "严重", count: 12 },
  { value: "HIGH", label: "高风险", count: 35 },
  { value: "MEDIUM", label: "待复核", count: 47 },
  { value: "LOW", label: "正常", count: 192 },
];

export function TaskFilters({
  activeRisk,
  onRiskChange,
}: {
  activeRisk: RiskFilter;
  onRiskChange: (value: RiskFilter) => void;
}) {
  return (
    <aside className="filter-rail">
      <div className="rail-kicker">FILTER / 筛选</div>
      <section>
        <h2>风险等级</h2>
        <div className="filter-stack">
          {riskOptions.map((option) => (
            <button
              type="button"
              className={activeRisk === option.value ? "active" : ""}
              key={option.value}
              onClick={() => onRiskChange(option.value)}
            >
              <span>{option.label}</span>
              <b>{option.count}</b>
            </button>
          ))}
        </div>
      </section>
      <section>
        <h2>异常字段</h2>
        <div className="chip-cloud">
          <button type="button">日期</button>
          <button type="button">主体</button>
          <button type="button">授权链</button>
          <button type="button">品牌</button>
          <button type="button">品类</button>
          <button type="button">区域</button>
          <button type="button">项目</button>
        </div>
      </section>
      <section className="rail-health">
        <div>
          <span className="pulse" />
          <b>数据源正常</b>
        </div>
        <small>12 个分片 · 13:59 更新</small>
      </section>
    </aside>
  );
}
