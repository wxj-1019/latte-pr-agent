import { NextRequest } from "next/server";
import { mockPromptVersions } from "@/lib/mock-data";

export async function GET() {
  return Response.json(mockPromptVersions);
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  return Response.json({
    id: Math.floor(Math.random() * 10000),
    ...body,
    created_at: new Date().toISOString(),
  });
}
