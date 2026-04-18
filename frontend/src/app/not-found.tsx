import Link from "next/link";
import { Coffee } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-latte-bg-primary text-latte-text-primary">
      <Coffee size={64} className="text-latte-gold mb-6" />
      <h1 className="text-4xl font-display font-bold mb-2">404</h1>
      <p className="text-latte-text-secondary mb-8">这个页面好像不在菜单里...</p>
      <Link
        href="/dashboard"
        className="px-6 py-2.5 rounded-latte-lg bg-latte-gold/10 text-latte-gold text-sm font-medium hover:bg-latte-gold/15 transition-colors"
      >
        返回首页
      </Link>
    </div>
  );
}
