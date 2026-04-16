import { NextRequest } from "next/server";

export async function POST(request: NextRequest, { params }: { params: { id: string } }) {
  const body = await request.json();
  return Response.json({
    id: Math.floor(Math.random() * 10000),
    finding_id: Number(params.id),
    is_false_positive: body.is_false_positive ?? false,
    comment: body.comment ?? "",
    created_at: new Date().toISOString(),
  });
}
