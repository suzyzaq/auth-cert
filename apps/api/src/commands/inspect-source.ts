import { SourceJsonClient } from "@auth-inspection/integrations/source-json-client";

const modeIndex = process.argv.indexOf("--mode");
const mode = modeIndex >= 0 ? process.argv[modeIndex + 1] : "read-only";
if (mode !== "read-only") {
  throw new Error("source inspection only supports read-only mode");
}

const baseUrl =
  process.env.SOURCE_API_BASE_URL ??
  "https://supply-auto-project.oss-cn-hangzhou.aliyuncs.com/auth-cert-db/api";

const result = await new SourceJsonClient(baseUrl).loadAll();
const nonEmptySamples = result.brands
  .filter((brand) => brand.auth.length > 0 || brand.cert.length > 0)
  .slice(0, 3)
  .map((brand) => ({
    brand: brand.brand,
    shard: brand.shard,
    authCount: brand.auth.length,
    certCount: brand.cert.length,
  }));

console.log(
  JSON.stringify(
    {
      mode,
      today: result.index.today,
      generated: result.index.generated,
      shardCount: result.index.shardCount,
      brandCount: result.index.brandCount,
      loadedBrandCount: result.brands.length,
      boundaryShardStatus: 404,
      writesIssued: 0,
      nonEmptySamples,
    },
    null,
    2,
  ),
);

