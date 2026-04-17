"use client";

import { Input } from "@/components/ui/input";
import { RealtimeIndicator } from "@/components/ui/realtime-indicator";
import { Search, Bell } from "lucide-react";

interface HeaderProps {
  sseStatus?: "connecting" | "connected" | "disconnected";
}

export function Header({ sseStatus = "connected" }: HeaderProps) {
  return (
    <header className="h-16 border-b border-latte-text-primary/5 flex items-center justify-between px-6 bg-latte-bg-primary/80 backdrop-blur-sm">
      <div className="flex items-center gap-3 w-80">
        <Search size={16} className="text-latte-text-tertiary" />
        <Input
          placeholder="Search reviews, repos..."
          className="h-9 text-sm border-none bg-transparent px-0 focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
        />
      </div>
      <div className="flex items-center gap-4">
        <RealtimeIndicator status={sseStatus} />
        <button
          disabled
          title="功能开发中"
          className="relative p-2 rounded-latte-md text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Bell size={18} />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-latte-critical" />
        </button>
        <div className="h-8 w-8 rounded-full bg-latte-gold/20 border border-latte-gold/30 flex items-center justify-center text-xs font-medium text-latte-gold">
          JD
        </div>
      </div>
    </header>
  );
}
