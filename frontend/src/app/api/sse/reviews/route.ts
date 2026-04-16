import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      let count = 0;
      const interval = setInterval(() => {
        count++;
        const statuses = ["pending", "running", "completed"] as const;
        const data = JSON.stringify({
          review_id: 42,
          status: statuses[count % statuses.length],
          timestamp: new Date().toISOString(),
          findings_count: count % statuses.length === 2 ? 3 : undefined,
        });
        controller.enqueue(encoder.encode(`data: ${data}\n\n`));
      }, 8000);

      request.signal.addEventListener("abort", () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
