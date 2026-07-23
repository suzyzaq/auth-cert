import type { ExtractedField } from "@auth-inspection/integrations/parsing";

type Rule = {
  name: string;
  labels: string[];
  transform?: (value: string) => string | null;
};

const clean = (value: string): string =>
  value.replace(/^[：:\s]+/, "").replace(/\s+$/, "").trim();

const normalizeDate = (value: string): string | null => {
  const match = value.match(/(\d{4})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})\s*日?/);
  if (!match) return null;
  return `${match[1]}-${match[2]!.padStart(2, "0")}-${match[3]!.padStart(2, "0")}`;
};

const rules: Rule[] = [
  { name: "authorizationCode", labels: ["授权编号", "授权书编号", "授权编码"] },
  { name: "grantor", labels: ["授权方", "授权人", "品牌方"] },
  { name: "grantees", labels: ["被授权方", "被授权人", "受权方"] },
  { name: "brand", labels: ["授权品牌", "品牌名称", "品牌"] },
  { name: "category", labels: ["授权品类", "授权类别", "产品品类"] },
  { name: "region", labels: ["授权区域", "销售区域", "授权范围"] },
  {
    name: "authorizationLevel",
    labels: ["授权级别", "授权层级"],
    transform: (value) => value.match(/(\d+)\s*级/)?.[1] ?? null,
  },
  { name: "projectName", labels: ["项目名称", "授权项目"] },
  {
    name: "transferAllowed",
    labels: ["允许转授权", "是否允许转授权", "可否转授权"],
    transform: (value) =>
      /^(是|允许|可以|可)$/.test(value)
        ? "是"
        : /^(否|不允许|不可)$/.test(value)
          ? "否"
          : null,
  },
];

function fieldFromLine(
  source: ExtractedField,
  name: string,
  value: string,
  evidenceText: string,
): ExtractedField {
  return {
    name,
    value,
    confidence: source.confidence,
    method: "RULE",
    ...(source.page === undefined ? {} : { page: source.page }),
    evidenceText,
    validationStatus: "SINGLE_SOURCE",
  };
}

export function extractAuthorizationFields(
  sourceFields: ExtractedField[],
): ExtractedField[] {
  const extracted: ExtractedField[] = [];
  const seen = new Set<string>();

  for (const source of sourceFields.filter(
    (item) => item.name === "documentText" && item.value,
  )) {
    const lines = source.value!.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    for (const line of lines) {
      for (const rule of rules) {
        if (seen.has(rule.name)) continue;
        const label = rule.labels.find((item) =>
          new RegExp(`^${item}\\s*[：:]`).test(line),
        );
        if (!label) continue;
        const raw = clean(line.slice(label.length));
        const value = rule.transform ? rule.transform(raw) : raw;
        if (!value) continue;
        extracted.push(fieldFromLine(source, rule.name, value, line));
        seen.add(rule.name);
      }
    }

    const periodLine = lines.find((line) =>
      /^(有效期|授权期限)\s*[：:]/.test(line),
    );
    if (periodLine) {
      const dates = [...periodLine.matchAll(/(\d{4}\s*[年./-]\s*\d{1,2}\s*[月./-]\s*\d{1,2}\s*日?)/g)]
        .map((match) => normalizeDate(match[1]!))
        .filter((value): value is string => value !== null);
      if (dates[0] && !seen.has("effectiveDate")) {
        extracted.push(fieldFromLine(source, "effectiveDate", dates[0], periodLine));
        seen.add("effectiveDate");
      }
      if (dates[1] && !seen.has("expiryDate")) {
        extracted.push(fieldFromLine(source, "expiryDate", dates[1], periodLine));
        seen.add("expiryDate");
      }
    }
  }

  const project = extracted.find((item) => item.name === "projectName");
  if (project && !seen.has("isProjectAuthorization")) {
    extracted.push(
      fieldFromLine(
        project,
        "isProjectAuthorization",
        "是",
        project.evidenceText ?? project.value ?? "",
      ),
    );
  }
  return extracted;
}
