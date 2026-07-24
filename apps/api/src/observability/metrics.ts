export const alertThresholds = {
  sourceUnavailableMinutes: 5,
  queueBacklog: 500,
  parserFailureRate: 0.05,
  writebackFailureCount: 1,
} as const;

export class InspectionMetrics {
  private counters = new Map<string, number>();

  increment(name: string, value = 1): void {
    this.counters.set(name, (this.counters.get(name) ?? 0) + value);
  }

  snapshot(): Record<string, number> {
    return Object.fromEntries(this.counters);
  }
}

