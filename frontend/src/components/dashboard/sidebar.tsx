"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { GitPullRequest, BarChart3, Settings, FileText, Sparkles } from "lucide-react";

const navItems = [
  { href: "/dashboard/reviews", icon: GitPullRequest, label: "Reviews" },
  { href: "/dashboard/analyze", icon: Sparkles, label: "Analyze" },
  { href: "/dashboard/metrics", icon: BarChart3, label: "Metrics" },
  { href: "/dashboard/config", icon: Settings, label: "Config" },
  { href: "/dashboard/prompts", icon: FileText, label: "Prompts" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="latte-sidebar pt-6">
      <div className="mb-8 w-10 h-10 flex items-center justify-center rounded-full bg-latte-bg-tertiary border border-latte-gold/20">
        <span className="text-lg font-bold text-latte-gold">L</span>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "latte-sidebar-item",
              pathname.startsWith(item.href) && "active"
            )}
            title={item.label}
          >
            <item.icon size={20} strokeWidth={1.5} />
          </Link>
        ))}
      </nav>
    </aside>
  );
}
