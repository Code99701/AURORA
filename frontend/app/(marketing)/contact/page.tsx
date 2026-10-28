import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Mail, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = {
  title: "Contact Us · AURORA",
  description: "Get in touch with the AURORA team for support, research collaborations, or enterprise inquiries.",
};

export default function ContactPage() {
  return (
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "3rem 1.5rem 5rem" }}>
      <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", marginBottom: "2rem", color: "var(--accent)", fontWeight: 500 }}>
        <ArrowLeft size={16} /> Back to Home
      </Link>

      <Badge variant="primary" style={{ marginBottom: "1rem" }}>
        GET IN TOUCH
      </Badge>
      <h1 style={{ fontSize: "clamp(2rem, 4vw, 2.75rem)", fontWeight: 800, margin: "0 0 1rem", letterSpacing: "-0.02em", color: "var(--foreground)" }}>
        We’d love to hear from you.
      </h1>
      <p style={{ fontSize: "var(--text-base, 1rem)", color: "var(--foreground-soft)", lineHeight: 1.6, marginBottom: "2.5rem" }}>
        Have questions about deployment, multilingual performance, or custom document pipelines? Reach out and our engineering team will get back to you.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "1.5rem" }}>
        <Card>
          <form style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <Input label="Your Name" placeholder="Jane Doe" required />
            <Input label="Email Address" type="email" placeholder="jane@example.com" required />
            <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <label style={{ fontSize: "var(--text-sm, 0.875rem)", fontWeight: 600, color: "var(--foreground)" }}>Message</label>
              <textarea
                rows={4}
                placeholder="How can we assist your research?"
                style={{
                  width: "100%",
                  padding: "0.75rem 0.95rem",
                  fontSize: "0.875rem",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border)",
                  background: "var(--surface)",
                  color: "var(--foreground)",
                  fontFamily: "inherit",
                  resize: "vertical",
                  outline: "none",
                }}
                required
              />
            </div>
            <Button type="button" size="md">Send Message</Button>
          </form>
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <Card>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.5rem" }}>
              <Mail size={18} color="var(--accent)" />
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Direct Support</h2>
            </div>
            <p style={{ color: "var(--foreground-soft)", fontSize: "0.875rem", margin: 0, lineHeight: 1.5 }}>
              Email our core team for technical questions and workspace administration.
            </p>
          </Card>

          <Card>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.5rem" }}>
              <MessageSquare size={18} color="var(--accent)" />
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, margin: 0, color: "var(--foreground)" }}>Community & Research</h2>
            </div>
            <p style={{ color: "var(--foreground-soft)", fontSize: "0.875rem", margin: 0, lineHeight: 1.5 }}>
              Collaborating on multilingual benchmark datasets? We provide open test suites and evaluation protocols.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
