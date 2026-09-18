# AURORA RAG Data Pipeline Foundation v0.7

## Scope

v0.7 turns the page-aware text produced by document processing into durable,
authorized retrieval data. It deliberately stops before answer generation.

The pipeline is:

`ExtractedPage -> deterministic chunks -> document embeddings -> pgvector -> workspace search`

## Chunking strategy

Each extracted page is chunked independently, so a chunk never crosses a page
boundary and its citation provenance remains exact. The baseline uses a maximum
of 1,000 characters with 150 characters of overlap. It prefers a paragraph,
sentence, newline, or whitespace boundary in the final 20% of a window and uses
the hard character boundary when none exists. Blank pages produce no chunks.

Both a document-wide `chunk_index` and page-local `page_chunk_index` are stored.
`approximate_token_count` is `ceil(character_count / 4)` and is only operational
metadata, not a claim about the provider tokenizer.

These values are intentionally simple and configurable. They provide a
deterministic, testable baseline that can be measured before more sophisticated
chunking is introduced.

## Embeddings

The provider-neutral `EmbeddingProvider` boundary separates indexing and query
embeddings. The production adapter calls Google's documented Gemini embedding
REST API through the existing HTTP client and uses `gemini-embedding-001`:

- document task type: `RETRIEVAL_DOCUMENT`
- query task type: `RETRIEVAL_QUERY`
- output dimension: 768
- vectors: explicitly L2-normalized before persistence/querying

Gemini supports multilingual inputs, making it a practical match for AURORA.
The dimension is fixed in both configuration validation and `vector(768)` so a
model/configuration mismatch fails before corrupting the index. The API key is
read from `GEMINI_API_KEY`; no credential is stored in source or the database.

Tests replace the production dependency with a deterministic local fake and do
not make paid or cloud calls.

## Indexing lifecycle

Document extraction and indexing have separate state machines. `PROCESSED`
continues to mean that page extraction succeeded, while indexing uses:

- `NOT_INDEXED`
- `INDEXING`
- `INDEXED`
- `FAILED`

`POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/index` requires
workspace membership and a processed document. A fingerprint covers page text,
chunk configuration, provider, model, and dimension. Repeating an unchanged
index request returns the existing index without another provider call.

When rebuilding, new embeddings are generated before old chunks are replaced in
one database transaction. A failed rebuild leaves no partially written index.
Reprocessing resets indexing metadata and deletion cascades from documents or
extracted pages to chunks.

## pgvector storage and retrieval

`document_chunks.embedding` is PostgreSQL `vector(768)`. v0.7 performs exact
cosine-distance search and deliberately creates no HNSW or IVFFlat index. Exact
search is the correct correctness baseline until corpus measurements justify an
approximate index.

`POST /api/v1/workspaces/{workspace_id}/search` accepts a nonblank query and
bounded `top_k` (default 5, maximum 20). It returns chunk/document IDs, safe
original filename, page number, text, and cosine similarity.

Authorization is enforced twice:

1. the route resolves an authenticated workspace member;
2. the SQL nearest-neighbor query filters `documents.workspace_id` and
   `documents.indexing_status = 'INDEXED'` before ordering and limiting.

No caller-supplied workspace or document metadata is trusted, and unauthorized
workspaces retain the existing concealed 404 behavior.

## Configuration

```env
GEMINI_API_KEY=
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSION=768
CHUNK_SIZE_CHARACTERS=1000
CHUNK_OVERLAP_CHARACTERS=150
RETRIEVAL_MAX_TOP_K=20
```

## Explicitly deferred

Answer generation, chat orchestration, LangChain/LangGraph, OCR, frontend work,
cloud storage migration, and approximate vector indexes are outside v0.7.
The next milestone is RAG Generation Foundation v0.8.
