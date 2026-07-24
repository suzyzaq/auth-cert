import { useMemo, useState } from "react";
import { MetricCard } from "../components/MetricCard.js";
import {
  categoryLabels,
  filterRules,
  inspectionRules,
  severityLabels,
  type InspectionRule,
  type RuleCategory,
  type RuleSeverity,
} from "../features/rules/rule-catalog.js";

const categories: Array<RuleCategory | "ALL"> = [
  "ALL",
  "AVAILABILITY",
  "FRESHNESS",
  "CONSISTENCY",
  "FIELD",
  "BUSINESS",
  "EVIDENCE",
];

const severities: Array<RuleSeverity | "ALL"> = [
  "ALL",
  "CRITICAL",
  "HIGH",
  "MEDIUM",
  "INFO",
];

function RuleDetail({ rule }: { rule: InspectionRule }) {
  return (
    <article className="rule-detail">
      <header>
        <div>
          <span>{rule.code}</span>
          <h2>{rule.name}</h2>
        </div>
        <b className={`rule-severity severity-${rule.severity.toLowerCase()}`}>
          {severityLabels[rule.severity]}
        </b>
      </header>
      <p className="rule-description">{rule.description}</p>
      <dl className="rule-facts">
        <div>
          <dt>规则分类</dt>
          <dd>{categoryLabels[rule.category]}</dd>
        </div>
        <div>
          <dt>运行状态</dt>
          <dd className={rule.enabled ? "enabled-copy" : "disabled-copy"}>
            {rule.enabled ? "已启用" : "已停用"}
          </dd>
        </div>
        <div>
          <dt>最近命中</dt>
          <dd>{rule.hitCount} 条</dd>
        </div>
        <div>
          <dt>最近运行</dt>
          <dd>{rule.lastRunAt}</dd>
        </div>
      </dl>
      <section className="rule-condition">
        <span>TRIGGER / 触发条件</span>
        <strong>{rule.condition}</strong>
      </section>
      <section className="rule-fields">
        <span>INSPECTED FIELDS / 校验字段</span>
        <div>
          {rule.fields.map((field) => (
            <code key={field}>{field}</code>
          ))}
        </div>
      </section>
      <footer>
        <span className="pulse" />
        当前为已发布规则的只读视图，调整后需管理员二次确认
      </footer>
    </article>
  );
}

export function RulesCenterPage() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<RuleCategory | "ALL">("ALL");
  const [severity, setSeverity] = useState<RuleSeverity | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState(inspectionRules[0]!.id);

  const rules = useMemo(
    () => filterRules(inspectionRules, { query, category, severity }),
    [query, category, severity],
  );
  const selectedRule =
    rules.find((rule) => rule.id === selectedId) ?? rules[0] ?? null;
  const criticalCount = inspectionRules.filter(
    (rule) => rule.severity === "CRITICAL",
  ).length;
  const enabledCount = inspectionRules.filter((rule) => rule.enabled).length;

  return (
    <div className="workspace-page rules-page">
      <section className="page-heading rules-heading">
        <div>
          <div className="eyebrow">RULE GOVERNANCE / 规则治理</div>
          <h1>
            巡检规则
            <span>控制中心</span>
          </h1>
        </div>
        <a
          className="source-database-card"
          href="https://suzyzaq.github.io/auth-cert-db/"
          target="_blank"
          rel="noopener noreferrer"
        >
          <span>PUBLIC DATA SOURCE</span>
          <b>授权资质数据库</b>
          <small>打开公开查询页 ↗</small>
        </a>
      </section>

      <section className="metric-grid" aria-label="规则指标">
        <MetricCard label="规则总数" value={String(inspectionRules.length)} note="覆盖六类巡检" />
        <MetricCard label="当前启用" value={String(enabledCount)} note="全部正常运行" tone="acid" />
        <MetricCard label="严重规则" value={String(criticalCount)} note="异常立即进入复核" tone="critical" />
        <MetricCard label="待调整" value="0" note="无未发布变更" />
      </section>

      <section className="rules-workspace">
        <aside className="rules-filter">
          <div className="rail-kicker">RULE FILTER / 规则筛选</div>
          <label className="rules-search">
            <span>搜索规则</span>
            <input
              aria-label="搜索规则"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="名称、编码、字段或条件"
            />
          </label>
          <section>
            <h2>规则分类</h2>
            <div className="filter-stack">
              {categories.map((value) => (
                <button
                  className={category === value ? "active" : ""}
                  key={value}
                  type="button"
                  onClick={() => setCategory(value)}
                >
                  <span>{value === "ALL" ? "全部分类" : categoryLabels[value]}</span>
                  <b>
                    {value === "ALL"
                      ? inspectionRules.length
                      : inspectionRules.filter((rule) => rule.category === value)
                          .length}
                  </b>
                </button>
              ))}
            </div>
          </section>
          <section>
            <h2>风险等级</h2>
            <div className="rule-severity-filters">
              {severities.map((value) => (
                <button
                  className={severity === value ? "active" : ""}
                  key={value}
                  type="button"
                  onClick={() => setSeverity(value)}
                >
                  {value === "ALL" ? "全部" : severityLabels[value]}
                </button>
              ))}
            </div>
          </section>
        </aside>

        <div className="rules-list-panel">
          <header>
            <div>
              <span className="stage-index">02</span>
              <div>
                <b>已发布规则</b>
                <small>当前显示 {rules.length} 条</small>
              </div>
            </div>
            <span className="readonly-flag">只读发布视图</span>
          </header>
          <div className="rule-list">
            {rules.map((rule) => (
              <button
                className={`rule-list-item ${
                  selectedRule?.id === rule.id ? "active" : ""
                }`}
                key={rule.id}
                type="button"
                onClick={() => setSelectedId(rule.id)}
              >
                <span className={`rule-code severity-${rule.severity.toLowerCase()}`}>
                  {rule.code}
                </span>
                <span className="rule-list-copy">
                  <b>{rule.name}</b>
                  <small>{categoryLabels[rule.category]}</small>
                </span>
                <span className="rule-hit">{rule.hitCount}</span>
              </button>
            ))}
            {rules.length === 0 && (
              <div className="rules-empty">
                <b>没有符合条件的规则</b>
                <span>调整分类、风险等级或搜索关键词</span>
              </div>
            )}
          </div>
        </div>

        {selectedRule ? (
          <RuleDetail rule={selectedRule} />
        ) : (
          <article className="rule-detail rule-detail-empty">请选择一条规则</article>
        )}
      </section>
    </div>
  );
}

