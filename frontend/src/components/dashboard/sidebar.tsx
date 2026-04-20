"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, GitPullRequest, BarChart3, Settings, FileText, Sparkles, Shield, FolderGit2 } from "lucide-react";

const navItems = [
  { href: "/dashboard", icon: LayoutDashboard, label: "首页" },
  { href: "/dashboard/projects", icon: FolderGit2, label: "项目" },
  { href: "/dashboard/reviews", icon: GitPullRequest, label: "审查" },
  { href: "/dashboard/analyze", icon: Sparkles, label: "分析" },
  { href: "/dashboard/metrics", icon: BarChart3, label: "指标" },
  { href: "/dashboard/config", icon: Settings, label: "配置" },
  { href: "/dashboard/prompts", icon: FileText, label: "Prompts" },
  { href: "/dashboard/settings", icon: Shield, label: "系统设置" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="latte-sidebar pt-6">
      <div className="mb-8 px-3">
        <div className="w-10 h-10 flex items-center justify-center rounded-full bg-latte-bg-tertiary border border-latte-gold/20">
          <span className="text-lg font-bold text-latte-gold">L</span>
        </div>
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "latte-sidebar-item",
              (item.href === "/dashboard" ? pathname === item.href : pathname.startsWith(item.href)) && "active"
            )}
            title={item.label}
          >
            <item.icon size={20} strokeWidth={1.5} />
            <span className="text-sm font-medium">{item.label}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}
