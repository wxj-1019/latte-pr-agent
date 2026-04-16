import { NextRequest } from "next/server";
import { mockReviews } from "@/lib/mock-data";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get("status");
  const repo = searchParams.get("repo");

  let data = [...mockReviews];
  if (status) {
    data = data.filter((r) => r.status === status);
  }
  if (repo) {
    data = data.filter((r) => r.repo_id.includes(repo));
  }

  return Response.json(data);
}
