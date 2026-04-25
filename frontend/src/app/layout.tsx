import type { Metadata } from "next";
import "./globals.css";
import "nprogress/nprogress.css";
import { ErrorBoundary } from "@/components/error-boundary";
import { EnvCheck } from "@/components/env-check";
import { ToastProvider } from "@/components/ui/toast";
import { NotificationProvider } from "@/components/ui/notification";
import { ProgressBar } from "@/components/ui/progress-bar";
import { ThemeProvider } from "@/themes";

export const metadata: Metadata = {
  title: "Latte PR Agent - 企业级 AI 代码审查",
  description: "企业级 AI 代码审查系统，具备多模型智能、上下文感知分析和质量门禁。",
};

const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem('latte-theme')||'latte-night';document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','latte-night');}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <ThemeProvider>
          <ProgressBar />
          <EnvCheck />
          <NotificationProvider>
            <ToastProvider>
              <ErrorBoundary>{children}</ErrorBoundary>
            </ToastProvider>
          </NotificationProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
