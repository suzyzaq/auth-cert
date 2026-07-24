import { Queue } from "bullmq";
import { retryPolicy } from "./retry-policy.js";

export function createInspectionQueue(redisUrl: string) {
  const connection = new URL(redisUrl);
  return new Queue("authorization-inspections", {
    connection: {
      host: connection.hostname,
      port: Number(connection.port || 6379),
      password: connection.password || undefined,
    },
    defaultJobOptions: {
      attempts: retryPolicy.attempts,
      backoff: retryPolicy.backoff,
      removeOnComplete: 500,
      removeOnFail: 1_000,
    },
  });
}
