import { createDatabaseClient } from "./client.js";

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("DATABASE_URL is required");
}

const client = createDatabaseClient(databaseUrl);
await client.migrate();
await client.close();
