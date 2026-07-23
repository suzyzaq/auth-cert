import { describe, expect, it } from "vitest";
import { extractAuthorizationFields } from "./authorization-field-extractor.js";

describe("extractAuthorizationFields", () => {
  it("extracts labeled authorization fields with page evidence", () => {
    const fields = extractAuthorizationFields([
      {
        name: "documentText",
        value: [
          "授权书",
          "授权编号：AUTH-2026-001",
          "授权方：甲品牌有限公司",
          "被授权方：乙供应链有限公司",
          "授权品牌：欧菲斯、示例牌",
          "授权品类：办公用品；劳保用品",
          "授权区域：浙江省",
          "授权级别：2级",
          "有效期：2026年1月2日至2026年12月31日",
          "项目名称：某某采购项目",
          "允许转授权：否",
        ].join("\n"),
        confidence: 0.93,
        method: "OCR",
        page: 2,
        evidenceText: "授权书正文",
        validationStatus: "SINGLE_SOURCE",
      },
    ]);

    expect(fields).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          name: "authorizationCode",
          value: "AUTH-2026-001",
          page: 2,
        }),
        expect.objectContaining({ name: "grantor", value: "甲品牌有限公司" }),
        expect.objectContaining({
          name: "grantees",
          value: "乙供应链有限公司",
        }),
        expect.objectContaining({ name: "brand", value: "欧菲斯、示例牌" }),
        expect.objectContaining({
          name: "category",
          value: "办公用品；劳保用品",
        }),
        expect.objectContaining({ name: "region", value: "浙江省" }),
        expect.objectContaining({ name: "authorizationLevel", value: "2" }),
        expect.objectContaining({ name: "effectiveDate", value: "2026-01-02" }),
        expect.objectContaining({ name: "expiryDate", value: "2026-12-31" }),
        expect.objectContaining({
          name: "isProjectAuthorization",
          value: "是",
        }),
        expect.objectContaining({
          name: "projectName",
          value: "某某采购项目",
        }),
        expect.objectContaining({ name: "transferAllowed", value: "否" }),
      ]),
    );
    expect(fields.every((field) => field.evidenceText)).toBe(true);
  });

  it("does not invent fields from unlabeled prose", () => {
    const fields = extractAuthorizationFields([
      {
        name: "documentText",
        value: "甲公司与乙公司开展合作，期限另行约定。",
        confidence: 0.9,
        method: "OCR",
        page: 1,
        evidenceText: "甲公司与乙公司开展合作，期限另行约定。",
      },
    ]);

    expect(fields).toEqual([]);
  });

  it("flags a missing grantee when OCR drops the name between authorization cues", () => {
    const fields = extractAuthorizationFields([
      {
        name: "documentText",
        value: [
          "授权书",
          "兹认定",
          "为得力品牌",
          "广东",
          "文具品类",
          "经销商",
        ].join("\n"),
        confidence: 0.9,
        method: "OCR",
        page: 1,
        evidenceText: "授权书正文",
      },
    ]);

    expect(fields).toContainEqual(
      expect.objectContaining({
        name: "grantees",
        value: null,
        page: 1,
        evidenceText: "兹认定 … 为得力品牌",
      }),
    );
  });
});
