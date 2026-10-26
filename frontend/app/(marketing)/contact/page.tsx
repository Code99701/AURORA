import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Mail, MessageSquare, Sparkles } from "lucide-react";
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
      <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", marginBottom: "2rem", color: "var(--accent, #6C5CE7)", fontWeight: 500 }}>
        <ArrowLeft size={16} /> Back to Home
      </Link>

      <Badge variant="primary" icon={<Sparkles size={12} />} style={{ marginBottom: "1rem" }}>
        GET IN TOUCH
      </Badge>
      <h1 style={{ fontSize: "clamp(2rem, 4vw, 2.75rem)", fontWeight: 800, margin: "0 0 1rem", letterSpacing: "-0.02em" }}>
        We’d love to hear from you.
      </h1>
      <p style={{ fontSize: "var(--text-base, 1rem)", color: "var(--foreground-soft, #4A4F6A)", lineHeight: 1.6, marginBottom: "2.5rem" }}>
        Have questions about deployment, multilingual performance, or custom document pipelines? Reach out and our engineering team will get back to you.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "2rem" }}>
        <Card elevated>
          <form style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
            <Input label="Your Name" placeholder="Jane Doe" required />
            <Input label="Email Address" type="email" placeholder="jane@example.com" required />
            <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              <label style={{ fontSize: "var(--text-sm, 0.875rem)", fontWeight: 600 }}>Message</label>
              <textarea
                rows={4}
                placeholder="How can we assist your research?"
                style={{
                  width: "100%",
                  padding: "0.75rem 0.95rem",
                  fontSize: "1rem",
                  borderRadius: "var(--radius-md, 12px)",
                  border: "1.5px solid var(--border, #E2E5F0)",
                  background: "var(--surface, #ffffff)",
                  color: "var(--foreground, #1A1D2E)",
                  fontFamily: "inherit",
                  resize: "vertical",
                }}
                required
              />
            </div>
            <Button type="button" size="md">Send Message</Button>
          </form>
        </Card>

        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <Card>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.5rem" }}>
              <Mail size={20} color="var(--accent, #6C5CE7)" />
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>Direct Support</h2>
            </div>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", fontSize: "0.9rem", margin: 0 }}>
              Email our core team for technical questions and workspace administration.
            </p>
          </Card>

          <Card>
            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.5rem" }}>
              <MessageSquare size={20} color="var(--teal, #00D2D3)" />
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700, margin: 0 }}>Community & Research</h2>
            </div>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", fontSize: "0.9rem", margin: 0 }}>
              Collaborating on multilingual benchmark datasets? We provide open test suites and evaluation protocols.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
