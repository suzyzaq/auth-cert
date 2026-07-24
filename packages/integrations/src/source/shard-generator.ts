import { createHash } from "node:crypto";

export interface BrandSource {
  brand: string;
  records: Array<Record<string, unknown>>;
}

export interface GeneratedShard {
  brands: Record<string, Array<Record<string, unknown>>>;
}

export interface GeneratedQueryData {
  prefix?: string;
  index: {
    today: string;
    brandCount: number;
    shardCount: number;
    brands: Record<string, number>;
  };
  shards: Record<string, GeneratedShard>;
}

export class ShardGenerator {
  constructor(
    private readonly shardCount = 12,
    private readonly today = new Date().toISOString().slice(0, 10),
  ) {
    if (!Number.isInteger(shardCount) || shardCount < 1) {
      throw new Error("shard count must be a positive integer");
    }
  }

  async build(sources: BrandSource[]): Promise<GeneratedQueryData> {
    const unique = new Set<string>();
    const brands: Record<string, number> = {};
    const shards: Record<string, GeneratedShard> = Object.fromEntries(
      Array.from({ length: this.shardCount }, (_, index) => [
        String(index),
        { brands: {} },
      ]),
    );

    for (const source of [...sources].sort((left, right) =>
      left.brand.localeCompare(right.brand, "zh-CN"),
    )) {
      const brand = source.brand.trim();
      if (!brand) throw new Error("brand is required");
      if (unique.has(brand)) throw new Error(`duplicate brand: ${brand}`);
      unique.add(brand);

      const shard = this.shardFor(brand);
      brands[brand] = shard;
      shards[String(shard)]!.brands[brand] = source.records;
    }

    return {
      index: {
        today: this.today,
        brandCount: unique.size,
        shardCount: this.shardCount,
        brands,
      },
      shards,
    };
  }

  async validate(data: GeneratedQueryData): Promise<void> {
    const actualBrands = Object.values(data.shards).reduce(
      (total, shard) => total + Object.keys(shard.brands).length,
      0,
    );
    if (actualBrands !== data.index.brandCount) {
      throw new Error("invalid brand count");
    }
    if (Object.keys(data.shards).length !== data.index.shardCount) {
      throw new Error("invalid shard count");
    }
  }

  private shardFor(brand: string): number {
    const digest = createHash("sha256").update(brand).digest();
    return digest.readUInt32BE(0) % this.shardCount;
  }
}

