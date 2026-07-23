import { buildApp } from "./app.js";

const port = Number(process.env.API_PORT ?? 8788);
const app = buildApp();

await app.listen({ port, host: "0.0.0.0" });
