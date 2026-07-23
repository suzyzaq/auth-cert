import { createInspectionQueue } from "./queue.js";

const redisUrl = process.env.REDIS_URL ?? "redis://localhost:6379";
const queue = createInspectionQueue(redisUrl);

console.log(
  JSON.stringify({
    service: "authorization-inspection-worker",
    queue: queue.name,
    status: "ready",
  }),
);
