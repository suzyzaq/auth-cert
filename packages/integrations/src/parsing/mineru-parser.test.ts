import { describe, expect, it, vi } from "vitest";
import { MinerUParser } from "./mineru-parser.js";

describe("MinerUParser", () => {
  it("submits a VLM OCR task, polls it, and preserves page evidence", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ code: 0, data: { task_id: "task-1" }, msg: "ok" }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: 0,
            data: { task_id: "task-1", state: "running" },
            msg: "ok",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: 0,
            data: {
              task_id: "task-1",
              state: "done",
              full_zip_url:
                "https://cdn-mineru.openxlab.org.cn/pdf/result.zip",
            },
            msg: "ok",
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(new Uint8Array([1, 2, 3]), { status: 200 }),
      );
    const resultReader = vi.fn().mockResolvedValue({
      pages: 2,
      rawText: "授权区域仅限浙江省",
      blocks: [
        {
          page: 2,
          text: "授权区域仅限浙江省",
          confidence: 0.96,
        },
      ],
    });
    const parser = new MinerUParser({
      token: "secret-token",
      fetcher,
      pollIntervalMs: 0,
      resultReader,
    });

    const result = await parser.parse({
      attachmentId: "record-1",
      sourceUrl:
        "https://supply-auto-project.oss-cn-hangzhou.aliyuncs.com/auth.pdf",
      mime: "application/pdf",
      bytes: new Uint8Array([1]),
    });

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "https://mineru.net/api/v4/extract/task",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer secret-token",
        }),
      }),
    );
    expect(JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body))).toMatchObject({
      model_version: "vlm",
      is_ocr: true,
      language: "ch",
      enable_formula: false,
    });
    expect(result).toMatchObject({
      pages: 2,
      rawText: "授权区域仅限浙江省",
      fields: [
        {
          name: "documentText",
          value: "授权区域仅限浙江省",
          page: 2,
          evidenceText: "授权区域仅限浙江省",
          confidence: 0.96,
        },
      ],
    });
    expect(resultReader).toHaveBeenCalledOnce();
  });

  it("rejects attachment URLs outside the approved source hosts", async () => {
    const parser = new MinerUParser({
      token: "secret-token",
      fetcher: vi.fn(),
      resultReader: vi.fn(),
    });

    await expect(
      parser.parse({
        attachmentId: "record-2",
        sourceUrl: "https://untrusted.example/private.pdf",
        mime: "application/pdf",
        bytes: new Uint8Array([1]),
      }),
    ).rejects.toThrow("attachment host is not allowed");
  });

  it("fails safely when MinerU reports a parsing failure", async () => {
    const fetcher = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ code: 0, data: { task_id: "task-3" }, msg: "ok" }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            code: 0,
            data: {
              task_id: "task-3",
              state: "failed",
              err_msg: "文件读取失败",
            },
            msg: "ok",
          }),
          { status: 200 },
        ),
      );
    const parser = new MinerUParser({
      token: "secret-token",
      fetcher,
      pollIntervalMs: 0,
      resultReader: vi.fn(),
    });

    await expect(
      parser.parse({
        attachmentId: "record-3",
        sourceUrl:
          "https://supply-auto-project.oss-cn-hangzhou.aliyuncs.com/bad.pdf",
        mime: "application/pdf",
        bytes: new Uint8Array([1]),
      }),
    ).rejects.toThrow("MinerU parsing failed: 文件读取失败");
  });
});
