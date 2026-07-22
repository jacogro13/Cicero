import { useQuery } from "@tanstack/react-query";

import { getContent } from "../api/documents";
import { MarkdownModal } from "./MarkdownModal";

interface ContentPanelProps {
  documentId: string;
  title: string;
  onClose: () => void;
}

// Admin inspection of the extracted Markdown (GET /documents/{id}/content,
// ADR-019) — the internal text a reader never sees, shown here to verify that
// extraction produced sane content. Fetched on demand, rendered in the shared
// modal.
export function ContentPanel({ documentId, title, onClose }: ContentPanelProps) {
  const content = useQuery({
    queryKey: ["content", documentId],
    queryFn: () => getContent(documentId),
  });

  return (
    <MarkdownModal
      ariaLabel={`Extracted text of ${title}`}
      title={title}
      onClose={onClose}
      isLoading={content.isLoading}
      isError={content.isError}
      loadingLabel="Loading extracted text…"
      errorLabel="Could not load the extracted text."
      markdown={content.data}
    />
  );
}
