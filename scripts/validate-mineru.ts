import { MinerUParser } from "../packages/integrations/src/parsing/mineru-parser.js";

const token = process.env.MINERU_API_TOKEN?.trim();
if (!token) throw new Error("MINERU_API_TOKEN is required");

const parser = new MinerUParser({
  token,
  allowedSourceHosts: ["cdn-mineru.openxlab.org.cn"],
  pollIntervalMs: 3_000,
  maxPolls: 40,
});

const result = await parser.parse({
  attachmentId: "mineru-public-smoke-test",
  sourceUrl: "https://cdn-mineru.openxlab.org.cn/demo/example.pdf",
  mime: "application/pdf",
  bytes: new Uint8Array([1]),
});

console.log(
  JSON.stringify({
    status: "ok",
    pages: result.pages,
    evidenceBlocks: result.fields.length,
    extractedCharacters: result.rawText.length,
  }),
);
