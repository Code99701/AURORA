from uuid import uuid4

from app.services.retrieval import RetrievedChunk, _diversify_candidates


def candidate(document_id, rank: int, text: str | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=document_id,
        filename=f"source-{document_id}.pdf",
        page_number=rank + 1,
        text=text or f"evidence {rank}",
        similarity=1.0 - rank / 100,
        locator={"v": 1, "type": "pdf_page", "page": rank + 1},
        extraction_method="NATIVE",
    )


def test_candidate_selection_represents_multiple_documents_before_extra_chunks():
    first = uuid4()
    second = uuid4()
    third = uuid4()
    ranked = [
        candidate(first, 0),
        candidate(first, 1),
        candidate(first, 2),
        candidate(second, 3),
        candidate(third, 4),
    ]

    selected = _diversify_candidates(ranked, top_k=3)

    assert [item.document_id for item in selected] == [first, second, third]
    assert selected[0].similarity == ranked[0].similarity


def test_duplicate_text_is_suppressed_only_within_the_same_document():
    first = uuid4()
    second = uuid4()
    ranked = [
        candidate(first, 0, "Repeated   Evidence"),
        candidate(first, 1, " repeated evidence "),
        candidate(second, 2, "Repeated Evidence"),
    ]

    selected = _diversify_candidates(ranked, top_k=3)

    assert len(selected) == 2
    assert {item.document_id for item in selected} == {first, second}
