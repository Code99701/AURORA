import type { Metadata } from "next";
import { WorkspaceView } from "@/components/workspace-view";

export const metadata: Metadata = { title: "Research workspace" };

export default async function WorkspacePage({
  params,
  searchParams,
}: {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ view?: string; conversation?: string; document?: string; page?: string }>;
}) {
  const { workspaceId } = await params;
  const query = await searchParams;
  const parsedPage = Number.parseInt(query.page || "1", 10);
  return <WorkspaceView key={workspaceId} workspaceId={workspaceId} initialView={query.view === "research" ? "research" : "documents"} initialConversationId={query.conversation} initialDocumentId={query.document} initialPage={Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1} />;
}
