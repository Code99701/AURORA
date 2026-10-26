export const APP_NAME = "AURORA";
export const APP_TAGLINE = "Multilingual Research & Evidence Platform";
export const APP_DESCRIPTION =
  "A multilingual, evidence-grounded research workspace for asking precise questions, tracing citations, and exploring documents across English and Hindi.";

export const THEME_KEY = "aurora-theme";
export const THEME_EVENT = "aurora-theme-change";

export const NAV_LINKS = [
  { href: "/", label: "Public Showcase" },
  { href: "/workspaces", label: "Workspaces" },
  { href: "/documents", label: "Ingestion Pipeline" },
] as const;

export const APP_NAV_LINKS = [
  { href: "/workspaces", label: "Workspaces", icon: "PanelsTopLeft" },
  { href: "/documents", label: "Ingestion Pipeline", icon: "FileUp" },
  { href: "/settings", label: "Settings", icon: "Settings" },
] as const;

export const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English", nativeName: "English" },
  { code: "hi", name: "Hindi", nativeName: "हिन्दी" },
] as const;
