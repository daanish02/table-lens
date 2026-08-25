import { NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function GET() {
  const cookieStore = await cookies();
  const isAdmin = cookieStore.get("tl-admin")?.value === "1";
  return NextResponse.json({ isAdmin });
}
