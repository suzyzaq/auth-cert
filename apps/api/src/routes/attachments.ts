import type { FastifyInstance } from "fastify";

export async function registerAttachmentRoutes(app: FastifyInstance) {
  app.get("/api/attachments/:id/preview", async (request) => {
    const { id } = request.params as { id: string };
    return {
      id,
      available: true,
      expiresInSeconds: 300,
    };
  });
}
