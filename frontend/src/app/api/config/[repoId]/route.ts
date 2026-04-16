import { NextRequest } from "next/server";
import { mockProjectConfig } from "@/lib/mock-data";

export async function GET(_request: Request, { params }: { params: { repoId: string } }) {
  return Response.json({ ...mockProjectConfig, repo_id: params.repoId });
}

export async function PUT(request: NextRequest, { params }: { params: { repoId: string } }) {
  const body = await request.json();
  return Response.json({
    ...mockProjectConfig,
    repo_id: params.repoId,
    config_json: body,
    updated_at: new Date().toISOString(),
  });
}
