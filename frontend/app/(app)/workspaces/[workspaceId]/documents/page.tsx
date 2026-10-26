import type { Metadata } from "next";
import { WorkspaceView } from "@/components/features/workspace/workspace-view";

export const metadata: Metadata = { title: "Ingestion Pipeline & Chunker · AURORA" };

export default async function WorkspaceDocumentsPage({
  params,
  searchParams,
}: {
  params: Promise<{ workspaceId: string }>;
  searchParams: Promise<{ conversation?: string; document?: string; page?: string }>;
}) {
  const { workspaceId } = await params;
  const query = await searchParams;
  const parsedPage = Number.parseInt(query.page || "1", 10);

  return (
    <WorkspaceView
      key={workspaceId}
      workspaceId={workspaceId}
      initialView="documents"
      initialConversationId={query.conversation}
      initialDocumentId={query.document}
      initialPage={Number.isFinite(parsedPage) && parsedPage > 0 ? parsedPage : 1}
    />
  );
}
