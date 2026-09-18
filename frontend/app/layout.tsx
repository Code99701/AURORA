import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AURORA", template: "%s · AURORA" },
  description: "A multilingual, evidence-grounded research workspace.",
};

const themeScript = `
  try {
    const stored = localStorage.getItem('aurora-theme');
    const theme = stored || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    document.documentElement.dataset.theme = theme;
  } catch (_) { document.documentElement.dataset.theme = 'dark'; }
`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        {children}
      </body>
    </html>
  );
}
