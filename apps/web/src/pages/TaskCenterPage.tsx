import { MetricCard } from "../components/MetricCard.js";
import { TaskFilters, type RiskFilter } from "../features/tasks/TaskFilters.js";
import { TaskTable } from "../features/tasks/TaskTable.js";
import type { InspectionTask } from "../types.js";

export function TaskCenterPage({
  tasks,
  loading,
  activeRisk,
  onRiskChange,
}: {
  tasks: InspectionTask[];
  loading: boolean;
  activeRisk: RiskFilter;
  onRiskChange: (value: RiskFilter) => void;
}) {
  return (
    <div className="workspace-page">
      <section className="page-heading">
        <div>
          <div className="eyebrow">INSPECTION OPERATIONS / 巡检作业</div>
          <h1>
            授权任务
            <span>处理中心</span>
          </h1>
        </div>
        <div className="heading-actions">
          <button type="button" className="secondary-action">
            导出巡检结果
          </button>
          <button type="button" className="primary-action">
            ＋ 发起专项巡检
          </button>
        </div>
      </section>

      <section className="metric-grid" aria-label="巡检指标">
        <MetricCard label="待巡检" value="286" note="今日新增 38" />
        <MetricCard label="待复核" value="47" note="较昨日减少 8" tone="acid" />
        <MetricCard label="严重异常" value="12" note="需优先处理" tone="critical" />
        <MetricCard label="待回写" value="12" note="等待管理员确认" />
      </section>

      <section className="operations-panel">
        <TaskFilters activeRisk={activeRisk} onRiskChange={onRiskChange} />
        <div className="task-stage">
          <header className="stage-toolbar">
            <div>
              <span className="stage-index">01</span>
              <div>
                <b>待处理任务</b>
                <small>{loading ? "正在加载…" : `共 ${tasks.length} 条`}</small>
              </div>
            </div>
            <label className="search-box">
              <span>⌕</span>
              <input aria-label="搜索任务" placeholder="搜索品牌、编码或授权名称" />
            </label>
          </header>
          <TaskTable tasks={tasks} />
        </div>
      </section>
    </div>
  );
}
