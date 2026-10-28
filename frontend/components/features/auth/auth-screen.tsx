"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, ArrowLeft, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Brand } from "@/components/shared/brand";
import { api, ApiError } from "@/lib/api";

export function AuthScreen({ initialMode = "login" }: { initialMode?: "login" | "register" } = {}) {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [infoMessage, setInfoMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showResetHint, setShowResetHint] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    let cancelled = false;

    // Check if user already has an active session to prevent screen flash
    api.me()
      .then((user) => {
        if (!cancelled && user) {
          router.replace("/workspaces");
        }
      })
      .catch(() => {
        // Not authenticated, stay on login page
      });

    api.authProviders()
      .then((data) => {
        if (!cancelled) setGoogleEnabled(Boolean(data?.google?.enabled));
      })
      .catch(() => {
        if (!cancelled) setGoogleEnabled(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setInfoMessage("");

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setError("Please enter your email address.");
      return;
    }

    if (mode === "register") {
      const finalDisplayName = displayName.trim() || trimmedEmail.split("@")[0];
      if (password.length < 8) {
        setError("Password must be at least 8 characters long.");
        return;
      }

      setBusy(true);
      try {
        await api.register(trimmedEmail, password, finalDisplayName);
        // Automatically establish session cookie
        try {
          await api.login(trimmedEmail, password);
          router.push("/workspaces");
        } catch {
          // If auto-login fails, smoothly transition to login tab with confirmation
          setMode("login");
          setInfoMessage("Account created successfully! Please sign in with your password.");
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Registration failed. Please check your inputs and try again.");
        }
      } finally {
        setBusy(false);
      }
    } else {
      setBusy(true);
      try {
        await api.login(trimmedEmail, password);
        router.push("/workspaces");
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.message);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Sign in failed. Please check your email and password.");
        }
      } finally {
        setBusy(false);
      }
    }
  };

  return (
    <main
      style={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem 1.5rem",
        background: "var(--background)",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "400px",
          display: "flex",
          flexDirection: "column",
          gap: "1.25rem",
        }}
      >
        {/* Header */}
        <div style={{ textAlign: "center" }}>
          <Link href="/" style={{ display: "inline-block", marginBottom: "1.25rem" }}>
            <Brand />
          </Link>
          <h1
            style={{
              fontSize: "1.35rem",
              fontWeight: 700,
              margin: "0 0 0.35rem",
              color: "var(--foreground)",
            }}
          >
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          <p
            style={{
              fontSize: "0.85rem",
              color: "var(--foreground-soft)",
              margin: 0,
            }}
          >
            {mode === "login"
              ? "Sign in to access your research workspaces."
              : "Get started with AURORA — research with cited evidence."}
          </p>
        </div>

        {/* Form Card */}
        <div
          style={{
            background: "var(--surface)",
            borderRadius: "var(--radius-md)",
            padding: "1.5rem",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {/* Mode Tabs */}
          <div
            style={{
              display: "flex",
              background: "var(--surface-raised)",
              padding: "0.25rem",
              borderRadius: "var(--radius-sm)",
              marginBottom: "1.25rem",
            }}
          >
            <button
              type="button"
              onClick={() => { setMode("login"); setError(""); setInfoMessage(""); }}
              style={{
                flex: 1,
                border: "none",
                padding: "0.45rem 0.75rem",
                borderRadius: "4px",
                fontSize: "0.84rem",
                fontWeight: 600,
                cursor: "pointer",
                background: mode === "login" ? "var(--surface)" : "transparent",
                color: mode === "login" ? "var(--foreground)" : "var(--muted)",
                boxShadow: mode === "login" ? "var(--shadow-sm)" : "none",
                transition: "all 0.15s ease",
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode("register"); setError(""); setInfoMessage(""); }}
              style={{
                flex: 1,
                border: "none",
                padding: "0.45rem 0.75rem",
                borderRadius: "4px",
                fontSize: "0.84rem",
                fontWeight: 600,
                cursor: "pointer",
                background: mode === "register" ? "var(--surface)" : "transparent",
                color: mode === "register" ? "var(--foreground)" : "var(--muted)",
                boxShadow: mode === "register" ? "var(--shadow-sm)" : "none",
                transition: "all 0.15s ease",
              }}
            >
              Create Account
            </button>
          </div>

          {/* Info Banner */}
          {infoMessage && (
            <div
              role="status"
              style={{
                background: "var(--success-soft)",
                border: "1px solid color-mix(in srgb, var(--success) 30%, transparent)",
                borderRadius: "var(--radius-sm, 6px)",
                padding: "0.65rem 0.85rem",
                marginBottom: "1rem",
                fontSize: "0.82rem",
                color: "var(--success)",
              }}
            >
              {infoMessage}
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div
              role="alert"
              style={{
                background: "var(--danger-soft)",
                border: "1px solid color-mix(in srgb, var(--danger) 30%, transparent)",
                borderRadius: "var(--radius-sm, 6px)",
                padding: "0.65rem 0.85rem",
                marginBottom: "1rem",
                fontSize: "0.82rem",
                color: "var(--danger)",
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {mode === "register" && (
              <div>
                <label
                  htmlFor="displayName"
                  style={{
                    display: "block",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    marginBottom: "0.35rem",
                    color: "var(--foreground)",
                  }}
                >
                  Display Name
                </label>
                <input
                  id="displayName"
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g. Dr. Jane Smith"
                  className="input"
                  style={{ fontSize: "0.88rem" }}
                />
              </div>
            )}

            <div>
              <label
                htmlFor="email"
                style={{
                  display: "block",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  marginBottom: "0.35rem",
                  color: "var(--foreground)",
                }}
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input"
                style={{ fontSize: "0.88rem" }}
              />
            </div>

            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "0.35rem" }}>
                <label
                  htmlFor="password"
                  style={{
                    display: "block",
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    color: "var(--foreground)",
                  }}
                >
                  Password
                </label>
                {mode === "register" ? (
                  <span style={{ fontSize: "0.74rem", color: "var(--muted)" }}>
                    Min. 8 characters
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowResetHint(!showResetHint)}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      fontSize: "0.75rem",
                      color: "var(--accent)",
                      cursor: "pointer",
                      textDecoration: "underline",
                    }}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <div style={{ position: "relative" }}>
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={mode === "register" ? 8 : undefined}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input"
                  style={{ fontSize: "0.88rem", paddingRight: "2.5rem" }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  style={{
                    position: "absolute",
                    right: "0.75rem",
                    top: "50%",
                    transform: "translateY(-50%)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    color: "var(--muted)",
                    display: "flex",
                    alignItems: "center",
                    padding: 0,
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {showResetHint && mode === "login" && (
                <p
                  style={{
                    margin: "0.5rem 0 0",
                    fontSize: "0.78rem",
                    color: "var(--foreground-soft)",
                    background: "var(--surface-raised)",
                    padding: "0.5rem 0.75rem",
                    borderRadius: "6px",
                    border: "1px solid var(--border)",
                  }}
                >
                  Contact your workspace administrator to reset your password.
                </p>
              )}
            </div>

            <Button
              type="submit"
              variant="primary"
              size="md"
              busy={busy}
              rightIcon={<ArrowRight size={16} />}
              style={{ marginTop: "0.25rem" }}
            >
              {mode === "login" ? "Sign In" : "Create Account"}
            </Button>
          </form>

          {googleEnabled && (
            <>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  margin: "1.25rem 0",
                  color: "var(--muted)",
                  fontSize: "0.78rem",
                }}
              >
                <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
                <span>or continue with</span>
                <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
              </div>
              <a
                href="/api/v1/auth/google/authorize"
                className="button button-secondary"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.5rem",
                  textDecoration: "none",
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                Google
              </a>
            </>
          )}
        </div>

        {/* Back link */}
        <div style={{ textAlign: "center" }}>
          <Link
            href="/"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.35rem",
              fontSize: "0.82rem",
              color: "var(--muted, #8E93B0)",
              textDecoration: "none",
            }}
          >
            <ArrowLeft size={14} />
            Back to home
          </Link>
        </div>
      </div>
    </main>
  );
}
