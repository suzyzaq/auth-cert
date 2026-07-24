import { describe, expect, it } from "vitest";
import { ShardGenerator } from "./shard-generator.js";

describe("ShardGenerator", () => {
  it("builds deterministic shards and keeps brand totals consistent", async () => {
    const generator = new ShardGenerator(2);
    const result = await generator.build([
      { brand: "BABYCARE", records: [{ code: "1" }] },
      { brand: "HOYO", records: [{ code: "2" }] },
      { brand: "印芭贝", records: [{ code: "3" }] },
    ]);

    expect(result.index.brandCount).toBe(3);
    expect(result.index.shardCount).toBe(2);
    expect(Object.keys(result.shards)).toEqual(["0", "1"]);
    expect(
      Object.values(result.shards).reduce(
        (count, shard) => count + Object.keys(shard.brands).length,
        0,
      ),
    ).toBe(3);
  });

  it("rejects duplicate brands before publishing", async () => {
    const generator = new ShardGenerator(2);

    await expect(
      generator.build([
        { brand: "HOYO", records: [{ code: "1" }] },
        { brand: "HOYO", records: [{ code: "2" }] },
      ]),
    ).rejects.toThrow("duplicate brand");
  });
});
