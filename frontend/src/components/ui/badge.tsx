import { cn } from "@/lib/utils";

type BadgeVariant = "success" | "warning" | "critical" | "info";

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  dot?: boolean;
  className?: string;
}

export function Badge({ variant, children, dot = true, className }: BadgeProps) {
  return (
    <span className={cn("latte-badge", `latte-badge-${variant}`, className)}>
      {dot && <span className="latte-badge-dot" style={{ background: `var(--latte-${variant})` }} />}
      {children}
    </span>
  );
}
