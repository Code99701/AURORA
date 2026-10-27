"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { WorkspaceDashboard } from "@/components/features/workspace/workspace-dashboard";
import { PageSkeleton } from "@/components/ui/skeleton";

function WorkspacesRedirector() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const manageMode = searchParams.get("manage") === "true";
  const [showDashboard, setShowDashboard] = useState(false);
  const isShowingDashboard = manageMode || showDashboard;


  useEffect(() => {
    if (manageMode) {
      return;
    }

    let cancelled = false;
    api.workspaces()
      .then(async (data) => {
        if (cancelled) return;
        if (data.items && data.items.length > 0) {
          const savedId = typeof window !== "undefined" ? localStorage.getItem("aurora-active-workspace") : null;
          const target = data.items.find((w) => w.id === savedId) || data.items[0];
          router.replace(`/workspaces/${target.id}`);
        } else {
          try {
            const created = await api.createWorkspace("My Space", "Primary research workspace");
            if (!cancelled) {
              router.replace(`/workspaces/${created.id}`);
            }
          } catch {
            if (!cancelled) setShowDashboard(true);
          }
        }
      })
      .catch(() => {
        if (!cancelled) setShowDashboard(true);
      });

    return () => {
      cancelled = true;
    };
  }, [manageMode, router]);

  if (isShowingDashboard) {
    return <WorkspaceDashboard />;
  }


  return <PageSkeleton />;
}

export default function WorkspacesPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <WorkspacesRedirector />
    </Suspense>
  );
}
