import "server-only";
import { MongoClient, type Db } from "mongodb";

// Reuse one client across hot reloads in dev and across requests in prod.
const globalForMongo = globalThis as unknown as { _mongoClient?: Promise<MongoClient> };

export function getClient(): Promise<MongoClient> {
  const uri = process.env.MONGODB_URI;
  if (!uri) throw new Error("MONGODB_URI is not set; copy .env.example to .env");
  globalForMongo._mongoClient ??= new MongoClient(uri, { appName: "calhacks-store-a" }).connect();
  return globalForMongo._mongoClient;
}

export async function getDb(): Promise<Db> {
  return (await getClient()).db(process.env.MONGODB_DB_STORE_A ?? "store-a");
}
