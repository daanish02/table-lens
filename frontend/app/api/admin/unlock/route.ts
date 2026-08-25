import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export async function POST(req: NextRequest) {
  const { key } = await req.json();
  const adminKey = process.env.ADMIN_KEY;
  if (!adminKey || key !== adminKey) {
    return NextResponse.json({ ok: false }, { status: 403 });
  }
  const cookieStore = await cookies();
  cookieStore.set("tl-admin", "1", {
    httpOnly: true,
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24 * 90, // 90 days
  });
  return NextResponse.json({ ok: true });
}
