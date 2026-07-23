import type { FastifyInstance } from "fastify";
import { authorize, type UserRole } from "../auth/authorize.js";

function roleFromHeader(value: unknown): UserRole {
  return value === "ADMIN" || value === "REVIEWER" ? value : "INSPECTOR";
}

export async function registerReviewRoutes(app: FastifyInstance) {
  app.post("/api/tasks/:id/review", async (request, reply) => {
    try {
      authorize(roleFromHeader(request.headers["x-user-role"]), "REVIEW_TASK");
      return reply.code(200).send({ status: "REVIEWED" });
    } catch {
      return reply.code(403).send({ message: "forbidden" });
    }
  });

  app.post("/api/writebacks/:id/approve", async (request, reply) => {
    try {
      authorize(
        roleFromHeader(request.headers["x-user-role"]),
        "APPROVE_WRITEBACK",
      );
      return reply.code(200).send({ status: "AWAITING_WRITEBACK" });
    } catch {
      return reply.code(403).send({ message: "forbidden" });
    }
  });
}
