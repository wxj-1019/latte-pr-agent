"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Bell,
  CheckCheck,
  Trash2,
  Info,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type { AppNotification, NotificationType, NotificationCategory } from "@/types";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

interface NotificationContextValue {
  notifications: AppNotification[];
  unreadCount: number;
  addNotification: (n: Omit<AppNotification, "id" | "created_at" | "read">) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}

/* ------------------------------------------------------------------ */
/*  Global imperative API (for non-React callers like api.ts)          */
/* ------------------------------------------------------------------ */

let globalNotify: ((n: Omit<AppNotification, "id" | "created_at" | "read">) => void) | null = null;

export function notify(notification: Omit<AppNotification, "id" | "created_at" | "read">) {
  if (globalNotify) {
    globalNotify(notification);
  }
}

/* helpers */
export function notifySuccess(title: string, message: string, opts?: Partial<Omit<AppNotification, "id" | "created_at" | "read" | "title" | "message" | "type">>) {
  notify({ type: "success", title, message, category: opts?.category ?? "system", ...opts });
}

export function notifyError(title: string, message: string, opts?: Partial<Omit<AppNotification, "id" | "created_at" | "read" | "title" | "message" | "type">>) {
  notify({ type: "error", title, message, category: opts?.category ?? "system", ...opts });
}

export function notifyInfo(title: string, message: string, opts?: Partial<Omit<AppNotification, "id" | "created_at" | "read" | "title" | "message" | "type">>) {
  notify({ type: "info", title, message, category: opts?.category ?? "system", ...opts });
}

export function notifyWarning(title: string, message: string, opts?: Partial<Omit<AppNotification, "id" | "created_at" | "read" | "title" | "message" | "type">>) {
  notify({ type: "warning", title, message, category: opts?.category ?? "system", ...opts });
}

/* ------------------------------------------------------------------ */
/*  Context                                                             */
/* ------------------------------------------------------------------ */

const NotificationContext = createContext<NotificationContextValue | null>(null);

const STORAGE_KEY = "latte-notifications-v1";

function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function loadFromStorage(): AppNotification[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AppNotification[];
    /* keep last 50 only */
    return parsed.slice(-50);
  } catch {
    return [];
  }
}

function saveToStorage(items: AppNotification[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(-50)));
  } catch {
    /* quota exceeded or private mode */
  }
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifications, setNotifications] = useState<AppNotification[]>(loadFromStorage);

  /* sync to localStorage */
  useEffect(() => {
    saveToStorage(notifications);
  }, [notifications]);

  const addNotification = useCallback(
    (n: Omit<AppNotification, "id" | "created_at" | "read">) => {
      const item: AppNotification = {
        ...n,
        id: generateId(),
        created_at: new Date().toISOString(),
        read: false,
      };
      setNotifications((prev) => [item, ...prev].slice(0, 50));
    },
    []
  );

  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  /* expose global imperative API */
  useEffect(() => {
    globalNotify = addNotification;
    return () => {
      globalNotify = null;
    };
  }, [addNotification]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <NotificationContext.Provider
      value={{
        notifications,
        unreadCount,
        addNotification,
        markAsRead,
        markAllAsRead,
        removeNotification,
        clearAll,
      }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error("useNotification must be used within a NotificationProvider");
  }
  return ctx;
}

/* ------------------------------------------------------------------ */
/*  Icon helper                                                         */
/* ------------------------------------------------------------------ */

function typeIcon(type: NotificationType) {
  switch (type) {
    case "success":
      return <CheckCircle2 size={18} className="text-latte-success" />;
    case "warning":
      return <AlertTriangle size={18} className="text-latte-warning" />;
    case "error":
      return <AlertCircle size={18} className="text-latte-critical" />;
    default:
      return <Info size={18} className="text-latte-info" />;
  }
}

function typeBg(type: NotificationType) {
  switch (type) {
    case "success":
      return "bg-latte-success/10";
    case "warning":
      return "bg-latte-warning/10";
    case "error":
      return "bg-latte-critical/10";
    default:
      return "bg-latte-info/10";
  }
}

function categoryLabel(c: NotificationCategory) {
  const map: Record<string, string> = {
    system: "系统",
    review: "审查",
    project: "项目",
    prompt: "提示词",
    sync: "同步",
  };
  return map[c] || c;
}

/* ------------------------------------------------------------------ */
/*  Single item                                                         */
/* ------------------------------------------------------------------ */

function NotificationItem({
  item,
  onRead,
  onRemove,
}: {
  item: AppNotification;
  onRead: (id: string) => void;
  onRemove: (id: string) => void;
}) {
  const router = useRouter();

  function handleClick() {
    if (!item.read) onRead(item.id);
    if (item.action_url) {
      router.push(item.action_url);
    }
  }

  const timeAgo = formatTimeAgo(item.created_at);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.2 }}
      className={`group relative flex gap-3 p-3 rounded-latte-lg cursor-pointer transition-colors ${
        item.read
          ? "hover:bg-latte-bg-tertiary/50"
          : "bg-latte-bg-tertiary/30 hover:bg-latte-bg-tertiary/60"
      }`}
      onClick={handleClick}
    >
      {!item.read && (
        <span className="absolute top-3 right-3 h-2 w-2 rounded-full bg-latte-primary" />
      )}
      <div className={`flex-shrink-0 h-9 w-9 rounded-latte-md flex items-center justify-center ${typeBg(item.type)}`}>
        {typeIcon(item.type)}
      </div>
      <div className="flex-1 min-w-0 pr-5">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium text-latte-text-tertiary">
            {categoryLabel(item.category)}
          </span>
          <span className="text-xs text-latte-text-quaternary">·</span>
          <span className="text-xs text-latte-text-quaternary">{timeAgo}</span>
        </div>
        <p className="text-sm font-medium text-latte-text-primary leading-snug">{item.title}</p>
        <p className="text-xs text-latte-text-secondary mt-0.5 line-clamp-2">{item.message}</p>
        {item.action_url && (
          <div className="flex items-center gap-1 mt-1 text-xs text-latte-primary">
            <span>查看详情</span>
            <ChevronRight size={12} />
          </div>
        )}
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onRemove(item.id);
        }}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-latte-bg-tertiary"
      >
        <X size={12} className="text-latte-text-tertiary" />
      </button>
    </motion.div>
  );
}

function formatTimeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "刚刚";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} 天前`;
  return new Date(iso).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

/* ------------------------------------------------------------------ */
/*  Panel                                                               */
/* ------------------------------------------------------------------ */

export function NotificationPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
  } = useNotification();

  const panelRef = useRef<HTMLDivElement>(null);

  /* click outside to close */
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    if (open) {
      document.addEventListener("mousedown", handler);
      return () => document.removeEventListener("mousedown", handler);
    }
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={panelRef}
          initial={{ opacity: 0, y: -8, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -8, scale: 0.96 }}
          transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
          className="absolute right-0 top-full mt-2 w-96 max-w-[calc(100vw-2rem)] bg-latte-bg-primary border border-latte-text-primary/10 rounded-latte-xl shadow-2xl shadow-black/10 backdrop-blur-xl z-50 overflow-hidden"
        >
          {/* header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-latte-text-primary/5">
            <div className="flex items-center gap-2">
              <Bell size={16} className="text-latte-text-secondary" />
              <span className="text-sm font-semibold text-latte-text-primary">通知</span>
              {unreadCount > 0 && (
                <span className="px-1.5 py-0.5 rounded-full bg-latte-primary/10 text-latte-primary text-xs font-medium">
                  {unreadCount}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  onClick={markAllAsRead}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-latte-text-secondary hover:text-latte-text-primary hover:bg-latte-bg-tertiary rounded-latte-md transition-colors"
                  title="全部已读"
                >
                  <CheckCheck size={13} />
                  全部已读
                </button>
              )}
              {notifications.length > 0 && (
                <button
                  onClick={clearAll}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-latte-text-secondary hover:text-latte-critical hover:bg-latte-critical/10 rounded-latte-md transition-colors"
                  title="清空"
                >
                  <Trash2 size={13} />
                  清空
                </button>
              )}
            </div>
          </div>

          {/* list */}
          <div className="max-h-[28rem] overflow-y-auto p-2 space-y-1">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-10 text-latte-text-tertiary">
                <Bell size={32} className="mb-2 opacity-30" />
                <p className="text-sm">暂无通知</p>
                <p className="text-xs mt-1 opacity-60">系统事件、审查结果将在这里显示</p>
              </div>
            ) : (
              <AnimatePresence mode="popLayout">
                {notifications.map((n) => (
                  <NotificationItem
                    key={n.id}
                    item={n}
                    onRead={markAsRead}
                    onRemove={removeNotification}
                  />
                ))}
              </AnimatePresence>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
