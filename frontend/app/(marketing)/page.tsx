"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  BookOpenText,
  Languages,
  ShieldCheck,
  FileSpreadsheet,
  Zap,
  Lock,
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
          <Badge variant="purple">
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
          <span
            style={{
              background: "linear-gradient(135deg, var(--accent, #6C5CE7), var(--teal, #00D2D3))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Get cited answers.
          </span>
        </h1>

        <p
          style={{
            fontSize: "clamp(1.05rem, 2vw, 1.2rem)",
            color: "var(--foreground-soft, #4A4F6A)",
            maxWidth: "640px",
            margin: "0 auto 2rem",
            lineHeight: 1.6,
          }}
        >
          Upload PDFs, DOCX, XLSX, and PPTX files. Query in English or Hindi. 
          Every answer traces back to the exact page and paragraph in your source documents.
        </p>

        <div
          style={{
            display: "flex",
            gap: "0.75rem",
            justifyContent: "center",
            flexWrap: "wrap",
            marginBottom: "3rem",
          }}
        >
          <Link href="/register">
            <Button size="lg" rightIcon={<ArrowRight size={18} />}>
              Get Started
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="secondary" size="lg">
              Sign In
            </Button>
          </Link>
        </div>

        {/* Trust indicators — simple, honest */}
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            gap: "2rem",
            flexWrap: "wrap",
            fontSize: "0.85rem",
            color: "var(--muted, #8E93B0)",
          }}
        >
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <ShieldCheck size={16} color="var(--teal, #00D2D3)" />
            Every claim cited
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Languages size={16} color="var(--accent, #6C5CE7)" />
            English & Hindi
          </span>
          <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Lock size={16} color="var(--coral, #FF6B6B)" />
            Private workspaces
          </span>
        </div>
      </section>

      {/* ── How It Works ─────────────────────────────────────── */}
      <section
        style={{
          marginBottom: "4rem",
          background: "var(--surface, #FFFFFF)",
          padding: "2.5rem 2rem",
          borderRadius: "var(--radius-xl, 24px)",
          border: "1px solid var(--border, #E2E5F0)",
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <h2 style={{ fontSize: "1.75rem", fontWeight: 700, margin: "0 0 0.5rem", color: "var(--foreground, #1A1D2E)" }}>
            How It Works
          </h2>
          <p style={{ color: "var(--foreground-soft, #4A4F6A)", maxWidth: "480px", margin: "0 auto", fontSize: "0.95rem" }}>
            Three steps from raw documents to verified, cited research answers.
          </p>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
            gap: "2rem",
          }}
        >
          {/* Step 1 */}
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: "var(--radius-md, 12px)",
                background: "var(--accent-soft, #EDE9FE)",
                color: "var(--accent, #6C5CE7)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 1rem",
              }}
            >
              <Upload size={24} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              1. Upload Documents
            </h3>
            <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft, #4A4F6A)", lineHeight: 1.55, margin: 0 }}>
              Drag and drop PDFs, Word documents, Excel spreadsheets, or PowerPoint decks into your private workspace.
            </p>
          </div>

          {/* Step 2 */}
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: "var(--radius-md, 12px)",
                background: "var(--teal-soft, #E0FAFA)",
                color: "var(--teal, #00D2D3)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 1rem",
              }}
            >
              <MessageSquareText size={24} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              2. Ask Questions
            </h3>
            <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft, #4A4F6A)", lineHeight: 1.55, margin: 0 }}>
              Ask in English or Hindi. AURORA searches across all your uploaded documents to find the most relevant passages.
            </p>
          </div>

          {/* Step 3 */}
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: "var(--radius-md, 12px)",
                background: "var(--coral-soft, #FFF0F0)",
                color: "var(--coral, #FF6B6B)",
                display: "grid",
                placeItems: "center",
                margin: "0 auto 1rem",
              }}
            >
              <FileCheck2 size={24} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              3. Get Cited Answers
            </h3>
            <p style={{ fontSize: "0.88rem", color: "var(--foreground-soft, #4A4F6A)", lineHeight: 1.55, margin: 0 }}>
              Receive synthesized answers with inline citations. Click any citation to see the exact source passage and page.
            </p>
          </div>
        </div>
      </section>

      {/* ── Features Grid ────────────────────────────────────── */}
      <section style={{ marginBottom: "4rem" }}>
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <h2 style={{ fontSize: "1.75rem", fontWeight: 700, margin: "0 0 0.5rem", color: "var(--foreground, #1A1D2E)" }}>
            Built for Serious Research
          </h2>
          <p style={{ color: "var(--foreground-soft, #4A4F6A)", maxWidth: "520px", margin: "0 auto", fontSize: "0.95rem" }}>
            Every feature is designed to make document research faster, more accurate, and verifiable.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.25rem" }}>
          <Card gradientTop radius="xl" style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                background: "var(--accent-soft, #EDE9FE)",
                color: "var(--accent, #6C5CE7)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
              }}
            >
              <FileSpreadsheet size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              Multi-Format Support
            </h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              PDF, DOCX, XLSX, and PPTX. Tables, charts, and multi-column layouts are preserved during ingestion.
            </p>
            <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
              <Badge variant="purple">PDF</Badge>
              <Badge variant="teal">XLSX</Badge>
              <Badge variant="coral">DOCX</Badge>
              <Badge variant="amber">PPTX</Badge>
            </div>
          </Card>

          <Card gradientTop radius="xl" style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                background: "var(--teal-soft, #E0FAFA)",
                color: "var(--teal, #00D2D3)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
              }}
            >
              <Languages size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              Bilingual Research
            </h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Ask in Hindi, get answers from English documents — or the other way around. Cross-lingual retrieval with no semantic loss.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="teal">English</Badge>
              <Badge variant="purple">हिन्दी</Badge>
            </div>
          </Card>

          <Card gradientTop radius="xl" style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                background: "var(--coral-soft, #FFF0F0)",
                color: "var(--coral, #FF6B6B)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
              }}
            >
              <BookOpenText size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              Page-Level Citations
            </h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Every answer includes clickable citations pointing to the exact document, page, and paragraph. Verify instantly.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="coral">Source Tracing</Badge>
              <Badge variant="neutral">Page & Section</Badge>
            </div>
          </Card>

          <Card gradientTop radius="xl" style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                background: "var(--amber-soft, #FFF9E6)",
                color: "#D48806",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
              }}
            >
              <Zap size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              Fast Retrieval
            </h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Vector similarity search combined with keyword matching ensures fast, relevant results across large document collections.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="amber">Vector Search</Badge>
              <Badge variant="neutral">Keyword Ranking</Badge>
            </div>
          </Card>

          <Card gradientTop radius="xl" style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                background: "var(--pink-soft, #FFF0FC)",
                color: "var(--pink, #FF9FF3)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
              }}
            >
              <ShieldCheck size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              Grounded Answers
            </h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Answers are tied directly to your uploaded documents. Claims without supporting evidence are flagged, not fabricated.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="pink">Grounded</Badge>
              <Badge variant="neutral">Evidence-Only</Badge>
            </div>
          </Card>

          <Card gradientTop radius="xl" style={{ padding: "1.5rem" }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "10px",
                background: "var(--surface-raised, #F5F7FC)",
                color: "var(--foreground, #1A1D2E)",
                display: "grid",
                placeItems: "center",
                marginBottom: "1rem",
              }}
            >
              <Lock size={20} />
            </div>
            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, margin: "0 0 0.4rem" }}>
              Private Workspaces
            </h3>
            <p style={{ color: "var(--foreground-soft, #4A4F6A)", margin: "0 0 0.75rem", lineHeight: 1.55, fontSize: "0.88rem" }}>
              Your documents stay in isolated workspaces. Built-in access control keeps sensitive research secure.
            </p>
            <div style={{ display: "flex", gap: "0.35rem" }}>
              <Badge variant="neutral">Workspace Isolation</Badge>
              <Badge variant="purple">Access Control</Badge>
            </div>
          </Card>
        </div>
      </section>

      {/* ── CTA Section ──────────────────────────────────────── */}
      <section
        style={{
          background: "linear-gradient(135deg, var(--accent, #6C5CE7), var(--accent-strong, #5A4BD1))",
          color: "#ffffff",
          borderRadius: "var(--radius-xl, 24px)",
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
              style={{ fontWeight: 700 }}
            >
              Create Free Account
            </Button>
          </Link>
          <Link href="/login">
            <Button
              size="lg"
              variant="outline"
              style={{ borderColor: "rgba(255,255,255,0.5)", color: "#ffffff" }}
            >
              Sign In
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}
