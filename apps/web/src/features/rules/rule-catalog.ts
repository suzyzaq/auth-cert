export type RuleCategory =
  | "AVAILABILITY"
  | "FRESHNESS"
  | "CONSISTENCY"
  | "FIELD"
  | "BUSINESS"
  | "EVIDENCE";

export type RuleSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "INFO";

export interface InspectionRule {
  id: string;
  code: string;
  name: string;
  category: RuleCategory;
  description: string;
  severity: RuleSeverity;
  enabled: boolean;
  fields: string[];
  condition: string;
  hitCount: number;
  lastRunAt: string;
}

export interface RuleFilters {
  category: RuleCategory | "ALL";
  severity: RuleSeverity | "ALL";
  query: string;
}

export const categoryLabels: Record<RuleCategory, string> = {
  AVAILABILITY: "接口可用性",
  FRESHNESS: "数据新鲜度",
  CONSISTENCY: "索引一致性",
  FIELD: "字段完整性",
  BUSINESS: "业务逻辑",
  EVIDENCE: "证据贯通",
};

export const severityLabels: Record<RuleSeverity, string> = {
  CRITICAL: "严重",
  HIGH: "高风险",
  MEDIUM: "需关注",
  INFO: "提示",
};

export const inspectionRules: InspectionRule[] = [
  {
    id: "source-http",
    code: "SRC-001",
    name: "索引与分片可用性",
    category: "AVAILABILITY",
    description: "所有已声明文件必须返回 200，并且响应内容能够解析为 JSON。",
    severity: "CRITICAL",
    enabled: true,
    fields: ["index.json", "shard/{0..11}.json"],
    condition: "HTTP 状态不为 200，或 JSON 解析失败",
    hitCount: 0,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "boundary-shard",
    code: "SRC-002",
    name: "边界分片探测",
    category: "AVAILABILITY",
    description: "索引声明范围之外的第一个分片必须返回 404。",
    severity: "HIGH",
    enabled: true,
    fields: ["shardCount"],
    condition: "shard/{shardCount}.json 状态不是 404",
    hitCount: 0,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "source-freshness",
    code: "FRE-001",
    name: "源站更新时间",
    category: "FRESHNESS",
    description: "OSS 源站应为当天或前一工作日数据。",
    severity: "HIGH",
    enabled: true,
    fields: ["today", "generated"],
    condition: "源站更新时间超过一个工作日",
    hitCount: 0,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "cdn-freshness",
    code: "FRE-002",
    name: "CDN 滞后上限",
    category: "FRESHNESS",
    description: "备用 CDN 相对 OSS 源站最多允许滞后两天。",
    severity: "MEDIUM",
    enabled: true,
    fields: ["today"],
    condition: "CDN today 早于 OSS today 两天以上",
    hitCount: 0,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "index-count",
    code: "CON-001",
    name: "索引数量一致性",
    category: "CONSISTENCY",
    description: "品牌数量和分片数量必须与实际加载结果一致。",
    severity: "CRITICAL",
    enabled: true,
    fields: ["brandCount", "shardCount", "brands"],
    condition: "声明数量与实际键数或实际分片数不一致",
    hitCount: 0,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "auth-required-fields",
    code: "FLD-001",
    name: "授权字段完整性",
    category: "FIELD",
    description: "授权记录必须包含清单规定的全部基础字段。",
    severity: "HIGH",
    enabled: true,
    fields: [
      "code",
      "name",
      "type",
      "level",
      "grant",
      "authed",
      "enable",
      "disable",
      "flag",
      "flagText",
      "files",
    ],
    condition: "必填字段缺失，或字段类型不符合约定",
    hitCount: 11,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "date-order",
    code: "FLD-002",
    name: "授权日期顺序",
    category: "FIELD",
    description: "生效日期不得晚于失效日期，并与附件证据保持一致。",
    severity: "CRITICAL",
    enabled: true,
    fields: ["enable", "disable"],
    condition: "生效日期晚于失效日期，或与附件日期冲突",
    hitCount: 3,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "authorization-chain",
    code: "BUS-001",
    name: "授权链合理性",
    category: "BUSINESS",
    description: "授权方、被授权方和层级关系需形成可解释的授权链。",
    severity: "HIGH",
    enabled: true,
    fields: ["level", "grant", "authed"],
    condition: "主体重复、链路中断或层级证据不足",
    hitCount: 18,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "low-confidence-review",
    code: "BUS-002",
    name: "低置信度强制复核",
    category: "BUSINESS",
    description: "品牌或品类匹配置信度不足时，不允许进入自动回写。",
    severity: "CRITICAL",
    enabled: true,
    fields: ["brand", "category", "confidence"],
    condition: "匹配置信度低于发布阈值",
    hitCount: 47,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "brand-evidence",
    code: "EVI-001",
    name: "品牌证据贯通",
    category: "EVIDENCE",
    description: "品牌必须定位到正确分片，且授权或资质记录至少一类非空。",
    severity: "HIGH",
    enabled: true,
    fields: ["brand", "shard", "auth", "cert", "files"],
    condition: "品牌无法定位、记录全空或附件不可访问",
    hitCount: 6,
    lastRunAt: "2026-07-23 17:30",
  },
  {
    id: "attachment-fact-priority",
    code: "EVI-002",
    name: "附件事实优先",
    category: "EVIDENCE",
    description:
      "清晰完整的授权附件是字段重建的第一事实源，数据库原值只用于比对，不能覆盖附件中的明确事实。",
    severity: "CRITICAL",
    enabled: true,
    fields: ["source_value", "attachment_value", "corrected_value"],
    condition:
      "附件有明确证据且与数据库冲突时输出 SOURCE_FIELD_ERROR；附件未明确时输出 ATTACHMENT_FIELD_MISSING",
    hitCount: 0,
    lastRunAt: "2026-07-23 18:00",
  },
  {
    id: "comparison-status",
    code: "EVI-003",
    name: "九类字段比对状态",
    category: "EVIDENCE",
    description:
      "每个字段必须落入一致、现存错误、现存缺失、附件缺失、附件模糊、附件冲突、匹配不确定、授权链不完整或人工复核之一。",
    severity: "HIGH",
    enabled: true,
    fields: [
      "CONSISTENT",
      "SOURCE_FIELD_ERROR",
      "SOURCE_FIELD_MISSING",
      "ATTACHMENT_FIELD_MISSING",
      "ATTACHMENT_UNCLEAR",
      "ATTACHMENT_CONFLICT",
      "SKILL_MATCH_UNCERTAIN",
      "CHAIN_INCOMPLETE",
      "MANUAL_REVIEW_REQUIRED",
    ],
    condition: "字段没有比较状态，或缺少页码、原文摘录和置信度",
    hitCount: 0,
    lastRunAt: "2026-07-23 18:00",
  },
  {
    id: "automatic-correction-gate",
    code: "BUS-003",
    name: "自动纠错准入门槛",
    category: "BUSINESS",
    description:
      "仅在附件清晰、无冲突、主体明确、授权链满足字段要求，并且品牌不低于 0.90、品类不低于 0.85 时给出自动纠错资格。",
    severity: "CRITICAL",
    enabled: true,
    fields: ["can_auto_correct", "brand_confidence", "category_confidence"],
    condition:
      "存在编码、品牌、主体、附件或授权链冲突；或品牌不低于 0.90、品类不低于 0.85 的条件未满足",
    hitCount: 0,
    lastRunAt: "2026-07-23 18:00",
  },
  {
    id: "critical-error-codes",
    code: "BUS-004",
    name: "关键错误编码分流",
    category: "BUSINESS",
    description:
      "严重冲突必须使用统一错误编码进入人工复核，避免附件挂错记录后继续流转。",
    severity: "CRITICAL",
    enabled: true,
    fields: [
      "AUTHORIZATION_CODE_MISMATCH",
      "BRAND_MISMATCH",
      "CATEGORY_SCOPE_OVERSTATED",
      "REGION_SCOPE_OVERSTATED",
      "AUTHORIZATION_CHAIN_INCOMPLETE",
      "MULTIPLE_ATTACHMENTS_CONFLICT",
    ],
    condition:
      "AUTHORIZATION_CODE_MISMATCH 或其他严重错误出现时，禁止自动回写并创建人工复核任务",
    hitCount: 0,
    lastRunAt: "2026-07-23 18:00",
  },
];

export function filterRules(
  rules: InspectionRule[],
  filters: RuleFilters,
): InspectionRule[] {
  const query = filters.query.trim().toLocaleLowerCase("zh-CN");
  return rules.filter((rule) => {
    if (filters.category !== "ALL" && rule.category !== filters.category) {
      return false;
    }
    if (filters.severity !== "ALL" && rule.severity !== filters.severity) {
      return false;
    }
    if (!query) return true;
    return [
      rule.name,
      rule.code,
      rule.description,
      rule.condition,
      ...rule.fields,
    ]
      .join(" ")
      .toLocaleLowerCase("zh-CN")
      .includes(query);
  });
}
