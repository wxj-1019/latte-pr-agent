"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { RealtimeIndicator } from "@/components/ui/realtime-indicator";
import { NotificationPanel, useNotification } from "@/components/ui/notification";
import { useSSE } from "@/hooks/use-sse";
import { Search, Bell, User } from "lucide-react";
import { ThemeSwitcher } from "@/components/ui/theme-switcher";

export function Header() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { status, reconnect } = useSSE();
  const { unreadCount } = useNotification();
  const [panelOpen, setPanelOpen] = useState(false);
  const bellRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (
        e.key === "/" &&
        !["INPUT", "TEXTAREA", "SELECT"].includes((e.target as HTMLElement).tagName)
      ) {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function handleSearch(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && query.trim()) {
      router.push(`/dashboard/reviews?repo=${encodeURIComponent(query.trim())}`);
      setQuery("");
    }
  }

  return (
    <header className="h-16 border-b border-latte-text-primary/5 flex items-center justify-between px-6 bg-latte-bg-primary/80 backdrop-blur-sm relative">
      <div className="flex items-center gap-3 w-80">
        <Search size={16} className="text-latte-text-tertiary" />
        <Input
          ref={inputRef}
          placeholder="Search reviews, repos... (按 / 聚焦)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleSearch}
          className="h-9 text-sm border-none bg-transparent px-0 focus:ring-0 focus-visible:ring-0 focus-visible:ring-offset-0"
        />
      </div>
      <div className="flex items-center gap-4">
        <RealtimeIndicator
          status={status}
          onClick={status !== "connected" ? reconnect : undefined}
        />
        <ThemeSwitcher />
        <div className="relative">
          <button
            ref={bellRef}
            onClick={() => setPanelOpen((v) => !v)}
            className="relative p-2 rounded-latte-md text-latte-text-tertiary hover:text-latte-text-primary hover:bg-latte-bg-tertiary transition-colors"
            aria-label="通知"
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute top-1.5 right-1.5 h-2.5 w-2.5 rounded-full bg-latte-critical ring-2 ring-latte-bg-primary" />
            )}
          </button>
          <NotificationPanel open={panelOpen} onClose={() => setPanelOpen(false)} />
        </div>
        <div className="h-8 w-8 rounded-full bg-latte-gold/20 border border-latte-gold/30 flex items-center justify-center text-latte-gold">
          <User size={14} strokeWidth={2} />
        </div>
      </div>
    </header>
  );
}
