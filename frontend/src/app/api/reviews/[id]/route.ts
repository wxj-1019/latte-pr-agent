import { mockReviews } from "@/lib/mock-data";

export async function GET(_request: Request, { params }: { params: { id: string } }) {
  const review = mockReviews.find((r) => r.id === Number(params.id));
  if (!review) {
    return Response.json({ error: "Review not found" }, { status: 404 });
  }
  return Response.json(review);
}
