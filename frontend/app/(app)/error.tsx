"use client";

import { AlertTriangle } from "lucide-react";

export default function ErrorBoundary({ reset }: { error: Error; reset: () => void }) {
  return (
    <section className="empty-state" role="alert">
      <span className="empty-icon"><AlertTriangle size={24} /></span>
      <h2>This research view could not load.</h2>
      <p>Your data is unchanged. Check the backend connection and try again.</p>
      <button className="button button-primary" onClick={reset}>Try again</button>
    </section>
  );
}
