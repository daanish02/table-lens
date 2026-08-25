import { NextResponse } from "next/server";
import { cookies } from "next/headers";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function POST() {
  const cookieStore = await cookies();
  if (cookieStore.get("tl-admin")?.value !== "1") {
    return NextResponse.json({ detail: "forbidden" }, { status: 403 });
  }
  const adminKey = process.env.ADMIN_KEY ?? "";
  const res = await fetch(`${BACKEND_URL}/api/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Key": adminKey },
  });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
