import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  // Basic CSRF protection: validate Origin/Referer for state-changing methods
  if (["POST", "PUT", "DELETE", "PATCH"].includes(request.method)) {
    const origin = request.headers.get("origin");
    const referer = request.headers.get("referer");
    const host = request.headers.get("host") || "";

    // Allow same-origin requests
    const isSameOrigin =
      (!origin || origin.includes(host)) &&
      (!referer || referer.includes(host));

    if (!isSameOrigin) {
      return new NextResponse("CSRF 验证失败", { status: 403 });
    }
  }

  // Security headers fallback for routes not covered by next.config headers
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");

  return response;
}

export const config = {
  matcher: "/((?!_next/static|_next/image|favicon.ico).*)",
};
