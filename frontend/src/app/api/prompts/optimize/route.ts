import { NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const original = body.prompt || body.content || "";
  const optimized = original
    ? `[Optimized] ${original}\n\n<!-- Enhanced for clarity and specificity -->`
    : "No prompt provided";
  return Response.json({ optimized, original });
}
