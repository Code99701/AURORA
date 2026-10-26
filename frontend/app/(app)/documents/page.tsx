"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useWorkspaces } from "@/hooks/use-workspaces";
import { PageSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { Files } from "lucide-react";
import Link from "next/link";

export default function DocumentsPage() {
  const router = useRouter();
  const { workspaces, loading } = useWorkspaces();

  useEffect(() => {
    if (!loading && workspaces.length > 0) {
      router.replace(`/workspaces/${workspaces[0].id}/documents`);
    }
  }, [loading, workspaces, router]);

  if (loading) {
    return <PageSkeleton />;
  }

  if (workspaces.length === 0) {
    return (
      <EmptyState
        icon={Files}
        title="No workspaces found"
        description="Documents belong to workspaces. Create or select a workspace to view and manage documents."
        action={
          <Link className="button button-primary" href="/workspaces">
            Go to Workspaces
          </Link>
        }
      />
    );
  }

  return <PageSkeleton />;
}
