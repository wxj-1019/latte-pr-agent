import { cn } from "@/lib/utils";

type GlassCardVariant = "default" | "interactive" | "elevated" | "status";
type StatusType = "pending" | "running" | "completed" | "failed" | "skipped";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  variant?: GlassCardVariant;
  status?: StatusType;
}

const statusBorderClass: Record<StatusType, string> = {
  pending: "border-l-amber-500",
  running: "border-l-blue-500",
  completed: "border-l-latte-success",
  failed: "border-l-latte-critical",
  skipped: "border-l-latte-text-muted",
};

export function GlassCard({ children, className, variant = "default", status }: GlassCardProps) {
  const isStatus = variant === "status" && status;
  return (
    <div
      className={cn(
        "latte-glass",
        variant === "interactive" && "cursor-pointer hover:scale-[1.01]",
        variant === "elevated" && "shadow-latte-lg",
        isStatus && ["border-l-4", statusBorderClass[status]],
        className
      )}
    >
      {children}
    </div>
  );
}
