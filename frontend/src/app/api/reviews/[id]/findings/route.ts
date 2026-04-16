import { mockFindings } from "@/lib/mock-data";

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const findings = mockFindings.filter((f) => f.review_id === Number(params.id));
  return Response.json(findings);
}
