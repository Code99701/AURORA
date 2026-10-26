"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error in component tree:", error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: undefined });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <section
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "3rem 1.5rem",
            textAlign: "center",
            gap: "1rem",
          }}
          role="alert"
        >
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "50%",
              background: "rgba(225, 112, 85, 0.12)",
              color: "var(--danger, #E17055)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <AlertTriangle size={24} />
          </div>
          <h2 style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700 }}>
            {this.props.fallbackTitle || "Something went wrong"}
          </h2>
          <p
            style={{
              margin: 0,
              maxWidth: "460px",
              color: "var(--foreground-soft, #4A4F6A)",
              fontSize: "0.95rem",
            }}
          >
            {this.props.fallbackMessage ||
              this.state.error?.message ||
              "An unexpected error occurred. Please try again."}
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={this.handleReset}
            leftIcon={<RefreshCw size={14} />}
          >
            Try again
          </Button>
        </section>
      );
    }

    return this.props.children;
  }
}
