import Link from "next/link";
import {
  FileSpreadsheet,
  Languages,
  BookOpenText,
  ShieldCheck,
  Zap,
  Lock,
  ArrowRight,
  Upload,
  MessageSquareText,
  FileCheck2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function LandingPage() {
  return (
    <div style={{ maxWidth: "1120px", margin: "0 auto", padding: "1.5rem 1.5rem 5rem" }}>

      {/* ── Hero Section ─────────────────────────────────────── */}
      <section style={{ textAlign: "center", padding: "3rem 1rem 4rem" }}>
        <div style={{ display: "inline-block", marginBottom: "1.25rem" }}>
          <Badge variant="primary">
            MULTILINGUAL RAG PLATFORM
          </Badge>
        </div>

        <h1
          className="hero-headline"
          style={{
            margin: "0 auto 1.25rem",
            maxWidth: "820px",
            fontSize: "clamp(2.2rem, 5vw, 3.5rem)",
            fontWeight: 800,
            lineHeight: 1.15,
            letterSpacing: "-0.03em",
          }}
        >
          Ask questions about your documents.{" "}
          <span style={{ color: "var(--accent)" }}>
            Get cited answers.
          </span>
        </h1>

        <p
          style={{
            fontSize: "clamp(1.05rem, 2vw, 1.2rem)",
            color: "var(--foreground-soft)",
            maxWidth: "640px",
            margin: "0 auto 2rem",
            lineHeight: 1.6,
          }}
        >
          Upload PDFs, spreadsheets, presentations, and documents. Ask questions in English or Hindi,
          and receive answers grounded in your evidence with page-level citations.
        </p>

        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap", marginBottom: "3rem" }}>
          <Link href="/register">
            <Button size="lg" variant="primary" rightIcon={<ArrowRight size={18} />}>
              Get Started Free
            </Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="secondary">
              Sign In
            </Button>
          </Link>
        </div>

        {/* Evidence Trust Badges */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "2rem",
            flexWrap: "wrap",
            fontSize: "0.85rem",
            color: "var(--muted)",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <ShieldCheck size={16} color="var(--accent)" />
            Every claim cited
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Languages size={16} color="var(--accent)" />
            English & Hindi
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Lock size={16} color="var(--foreground-soft)" />
            Private workspaces
          </span>
        </div>
      </section>

      {/* ── How It Works ─────────────────────────────────────── */}
      <section
        style={{
          marginBottom: "4rem",
          background: "var(--surface)",
          padding: "2.5rem 2rem",
          borderRadius: "var(--radius-lg, 12px)",
          border: "1px solid var(--border)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <h2 style={{ fontSize: "1.75rem", fontWeight: 700, margin: "0 0 0.5rem", color: "var(--foreground)" }}>
            How It Works
          </h2>
          <p style={{ color: "var(--foreground-soft)", margin: 0, fontSize: "0.95rem" }}>
            Three simple steps from raw documents to verifiable answers.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "2rem",
          }}
        >
          {/* Step 1 */}
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 1rem",
                border: "1px solid var(--border)",
              }}
            >
              <Upload size={22} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              1. Upload Evidence
            </h3>
            <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft)", lineHeight: 1.55, margin: 0 }}>
              Drag & drop PDFs, Word documents, Excel sheets, and PowerPoint decks into isolated research workspaces.
            </p>
          </div>

          {/* Step 2 */}
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 1rem",
                border: "1px solid var(--border)",
              }}
            >
              <MessageSquareText size={22} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              2. Ask Questions
            </h3>
            <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft)", lineHeight: 1.55, margin: 0 }}>
              Ask in English or Hindi. AURORA searches across all your uploaded documents to find the most relevant passages.
            </p>
          </div>

          {/* Step 3 */}
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: "var(--radius-md, 8px)",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 1rem",
                border: "1px solid var(--border)",
              }}
            >
              <FileCheck2 size={22} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              3. Get Cited Answers
            </h3>
            <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft)", lineHeight: 1.55, margin: 0 }}>
              Receive synthesized answers with inline citations. Click any citation to see the exact source passage and page.
            </p>
          </div>
        </div>
      </section>

      {/* ── Features Grid ────────────────────────────────────── */}
      <section style={{ marginBottom: "4rem" }}>
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <h2 style={{ fontSize: "1.75rem", fontWeight: 700, margin: "0 0 0.5rem", color: "var(--foreground)" }}>
            Engineered for Precision Research
          </h2>
          <p style={{ color: "var(--foreground-soft)", margin: 0, fontSize: "0.95rem" }}>
            Built from the ground up for strict evidence fidelity and zero hallucinations.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "1.5rem",
          }}
        >
          <Card style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "8px",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
                border: "1px solid var(--border)",
              }}
            >
              <FileSpreadsheet size={18} />
            </div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.4rem" }}>
              Multi-Format Support
            </h3>
            <p style={{ color: "var(--foreground-soft)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              PDF, DOCX, XLSX, and PPTX. Tables, charts, and multi-column layouts are preserved during ingestion.
            </p>
            <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
              <Badge variant="neutral">PDF</Badge>
              <Badge variant="neutral">XLSX</Badge>
              <Badge variant="neutral">DOCX</Badge>
              <Badge variant="neutral">PPTX</Badge>
            </div>
          </Card>

          <Card style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "8px",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
                border: "1px solid var(--border)",
              }}
            >
              <Languages size={18} />
            </div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.4rem" }}>
              Bilingual Research
            </h3>
            <p style={{ color: "var(--foreground-soft)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Ask in Hindi, get answers from English documents — or the other way around. Cross-lingual retrieval with no semantic loss.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="neutral">English</Badge>
              <Badge variant="neutral">हिन्दी</Badge>
            </div>
          </Card>

          <Card style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "8px",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
                border: "1px solid var(--border)",
              }}
            >
              <BookOpenText size={18} />
            </div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.4rem" }}>
              Page-Level Citations
            </h3>
            <p style={{ color: "var(--foreground-soft)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Every answer includes clickable citations pointing to the exact document, page, and paragraph. Verify instantly.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="primary">Source Tracing</Badge>
              <Badge variant="neutral">Page & Section</Badge>
            </div>
          </Card>

          <Card style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "8px",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
                border: "1px solid var(--border)",
              }}
            >
              <Zap size={18} />
            </div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.4rem" }}>
              Fast Retrieval
            </h3>
            <p style={{ color: "var(--foreground-soft)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Vector similarity search combined with keyword matching ensures fast, relevant results across large document collections.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="primary">Vector Search</Badge>
              <Badge variant="neutral">Keyword Ranking</Badge>
            </div>
          </Card>

          <Card style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "8px",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
                border: "1px solid var(--border)",
              }}
            >
              <ShieldCheck size={18} />
            </div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.4rem" }}>
              Grounded Answers
            </h3>
            <p style={{ color: "var(--foreground-soft)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Answers are tied directly to your uploaded documents. Claims without supporting evidence are flagged, not fabricated.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="primary">Grounded</Badge>
              <Badge variant="neutral">Evidence-Only</Badge>
            </div>
          </Card>

          <Card style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "8px",
                background: "var(--surface-raised)",
                color: "var(--accent)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
                border: "1px solid var(--border)",
              }}
            >
              <Lock size={18} />
            </div>
            <h3 style={{ fontSize: "1.05rem", fontWeight: 600, margin: "0 0 0.4rem" }}>
              Private Workspaces
            </h3>
            <p style={{ color: "var(--foreground-soft)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Your documents stay in isolated workspaces. Built-in access control keeps sensitive research secure.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="neutral">Workspace Isolation</Badge>
              <Badge variant="neutral">Access Control</Badge>
            </div>
          </Card>
        </div>
      </section>

      {/* ── CTA Section ──────────────────────────────────────── */}
      <section
        style={{
          background: "var(--accent)",
          color: "#ffffff",
          borderRadius: "var(--radius-lg, 12px)",
          padding: "3.5rem 2rem",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            fontSize: "clamp(1.5rem, 3vw, 2.25rem)",
            fontWeight: 700,
            margin: "0 0 0.75rem",
            letterSpacing: "-0.02em",
          }}
        >
          Ready to research smarter?
        </h2>
        <p
          style={{
            fontSize: "1rem",
            opacity: 0.9,
            maxWidth: "500px",
            margin: "0 auto 2rem",
            lineHeight: 1.6,
          }}
        >
          Create a workspace, upload your documents, and start asking questions with verifiable, cited answers.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/register">
            <Button
              size="lg"
              variant="secondary"
              rightIcon={<ArrowRight size={18} />}
              style={{ fontWeight: 600 }}
            >
              Create Free Account
            </Button>
          </Link>
          <Link href="/login">
            <Button
              size="lg"
              variant="outline"
              style={{ borderColor: "rgba(255,255,255,0.6)", color: "#ffffff" }}
            >
              Sign In
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
