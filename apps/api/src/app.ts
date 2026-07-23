import Fastify from "fastify";
import { registerAttachmentRoutes } from "./routes/attachments.js";
import { registerDashboardRoutes } from "./routes/dashboard.js";
import { registerReviewRoutes } from "./routes/reviews.js";
import { registerTaskRoutes } from "./routes/tasks.js";
import { InspectionMetrics } from "./observability/metrics.js";
import { FixedWindowRateLimit } from "./operations/rate-limit.js";

export function buildApp() {
  const metrics = new InspectionMetrics();
  const rateLimit = new FixedWindowRateLimit();
  const app = Fastify({
    logger: false,
    bodyLimit: 1_048_576,
    requestIdHeader: "x-trace-id",
  });
  app.addHook("onRequest", async (request, reply) => {
    if (!rateLimit.consume(request.ip)) {
      return reply.code(429).send({ error: "请求过于频繁，请稍后重试" });
    }
    metrics.increment("api_requests_total");
    reply
      .header("x-trace-id", request.id)
      .header("x-content-type-options", "nosniff")
      .header("referrer-policy", "no-referrer")
      .header("x-frame-options", "DENY")
      .header(
        "content-security-policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
      );
  });
  app.get("/health", async () => ({ status: "ok" }));
  app.get("/ready", async () => ({ status: "ready" }));
  app.get("/metrics", async () => metrics.snapshot());
  void registerTaskRoutes(app);
  void registerDashboardRoutes(app);
  void registerReviewRoutes(app);
  void registerAttachmentRoutes(app);
  return app;
}
