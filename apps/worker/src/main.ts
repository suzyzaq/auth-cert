import { createInspectionQueue } from "./queue.js";
import { createParserFromEnvironment } from "./parser-factory.js";

const redisUrl = process.env.REDIS_URL ?? "redis://localhost:6379";
const queue = createInspectionQueue(redisUrl);
const parser = createParserFromEnvironment(process.env);

console.log(
  JSON.stringify({
    service: "authorization-inspection-worker",
    queue: queue.name,
    parser: parser.constructor.name,
    status: "ready",
  }),
);
