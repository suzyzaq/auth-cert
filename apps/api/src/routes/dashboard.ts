import type { FastifyInstance } from "fastify";
import { taskFixtures } from "./tasks.js";

export async function registerDashboardRoutes(app: FastifyInstance) {
  app.get("/api/dashboard", async () => ({
    source: {
      today: "2026-07-23",
      generated: "2026-07-23 13:59:18",
      brands: 4249,
      authorizations: 5066,
      certificates: 4816,
      shards: 12,
      healthy: true,
    },
    metrics: {
      pending: 286,
      review: 47,
      critical: taskFixtures.filter((item) => item.risk === "CRITICAL").length,
      parsingFailed: 6,
      readyToWrite: 12,
    },
  }));
}
