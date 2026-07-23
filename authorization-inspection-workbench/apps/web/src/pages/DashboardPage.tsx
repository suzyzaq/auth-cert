import { MetricCard } from "../components/MetricCard.js";

export function DashboardPage() {
  return (
    <div className="workspace-page">
      <section className="page-heading">
        <div>
          <div className="eyebrow">CONTROL TOWER / 管理驾驶舱</div>
          <h1>
            巡检运行
            <span>全局总览</span>
          </h1>
        </div>
        <div className="source-status-card">
          <span>API STATUS</span>
          <strong>✓</strong>
          <b>数据源已连接</b>
          <small>2026-07-23 13:59:18</small>
        </div>
      </section>
      <section className="metric-grid">
        <MetricCard label="品牌" value="4,249" note="索引一致" tone="acid" />
        <MetricCard label="授权记录" value="5,066" note="11 条缺生效日期" />
        <MetricCard label="资质证书" value="4,816" note="3 条日期倒置" tone="critical" />
        <MetricCard label="附件" value="11,374" note="抽检可用率 100%" />
      </section>
      <section className="dashboard-grid">
        <article className="chart-card">
          <header>
            <div>
              <span>RISK DISTRIBUTION</span>
              <h2>异常风险分布</h2>
            </div>
            <b>本周</b>
          </header>
          <div className="bars">
            <div><span>日期异常</span><i style={{ width: "84%" }} /><b>38</b></div>
            <div><span>品类为空</span><i style={{ width: "68%" }} /><b>233</b></div>
            <div><span>授权链</span><i style={{ width: "46%" }} /><b>18</b></div>
            <div><span>附件异常</span><i style={{ width: "22%" }} /><b>6</b></div>
          </div>
        </article>
        <article className="pipeline-card">
          <span>PIPELINE</span>
          <h2>今日处理链路</h2>
          {[
            ["增量同步", "完成", "38"],
            ["附件解析", "进行中", "31 / 38"],
            ["字段巡检", "进行中", "24 / 38"],
            ["人工复核", "等待", "12"],
          ].map(([name, status, value], index) => (
            <div className="pipeline-row" key={name}>
              <em>{String(index + 1).padStart(2, "0")}</em>
              <b>{name}</b>
              <span>{status}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </article>
      </section>
    </div>
  );
}
