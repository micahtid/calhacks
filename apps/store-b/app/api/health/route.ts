import { connection } from "next/server";
import { getDb } from "@/lib/mongodb";

export async function GET() {
  await connection();
  try {
    await (await getDb()).command({ ping: 1 });
    return Response.json({ status: "ok", db: "ok" });
  } catch (e) {
    return Response.json({ status: "ok", db: `error: ${(e as Error).name}` }, { status: 503 });
  }
}
