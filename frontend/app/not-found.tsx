import Link from "next/link";
import { ArrowLeft, FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div
      style={{
        minHeight: "70vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "2rem",
      }}
    >
      <div
        style={{
          width: "64px",
          height: "64px",
          borderRadius: "50%",
          background: "var(--accent-soft)",
          color: "var(--accent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "1.5rem",
        }}
      >
        <FileQuestion size={32} />
      </div>
      <h1 style={{ fontSize: "2rem", fontWeight: 800, margin: "0 0 0.5rem", color: "var(--foreground)" }}>Page Not Found</h1>
      <p style={{ color: "var(--foreground-soft)", maxWidth: "440px", margin: "0 0 1.5rem" }}>
        The research page or workspace you requested does not exist or has been moved.
      </p>
      <Link href="/">
        <Button leftIcon={<ArrowLeft size={16} />}>Return Home</Button>
      </Link>
    </div>
  );
}
