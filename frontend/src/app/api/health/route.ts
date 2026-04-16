export async function GET() {
  const health = {
    status: "healthy",
    timestamp: new Date().toISOString(),
    service: "latte-pr-agent-web",
    version: process.env.npm_package_version || "0.1.0",
    environment: process.env.NODE_ENV || "development",
  };

  return Response.json(health, {
    status: 200,
    headers: {
      "Cache-Control": "no-cache",
    },
  });
}