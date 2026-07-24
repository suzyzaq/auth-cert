import { MinerUParser } from "../packages/integrations/src/parsing/mineru-parser.js";

const token = process.env.MINERU_API_TOKEN?.trim();
if (!token) throw new Error("MINERU_API_TOKEN is required");
const sourceUrl =
  process.env.MINERU_TEST_URL?.trim() ??
  "https://cdn-mineru.openxlab.org.cn/demo/example.pdf";
const sourceHost = new URL(sourceUrl).hostname;

const parser = new MinerUParser({
  token,
  allowedSourceHosts: [sourceHost],
  pollIntervalMs: 3_000,
  maxPolls: 40,
});

const result = await parser.parse({
  attachmentId: "mineru-public-smoke-test",
  sourceUrl,
  mime: "application/pdf",
  bytes: new Uint8Array([1]),
});

console.log(
  JSON.stringify({
    status: "ok",
    pages: result.pages,
    evidenceBlocks: result.fields.length,
    extractedCharacters: result.rawText.length,
    extractedText:
      process.env.MINERU_SHOW_TEXT === "true" ? result.rawText : undefined,
  }),
);
