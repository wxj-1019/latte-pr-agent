import type { Metadata } from "next";
import "./globals.css";
import { ErrorBoundary } from "@/components/error-boundary";
import { EnvCheck } from "@/components/env-check";
import { ToastProvider } from "@/components/ui/toast";

export const metadata: Metadata = {
  title: "Latte PR Agent - Enterprise AI Code Review",
  description: "Enterprise AI Code Review System with multi-model intelligence, context-aware analysis, and quality gates.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <EnvCheck />
        <ToastProvider>
          <ErrorBoundary>{children}</ErrorBoundary>
        </ToastProvider>
      </body>
    </html>
  );
}
