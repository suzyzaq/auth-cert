export interface SourceIndex {
  today: string;
  generated: string;
  shardCount: number;
  brandCount: number;
  brands: Record<string, number>;
}

export interface SourceBrandRecord {
  brand: string;
  shard: number;
  auth: unknown[];
  cert: unknown[];
}

export interface LoadedSource {
  index: SourceIndex;
  brands: SourceBrandRecord[];
}

function requireObject(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

export class SourceJsonClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  private async getJson(path: string): Promise<unknown> {
    const response = await this.fetcher(`${this.baseUrl}${path}`);
    if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
    return response.json();
  }

  async loadAll(): Promise<LoadedSource> {
    const rawIndex = requireObject(await this.getJson("/index.json"), "index");
    const index = rawIndex as unknown as SourceIndex;
    if (
      !Number.isInteger(index.shardCount) ||
      !Number.isInteger(index.brandCount) ||
      typeof index.today !== "string" ||
      typeof index.generated !== "string"
    ) {
      throw new Error("invalid source index");
    }

    const brandMap = requireObject(index.brands, "index.brands") as Record<
      string,
      number
    >;
    if (Object.keys(brandMap).length !== index.brandCount) {
      throw new Error("brand count mismatch");
    }

    const brands: SourceBrandRecord[] = [];
    for (let shard = 0; shard < index.shardCount; shard += 1) {
      const shardData = requireObject(
        await this.getJson(`/shard/${shard}.json`),
        `shard ${shard}`,
      );
      for (const [brand, rawRecord] of Object.entries(shardData)) {
        if (brandMap[brand] !== shard) {
          throw new Error(`brand shard mismatch: ${brand}`);
        }
        const record = requireObject(rawRecord, `brand ${brand}`);
        brands.push({
          brand,
          shard,
          auth: Array.isArray(record.auth) ? record.auth : [],
          cert: Array.isArray(record.cert) ? record.cert : [],
        });
      }
    }

    const boundaryResponse = await this.fetcher(
      `${this.baseUrl}/shard/${index.shardCount}.json`,
    );
    if (boundaryResponse.status !== 404) {
      throw new Error("boundary shard must return HTTP 404");
    }
    if (brands.length !== index.brandCount) {
      throw new Error("actual brand count mismatch");
    }

    return { index: { ...index, brands: brandMap }, brands };
  }
}
