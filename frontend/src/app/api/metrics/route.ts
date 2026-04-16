import { NextRequest } from "next/server";
import { mockMetrics, mockMetricsChart } from "@/lib/mock-data";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const range = searchParams.get("range") || "7d";
  return Response.json({
    metrics: mockMetrics,
    chart: mockMetricsChart,
    range,
  });
}
