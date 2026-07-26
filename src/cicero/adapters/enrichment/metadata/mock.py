from cicero.domain.document.ports.metadata_inferer import InferredMetadata, MetadataInferer


class MockMetadataInferer(MetadataInferer):
    """Self-contained default (ADR-028): infers nothing, calls no LLM.

    Covers still render from the PDF and a PDF's docinfo still fills author/year, so
    zero-config enrichment stays useful; an OpenAI-compatible adapter replaces this
    behind the same port when ``LLM_BASE_URL`` is set.
    """

    async def infer(self, text: str) -> InferredMetadata:
        return InferredMetadata()
