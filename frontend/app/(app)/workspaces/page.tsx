import type { Metadata } from "next";
import { WorkspaceDashboard } from "@/components/features/workspace/workspace-dashboard";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return <WorkspaceDashboard />;
}
