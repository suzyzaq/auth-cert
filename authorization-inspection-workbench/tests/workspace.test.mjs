import { readFile } from "node:fs/promises";
import { test, expect } from "vitest";

test("workspace exposes required applications", async () => {
  const pkg = JSON.parse(
    await readFile(new URL("../package.json", import.meta.url), "utf8"),
  );

  expect(pkg.scripts).toMatchObject({
    dev: expect.any(String),
    test: expect.any(String),
    typecheck: expect.any(String),
    lint: expect.any(String),
  });
});
