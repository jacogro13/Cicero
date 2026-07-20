from cicero.domain.document.ports.document_summarizer import DocumentSummarizer


class MockSummarizer(DocumentSummarizer):
    """Self-contained default summarizer (ADR-016): a canned summary so the app
    summarises with zero external services. Any OpenAI-compatible endpoint replaces
    it behind the same port, no architecture change.
    """

    async def summarize(self, markdown: str) -> str:
        return "This is a mock summary of the document."
