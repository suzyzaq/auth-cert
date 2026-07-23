import { createHash } from "node:crypto";
import { validateAttachment } from "./file-policy.js";

export interface DownloadedAttachment {
  bytes: Uint8Array;
  mime: string;
  size: number;
  sha256: string;
  resolvedUrl: string;
}

export class AttachmentClient {
  constructor(private readonly fetcher: typeof fetch = fetch) {}

  async download(url: string): Promise<DownloadedAttachment> {
    const response = await this.fetcher(url, { redirect: "follow" });
    if (!response.ok) {
      throw new Error(`attachment unavailable: HTTP ${response.status}`);
    }

    const bytes = new Uint8Array(await response.arrayBuffer());
    const mime = response.headers.get("content-type")?.split(";")[0] ?? "";
    validateAttachment({ mime, size: bytes.byteLength });

    return {
      bytes,
      mime,
      size: bytes.byteLength,
      sha256: createHash("sha256").update(bytes).digest("hex"),
      resolvedUrl: response.url || url,
    };
  }
}
