import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "disabled:opacity-50 disabled:cursor-not-allowed",
          variant === "primary" && [
            "latte-btn-primary",
            size === "sm" && "px-5 py-2.5 text-sm",
            size === "md" && "px-7 py-3.5 text-[15px]",
            size === "lg" && "px-9 py-4 text-base",
          ],
          variant === "secondary" && [
            "latte-btn-secondary",
            size === "sm" && "px-5 py-2.5 text-sm",
            size === "md" && "px-7 py-3.5 text-[15px]",
            size === "lg" && "px-9 py-4 text-base",
          ],
          variant === "ghost" && [
            "inline-flex items-center justify-center gap-2 rounded-latte-md text-latte-text-secondary transition-colors duration-200 hover:text-latte-text-primary hover:bg-latte-bg-tertiary",
            size === "sm" && "px-3 py-1.5 text-sm",
            size === "md" && "px-4 py-2 text-[15px]",
            size === "lg" && "px-5 py-2.5 text-base",
          ],
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
