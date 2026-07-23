import { Link, useParams } from "react-router-dom";
import { demoTasks } from "../data.js";

export function EvidenceReviewPage() {
  const { id } = useParams();
  const task = demoTasks.find((item) => item.id === id) ?? demoTasks[0]!;
  const isHoyo = task.id === "task-hoyo";

  return (
    <div className="review-page">
      <header className="review-header">
        <div>
          <Link to="/">← 返回任务中心</Link>
          <div className="eyebrow">EVIDENCE REVIEW / 证据复核</div>
          <h1>{task.brand}</h1>
          <p>{task.name} · {task.code}</p>
        </div>
        <div className="review-actions">
          <button type="button" className="secondary-action">退回重解析</button>
          <button type="button" className="primary-action">确认复核结果</button>
        </div>
      </header>
      <section className="review-workspace">
        <article className="document-panel">
          <header>
            <b>原始附件</b>
            <span>第 1 / 1 页</span>
          </header>
          <div className="document-sheet">
            <div className="certificate-seal">资质<br />证据</div>
            <span className="document-number">第 48623859 号</span>
            <h2>{isHoyo ? "授权书" : "商标注册证"}</h2>
            <strong>{task.brand}</strong>
            <p>注册人 / 授权方：示例企业主体有限公司</p>
            <p className="evidence-highlight">
              {isHoyo
                ? "授权期限至 2026年12月31日止"
                : "注册日期 2022年09月07日　有效期至 2032年09月06日"}
            </p>
            <small>系统已定位字段证据，请结合附件原图复核。</small>
          </div>
        </article>
        <article className="comparison-panel">
          <header>
            <div>
              <span>FIELD COMPARISON</span>
              <h2>字段重建与纠错</h2>
            </div>
            <b>{isHoyo ? "无异常" : `${task.issueCount} 项异常`}</b>
          </header>
          <div className="confidence-strip">
            <span>附件解析置信度</span>
            <i><b style={{ width: "96%" }} /></i>
            <strong>96%</strong>
          </div>
          {(isHoyo
            ? [
                ["生效日期", "空", "保持为空", "附件未明确开始日期"],
                ["失效日期", "2026-12-31", "2026-12-31", "附件明确记载"],
              ]
            : [
                ["生效日期", "2032-09-07", "2022-09-07", "附件日期与现值不一致"],
                ["失效日期", "2022-09-06", "2032-09-06", "附件日期与现值不一致"],
                ["证书主体", "杭州白贝壳实业股份有限公司", "保持原值", "附件一致"],
              ]
          ).map(([label, source, proposed, reason]) => (
            <section className="field-compare" key={label}>
              <header>
                <b>{label}</b>
                <span>{source === proposed || proposed === "保持原值" ? "一致" : "建议修正"}</span>
              </header>
              <div>
                <label>数据库现值<strong>{source}</strong></label>
                <i>→</i>
                <label>附件重建值<strong>{proposed}</strong></label>
              </div>
              <p>{reason}</p>
            </section>
          ))}
          <label className="review-note">
            复核说明
            <textarea defaultValue={isHoyo ? "附件未明确生效日期，按规则保持为空。" : "原始证书日期清晰，建议修正生效与失效日期。"} />
          </label>
        </article>
      </section>
    </div>
  );
}
