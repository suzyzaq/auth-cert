import type { AttachmentParser } from "@auth-inspection/integrations/parsing";
import { MinerUParser } from "@auth-inspection/integrations/mineru-parser";

type ParserEnvironment = Record<string, string | undefined>;

export function createParserFromEnvironment(
  environment: ParserEnvironment,
): AttachmentParser {
  const adapter = environment.PARSER_ADAPTER ?? "mineru";
  if (adapter !== "mineru") {
    throw new Error(`unsupported parser adapter: ${adapter}`);
  }
  const token = environment.MINERU_API_TOKEN?.trim();
  if (!token) throw new Error("MINERU_API_TOKEN is required");

  const allowedSourceHosts = environment.MINERU_ALLOWED_SOURCE_HOSTS
    ?.split(",")
    .map((host) => host.trim())
    .filter(Boolean);
  return new MinerUParser({
    token,
    ...(allowedSourceHosts ? { allowedSourceHosts } : {}),
  });
}
