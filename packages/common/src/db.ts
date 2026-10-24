import "server-only";
import { MongoClient, type Db } from "mongodb";

// Every store shares one MongoDB client per server process. The client is kept on globalThis, so hot reloads in dev do not open a new pool each time.
const cache = globalThis as typeof globalThis & { mongo?: Promise<MongoClient> };

function connect(): Promise<MongoClient> {
  const uri = process.env.MONGODB_URI;
  if (!uri) throw new Error("MONGODB_URI is not set");
  return new MongoClient(uri, { appName: "calhacks" }).connect();
}

export function mongo(): Promise<MongoClient> {
  // A failed connect is dropped from the cache, so the next call tries again.
  cache.mongo ??= connect().catch((error) => {
    cache.mongo = undefined;
    throw error;
  });
  return cache.mongo;
}

// Each store keeps its data in a database named after itself.
export async function database(name: string): Promise<Db> {
  return (await mongo()).db(name);
}
