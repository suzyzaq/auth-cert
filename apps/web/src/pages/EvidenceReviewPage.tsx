import { Link, useParams } from "react-router-dom";
import { demoReviews, demoTasks } from "../data.js";
import type { ReviewComparison } from "../types.js";

const statusLabels: Record<ReviewComparison["comparisonStatus"], string> = {
  CONSISTENT: "一致",
  SOURCE_FIELD_ERROR: "建议修正",
  SOURCE_FIELD_MISSING: "建议补充",
  ATTACHMENT_FIELD_MISSING: "附件未明确",
  ATTACHMENT_UNCLEAR: "附件不清晰",
  ATTACHMENT_CONFLICT: "附件冲突",
  SKILL_MATCH_UNCERTAIN: "匹配待确认",
  CHAIN_INCOMPLETE: "授权链不完整",
  MANUAL_REVIEW_REQUIRED: "需要人工复核",
};

function displayValue(value: string | null): string {
  return value === null || value === "" ? "未明确" : value;
}

function ComparisonCard({ item }: { item: ReviewComparison }) {
  const isConsistent = item.comparisonStatus === "CONSISTENT";
  return (
    <section className={`field-compare ${isConsistent ? "is-consistent" : "has-risk"}`}>
      <header>
        <div>
          <b>{item.label}</b>
          <code>{item.field}</code>
        </div>
        <span>{statusLabels[item.comparisonStatus]}</span>
      </header>
      <div>
        <label>
          数据库原值
          <strong>{displayValue(item.sourceValue)}</strong>
        </label>
        <i>→</i>
        <label>
          附件重建值
          <strong>{displayValue(item.attachmentValue)}</strong>
        </label>
      </div>
      <footer className="field-evidence">
        <span>
          {item.evidencePage ? `附件第 ${item.evidencePage} 页` : "附件未定位页码"}
        </span>
        <q>{item.evidenceText}</q>
        <b>{Math.round(item.confidence * 100)}%</b>
      </footer>
    </section>
  );
}

export function EvidenceReviewPage() {
  const { id } = useParams();
  const task = demoTasks.find((item) => item.id === id) ?? demoTasks[0]!;
  const review = demoReviews[task.id] ?? demoReviews["task-babycare"]!;
  const issueCount = review.comparisons.filter(
    (item) => item.comparisonStatus !== "CONSISTENT",
  ).length;

  return (
    <div className="review-page">
      <header className="review-header">
        <div>
          <Link to="/">← 返回任务中心</Link>
          <div className="eyebrow">EVIDENCE REVIEW / 附件证据复核</div>
          <h1>{task.brand}</h1>
          <p>{task.name} · {task.code}</p>
        </div>
        <div className="review-actions">
          <span className="readonly-flag">只读巡检 · 回写已关闭</span>
          <button type="button" className="secondary-action">退回重解析</button>
          <button type="button" className="primary-action">确认复核结果</button>
        </div>
      </header>

      <section className="review-summary" aria-label="巡检摘要">
        <div><span>附件识别</span><b>{Math.round(review.overallConfidence * 100)}%</b></div>
        <div><span>差异字段</span><b>{issueCount}</b></div>
        <div><span>自动修正</span><b>{review.canAutoCorrect ? "允许" : "禁止"}</b></div>
        <p>{review.manualReviewReasons.join("；")}</p>
      </section>

      <section className="review-workspace">
        <article className="document-panel">
          <header>
            <b>原始附件证据</b>
            <span>共 {review.attachmentPages} 页</span>
          </header>
          <div className="document-sheet">
            <div className="certificate-seal">附件<br />证据</div>
            <span className="document-number">{review.documentNumber}</span>
            <h2>{review.attachmentTitle}</h2>
            <strong>{task.brand}</strong>
            {review.documentBody.map((line, index) => (
              <p className={index > 0 ? "evidence-highlight" : ""} key={line}>
                {line}
              </p>
            ))}
            <small>页面摘录仅用于定位，最终结论应结合附件原图确认。</small>
          </div>
        </article>

        <article className="comparison-panel">
          <header>
            <div>
              <span>FIELD RECONCILIATION</span>
              <h2>字段重建与核对</h2>
            </div>
            <b>{issueCount} 项待处理</b>
          </header>
          <div className="confidence-strip">
            <span>附件解析置信度</span>
            <i><b style={{ width: `${review.overallConfidence * 100}%` }} /></i>
            <strong>{Math.round(review.overallConfidence * 100)}%</strong>
          </div>
          {review.comparisons.map((item) => (
            <ComparisonCard item={item} key={item.field} />
          ))}
          <label className="review-note">
            复核说明
            <textarea defaultValue={review.manualReviewReasons.join("；")} />
          </label>
        </article>
      </section>
    </div>
  );
}
