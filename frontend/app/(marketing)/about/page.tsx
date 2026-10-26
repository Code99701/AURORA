import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Layers, Cpu, ShieldAlert, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export const metadata: Metadata = {
  title: "About AURORA · Architecture & Mission",
  description: "Learn about AURORA's mission, high-assurance RAG pipeline, and multilingual evidence grounding.",
};

export default function AboutPage() {
  return (
    <div style={{ maxWidth: "960px", margin: "0 auto", padding: "3rem 1.5rem 5rem" }}>
      <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", marginBottom: "2rem", color: "var(--accent, #6C5CE7)", fontWeight: 500 }}>
        <ArrowLeft size={16} /> Back to Home
      </Link>

      <Badge variant="primary" icon={<Sparkles size={12} />} style={{ marginBottom: "1rem" }}>
        ABOUT THE PLATFORM
      </Badge>
      <h1 style={{ fontSize: "clamp(2rem, 4vw, 3rem)", fontWeight: 800, margin: "0 0 1rem", letterSpacing: "-0.02em" }}>
        Built for precision, truth, and transparency.
      </h1>
      <p style={{ fontSize: "var(--text-lg, 1.125rem)", color: "var(--foreground-soft, #4A4F6A)", lineHeight: 1.7, marginBottom: "3rem" }}>
        AURORA was created to solve the fundamental weakness of generic AI assistants: hallucination and lack of source traceability. When working with research papers, policy documents, legal statutes, and medical guidelines, an approximate answer is worse than no answer.
      </p>

      <div style={{ display: "grid", gap: "1.5rem", marginBottom: "3.5rem" }}>
        <Card elevated>
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{ color: "var(--accent, #6C5CE7)", marginTop: "0.2rem" }}>
              <Layers size={24} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700, margin: "0 0 0.5rem" }}>Multi-Stage Pipeline</h2>
              <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: 0, lineHeight: 1.6 }}>
                Documents undergo OCR, structural parsing, metadata extraction, hierarchical chunking, vector embedding generation, and high-assurance indexing into PostgreSQL with pgvector.
              </p>
            </div>
          </div>
        </Card>

        <Card elevated>
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{ color: "var(--teal, #00D2D3)", marginTop: "0.2rem" }}>
              <Cpu size={24} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700, margin: "0 0 0.5rem" }}>Cross-Lingual Embeddings</h2>
              <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: 0, lineHeight: 1.6 }}>
                Native vector representations align semantic meanings across languages. Ask questions in English against Hindi text or vice-versa with matched citations.
              </p>
            </div>
          </div>
        </Card>

        <Card elevated>
          <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{ color: "var(--coral, #FF6B6B)", marginTop: "0.2rem" }}>
              <ShieldAlert size={24} />
            </div>
            <div>
              <h2 style={{ fontSize: "1.2rem", fontWeight: 700, margin: "0 0 0.5rem" }}>Insufficient Evidence Refusal</h2>
              <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: 0, lineHeight: 1.6 }}>
                If retrieved chunks do not contain verifiable facts answering the user query, AURORA refuses to fabricate an answer and explicitly flags insufficient evidence.
              </p>
            </div>
          </div>
        </Card>
      </div>

      <div style={{ textAlign: "center", padding: "2.5rem", background: "var(--surface-raised, #F5F7FC)", borderRadius: "var(--radius-xl, 24px)" }}>
        <h2 style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0 0 0.75rem" }}>Ready to explore your documents?</h2>
        <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 1.5rem" }}>Start researching with full source verification today.</p>
        <Link href="/register">
          <Button size="lg">Get Started Free</Button>
        </Link>
      </div>
    </div>
  );
}
