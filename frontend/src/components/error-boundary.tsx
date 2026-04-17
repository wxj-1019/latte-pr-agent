"use client";

import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.error("ErrorBoundary caught an error:", error, errorInfo);
    }
    // In production, you could send this to an error tracking service like Sentry
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="min-h-screen flex items-center justify-center bg-latte-bg-primary text-latte-text-primary p-6">
          <div className="max-w-md w-full text-center space-y-4">
            <h2 className="text-xl font-semibold">Something went wrong</h2>
            <p className="text-sm text-latte-text-secondary">
              An unexpected error occurred. Please refresh the page or try again later.
            </p>
            {process.env.NODE_ENV === "development" && this.state.error && (
              <pre className="text-left text-xs bg-latte-bg-secondary p-4 rounded-latte-md overflow-auto text-latte-text-tertiary">
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center justify-center px-4 py-2 rounded-latte-md bg-latte-gold text-latte-bg-primary font-medium text-sm hover:bg-latte-gold/90 transition-colors"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
