"use client";

import { useCallback } from "react";
import { Sidebar } from "@/components/dashboard/sidebar";
import { Header } from "@/components/dashboard/header";
import { useSSE } from "@/hooks/use-sse";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const handleSSE = useCallback(() => {}, []);
  const { status } = useSSE(handleSSE);

  return (
    <div className="flex min-h-screen bg-latte-bg-primary">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header sseStatus={status} />
        <main className="flex-1 p-6 lg:p-8 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
