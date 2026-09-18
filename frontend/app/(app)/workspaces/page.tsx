import type { Metadata } from "next";
import { WorkspaceDashboard } from "@/components/workspace-dashboard";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return <WorkspaceDashboard />;
}
