import { strFromU8, unzipSync } from "fflate";
import type {
  AttachmentParser,
  ParsedDocument,
  ParseAttachmentInput,
} from "./contracts.js";

interface MinerUBlock {
  page: number;
  text: string;
  confidence: number;
}

interface MinerUReadResult {
  pages: number;
  rawText: string;
  blocks: MinerUBlock[];
}

type MinerUResultReader = (archive: Uint8Array) => Promise<MinerUReadResult>;

interface MinerUParserOptions {
  token: string;
  fetcher?: typeof fetch;
  pollIntervalMs?: number;
  maxPolls?: number;
  resultReader?: MinerUResultReader;
  allowedSourceHosts?: string[];
}

interface MinerUEnvelope<T> {
  code: number;
  msg: string;
  data: T;
}

interface ContentListItem {
  type?: string;
  text?: string;
  table_body?: string;
  page_idx?: number;
  score?: number;
}

const defaultAllowedSourceHosts = [
  "supply-auto-project.oss-cn-hangzhou.aliyuncs.com",
  "cdn.jsdelivr.net",
  "fastly.jsdelivr.net",
  "gcore.jsdelivr.net",
];

function stripHtml(value: string): string {
  return value.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

export async function readMinerUArchive(
  archive: Uint8Array,
): Promise<MinerUReadResult> {
  const files = unzipSync(archive);
  const contentEntry = Object.entries(files).find(([name]) =>
    name.endsWith("_content_list.json"),
  );
  if (!contentEntry) {
    throw new Error("MinerU result does not contain content_list.json");
  }
  const content = JSON.parse(strFromU8(contentEntry[1])) as ContentListItem[];
  const blocks = content
    .map((item): MinerUBlock | null => {
      const raw =
        typeof item.text === "string"
          ? item.text
          : typeof item.table_body === "string"
            ? stripHtml(item.table_body)
            : "";
      const text = raw.trim();
      if (!text) return null;
      return {
        page: (item.page_idx ?? 0) + 1,
        text,
        confidence:
          typeof item.score === "number"
            ? Math.max(0, Math.min(1, item.score))
            : 0.9,
      };
    })
    .filter((item): item is MinerUBlock => item !== null);
  return {
    pages: Math.max(1, ...blocks.map((block) => block.page)),
    rawText: blocks.map((block) => block.text).join("\n"),
    blocks,
  };
}

export class MinerUParser implements AttachmentParser {
  private readonly fetcher: typeof fetch;
  private readonly pollIntervalMs: number;
  private readonly maxPolls: number;
  private readonly resultReader: MinerUResultReader;
  private readonly allowedSourceHosts: Set<string>;

  constructor(private readonly options: MinerUParserOptions) {
    if (!options.token.trim()) throw new Error("MinerU token is not configured");
    this.fetcher = options.fetcher ?? fetch;
    this.pollIntervalMs = options.pollIntervalMs ?? 3_000;
    this.maxPolls = options.maxPolls ?? 40;
    this.resultReader = options.resultReader ?? readMinerUArchive;
    this.allowedSourceHosts = new Set(
      options.allowedSourceHosts ?? defaultAllowedSourceHosts,
    );
  }

  async parse(input: ParseAttachmentInput): Promise<ParsedDocument> {
    if (!input.sourceUrl) {
      throw new Error("MinerU requires an attachment source URL");
    }
    const source = new URL(input.sourceUrl);
    if (
      source.protocol !== "https:" ||
      !this.allowedSourceHosts.has(source.hostname)
    ) {
      throw new Error("attachment host is not allowed");
    }

    const submitted = await this.request<
      MinerUEnvelope<{ task_id: string }>
    >("https://mineru.net/api/v4/extract/task", {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify({
        url: source.toString(),
        model_version: "vlm",
        is_ocr: true,
        language: "ch",
        enable_formula: false,
        enable_table: true,
        data_id: input.attachmentId,
        no_cache: false,
      }),
    });
    this.assertApiSuccess(submitted);
    const taskId = submitted.data.task_id;

    for (let attempt = 0; attempt < this.maxPolls; attempt += 1) {
      const status = await this.request<
        MinerUEnvelope<{
          state: "done" | "pending" | "running" | "failed" | "converting";
          full_zip_url?: string;
          err_msg?: string;
        }>
      >(`https://mineru.net/api/v4/extract/task/${encodeURIComponent(taskId)}`, {
        method: "GET",
        headers: this.headers(),
      });
      this.assertApiSuccess(status);
      if (status.data.state === "failed") {
        throw new Error(
          `MinerU parsing failed: ${status.data.err_msg || "unknown error"}`,
        );
      }
      if (status.data.state === "done") {
        if (!status.data.full_zip_url) {
          throw new Error("MinerU completed without a result URL");
        }
        const resultUrl = new URL(status.data.full_zip_url);
        if (
          resultUrl.protocol !== "https:" ||
          resultUrl.hostname !== "cdn-mineru.openxlab.org.cn"
        ) {
          throw new Error("MinerU result host is not allowed");
        }
        const archiveResponse = await this.fetcher(resultUrl);
        if (!archiveResponse.ok) {
          throw new Error(
            `MinerU result download failed: HTTP ${archiveResponse.status}`,
          );
        }
        const document = await this.resultReader(
          new Uint8Array(await archiveResponse.arrayBuffer()),
        );
        return {
          pages: document.pages,
          rawText: document.rawText,
          fields: document.blocks.map((block) => ({
            name: "documentText",
            value: block.text,
            confidence: block.confidence,
            method: "OCR",
            page: block.page,
            evidenceText: block.text,
            validationStatus: "SINGLE_SOURCE",
          })),
        };
      }
      if (this.pollIntervalMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, this.pollIntervalMs));
      }
    }
    throw new Error("MinerU parsing timed out");
  }

  private headers(): Record<string, string> {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.options.token}`,
    };
  }

  private async request<T>(url: string, init: RequestInit): Promise<T> {
    const response = await this.fetcher(url, init);
    if (!response.ok) {
      throw new Error(`MinerU request failed: HTTP ${response.status}`);
    }
    return (await response.json()) as T;
  }

  private assertApiSuccess(response: MinerUEnvelope<unknown>): void {
    if (response.code !== 0) {
      throw new Error(`MinerU API error ${response.code}: ${response.msg}`);
    }
  }
}
