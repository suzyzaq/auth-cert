import { describe, expect, it } from "vitest";
import { MinerUParser } from "@auth-inspection/integrations/mineru-parser";
import { createParserFromEnvironment } from "./parser-factory.js";

describe("createParserFromEnvironment", () => {
  it("creates MinerU as the primary parser when configured", () => {
    const parser = createParserFromEnvironment({
      PARSER_ADAPTER: "mineru",
      MINERU_API_TOKEN: "token-value",
    });

    expect(parser).toBeInstanceOf(MinerUParser);
  });

  it("refuses MinerU startup without a token", () => {
    expect(() =>
      createParserFromEnvironment({ PARSER_ADAPTER: "mineru" }),
    ).toThrow("MINERU_API_TOKEN is required");
  });
});
