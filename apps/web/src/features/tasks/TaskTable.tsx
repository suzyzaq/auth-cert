import { Link } from "react-router-dom";
import { StatusBadge } from "../../components/StatusBadge.js";
import type { InspectionTask } from "../../types.js";

export function TaskTable({ tasks }: { tasks: InspectionTask[] }) {
  return (
    <div className="task-table-wrap">
      <table className="task-table">
        <thead>
          <tr>
            <th>风险</th>
            <th>品牌 / 记录</th>
            <th>异常</th>
            <th>处理状态</th>
            <th>负责人</th>
            <th>更新时间</th>
            <th aria-label="操作" />
          </tr>
        </thead>
        <tbody>
          {tasks.map((task) => (
            <tr key={task.id}>
              <td>
                <StatusBadge risk={task.risk} />
              </td>
              <td>
                <div className="task-identity">
                  <strong>{task.brand}</strong>
                  <span>{task.name}</span>
                  <code>{task.code}</code>
                </div>
              </td>
              <td>
                <b className={task.issueCount ? "issue-count" : "issue-zero"}>
                  {task.issueCount} 项异常
                </b>
              </td>
              <td>
                {task.status === "REVIEW_REQUIRED" ? "待人工复核" : "复核完成"}
              </td>
              <td>{task.assignee}</td>
              <td>{task.updatedAt}</td>
              <td>
                <Link className="row-action" to={`/tasks/${task.id}`}>
                  查看证据 <span>↗</span>
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {tasks.length === 0 && (
        <div className="empty-state">
          <b>没有符合条件的任务</b>
          <span>调整左侧筛选条件后重试</span>
        </div>
      )}
    </div>
  );
}
