import React from "react";
import { Navbar } from "@/components/layout/navbar";
import { Footer } from "@/components/layout/footer";

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", minHeight: "100dvh" }}>
      <Navbar />
      <main id="main-content" style={{ flex: 1 }}>
        {children}
      </main>
      <Footer />
    </div>
  );
}
