interface WindowEntry {
  count: number;
  resetAt: number;
}

export class FixedWindowRateLimit {
  private readonly entries = new Map<string, WindowEntry>();

  constructor(
    private readonly limit = 300,
    private readonly windowMs = 60_000,
  ) {}

  consume(key: string, now = Date.now()): boolean {
    const current = this.entries.get(key);
    if (!current || current.resetAt <= now) {
      this.entries.set(key, { count: 1, resetAt: now + this.windowMs });
      return true;
    }
    current.count += 1;
    return current.count <= this.limit;
  }
}

