"use client";

import { ArrowRight, BookOpenText, Languages, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { oauthErrorMessage } from "@/lib/oauth-errors";
import { Brand } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import styles from "./auth-screen.module.css";

export function AuthScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [providerReady, setProviderReady] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    api.me().then(() => router.replace("/workspaces")).catch(() => undefined);
    api.authProviders()
      .then((providers) => setGoogleEnabled(providers.google.enabled))
      .catch(() => setGoogleEnabled(false))
      .finally(() => setProviderReady(true));

    const url = new URL(window.location.href);
    const oauthError = oauthErrorMessage(url.searchParams.get("oauth_error"));
    const errorTimer = oauthError
      ? window.setTimeout(() => {
          setError(oauthError);
          url.searchParams.delete("oauth_error");
          window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
        }, 0)
      : undefined;
    return () => {
      if (errorTimer !== undefined) window.clearTimeout(errorTimer);
    };
  }, [router]);

  function startGoogleSignIn() {
    setError("");
    setGoogleBusy(true);
    // OAuth requires a top-level document navigation so provider redirects and cookies work.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/api/v1/auth/google/authorize");
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "register") {
        await api.register(email, password, displayName);
      }
      await api.login(email, password);
      router.replace("/workspaces");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "AURORA could not sign you in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main-content" className={styles.shell}>
      <section className={styles.story} aria-labelledby="aurora-intro">
        <div className={styles.storyTop}><Brand /><ThemeToggle /></div>
        <div className={styles.storyBody}>
          <p className={styles.eyebrow}>Evidence-first research</p>
          <h1 id="aurora-intro">Find what your documents actually say.</h1>
          <p className={styles.lede}>
            A calm multilingual workspace for asking precise questions, tracing every answer,
            and returning to the source.
          </p>
          <div className={styles.principles}>
            <article><BookOpenText /><div><strong>Grounded answers</strong><span>Research from your indexed knowledge, not generic recall.</span></div></article>
            <article><ShieldCheck /><div><strong>Private by workspace</strong><span>Evidence is authorized before it reaches the research context.</span></div></article>
            <article><Languages /><div><strong>Cross-language discovery</strong><span>Ask in English or Hindi while preserving the original source.</span></div></article>
          </div>
        </div>
        <p className={styles.storyFooter}>AURORA · Multilingual RAG Platform</p>
      </section>

      <section className={styles.formPanel} aria-labelledby="auth-heading">
        <div className={styles.formWrap}>
          <p className={styles.eyebrow}>{mode === "login" ? "Welcome back" : "Create your research space"}</p>
          <h2 id="auth-heading">{mode === "login" ? "Continue to AURORA" : "Begin with evidence"}</h2>
          <p className={styles.formIntro}>
            {mode === "login" ? "Sign in to your private workspaces and sources." : "Create an account, then build your first knowledge workspace."}
          </p>
          <button
            className={`${styles.googleButton} button`}
            type="button"
            onClick={startGoogleSignIn}
            disabled={!providerReady || !googleEnabled || googleBusy || busy}
          >
            {googleBusy ? "Connecting to Google…" : "Continue with Google"}
          </button>
          {providerReady && !googleEnabled && (
            <p className={styles.providerNote}>Google sign-in is not configured yet. Email access remains available.</p>
          )}
          <div className={styles.divider} aria-hidden="true"><span>or continue with email</span></div>
          <form className={styles.form} onSubmit={submit}>
            {mode === "register" && (
              <div className="field">
                <label htmlFor="display-name">Display name</label>
                <input className="input" id="display-name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} minLength={1} maxLength={100} autoComplete="name" required />
              </div>
            )}
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input className="input" id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required />
            </div>
            <div className="field">
              <label htmlFor="password">Password</label>
              <input className="input" id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} maxLength={128} autoComplete={mode === "login" ? "current-password" : "new-password"} required />
              {mode === "register" && <p className="helper">Use 12–128 characters.</p>}
            </div>
            {error && <div className="error-banner" role="alert">{error}</div>}
            <button className="button button-primary" type="submit" disabled={busy || googleBusy}>
              {busy ? "Securing your session…" : mode === "login" ? "Sign in" : "Create account"}
              {!busy && <ArrowRight size={18} aria-hidden="true" />}
            </button>
          </form>
          <button className={`${styles.modeSwitch} button button-ghost`} type="button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "New to AURORA? Create an account" : "Already have an account? Sign in"}
          </button>
        </div>
      </section>
    </main>
  );
}
