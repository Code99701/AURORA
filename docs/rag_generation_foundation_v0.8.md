# AURORA RAG Generation Foundation v0.8

## Scope

v0.8 adds one-shot grounded answer generation to the authorized semantic
retrieval completed in v0.7. It preserves the direct two-step RAG architecture
and stops before persistent conversations, citation validation, and advanced
retrieval.

```text
Question
   ↓
Authorized Retrieval
   ↓
Context Builder
   ↓
Prompt Builder
   ↓
Gemini LLM
   ↓
Grounded Answer
   ↓
Server-Controlled Source References
```

## Orchestration

`POST /api/v1/workspaces/{workspace_id}/rag` is a thin authenticated route. The
RAG orchestrator coordinates the existing workspace-filtered retriever, evidence
threshold, context builder, prompt builder, generation provider, and source
assembly. It is intentionally one-shot but keeps these responsibilities separate
so conversation context can be introduced in a later milestone.

The LLM never authorizes data. Workspace membership is resolved before the
orchestrator runs, and v0.7 applies the workspace filter inside the pgvector SQL
query before context is constructed.

## Context construction

The context builder consumes only already-authorized `RetrievedChunk` values. It
does not query the database. Results retain relevance order and each serialized
evidence block includes:

- chunk ID
- document ID
- original filename
- page number
- cosine similarity
- chunk text

The default `RAG_CONTEXT_MAX_CHARACTERS=12000` provides a hard deterministic
serialized-context budget. Blocks are selected in retrieval order and the last
usable block may be truncated. Multi-document evidence is supported and remains
independently traceable.

## Grounding and prompt-injection boundary

The application sends system instructions separately from the user question and
retrieved evidence. Evidence is enclosed in `AUTHORIZED_EVIDENCE`, `EVIDENCE`,
and `UNTRUSTED_DOCUMENT_TEXT` delimiters. Document markup is escaped.

The system instruction requires answers to use only supplied evidence, prohibits
inventing missing facts, supplies an explicit insufficient-evidence response, and
states that commands or role changes contained in uploaded documents are data.
This establishes a strong instruction boundary, but prompt injection is not
claimed to be completely solved. Future evaluation should include adversarial
documents and model-specific safety testing.

The system prompt is internal and is never included in an API response.

## Insufficient evidence

The deterministic v0.8 policy requires at least one retrieved chunk with cosine
similarity at or above `RAG_MIN_SIMILARITY` (default `0.30`). Zero results, all
results below the threshold, or a context budget too small for any evidence
returns:

> I couldn't find enough information in your authorized documents to answer this reliably.

Gemini is not called in this path, sources are empty, and the system does not fall
back to model general knowledge. This threshold is a baseline for later RAG
evaluation rather than a calibrated confidence score.

## Gemini adapter

Generation uses a small provider-neutral `LLMProvider` interface returning a
normalized `GenerationResult`. The production adapter calls Gemini's documented
`generateContent` REST endpoint through the existing HTTP client.

The selected default is `gemini-3.6-flash`, configured independently through
`LLM_MODEL`. A configured model is never silently replaced if unavailable.
`GEMINI_API_KEY` is loaded by Pydantic settings from the private `.env` file and
is never sent to browsers, persisted, logged, documented, or included in errors.

Provider failures are reduced to safe categories:

- `LLM_CONFIGURATION_ERROR`
- `LLM_PROVIDER_ERROR`
- `LLM_RATE_LIMIT_ERROR`
- `RAG_RETRIEVAL_ERROR`

## Source references

Gemini produces only natural-language answer text. The server derives sources
directly from the exact context evidence and returns document ID, chunk ID,
filename, page number, and similarity. Model-generated identifiers cannot enter
the `sources` array. This is citation-ready provenance, not yet the persistent
response-to-citation subsystem.

## Multilingual preparation

The request accepts optional `answer_language`. When supplied, the prompt treats
it only as a language preference. Without it, Gemini is asked to answer in the
question's language. Original source filenames, text, identifiers, and page
metadata are preserved. Meaningful cross-language quality remains for the
dedicated multilingual evaluation milestone.

## Configuration

```env
GEMINI_API_KEY=
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.6-flash
LLM_MAX_OUTPUT_TOKENS=1024
RAG_CONTEXT_MAX_CHARACTERS=12000
RAG_MIN_SIMILARITY=0.30
```

The blank key line above documents only the variable name. Real credentials must
remain in `.env`, which is Git-ignored.

## Testing and cost control

Automated tests override both embedding and LLM dependencies with deterministic
fakes. They perform no network requests and consume no Gemini quota.

One explicit integration test exercises the real configured Gemini adapter:

```powershell
cd backend
$env:AURORA_RUN_REAL_GEMINI_TEST="1"
.\aurora-env\Scripts\python.exe -m pytest tests\test_rag_generation.py `
  -k real_gemini_generation_explicit_integration -q
```

Run it manually only when provider availability and quota consumption are
acceptable. The normal suite skips it.

No new paid infrastructure, queue, cache, orchestration framework, or vector
database was introduced.

## Limitations and deferred work

- Similarity threshold quality is not yet empirically calibrated.
- The model can still misunderstand or incompletely synthesize evidence.
- Prompt injection risk is reduced, not eliminated.
- Sources are response metadata, not persistent validated citations.
- There is no conversation history, streaming, reranking, hybrid search, query
  rewriting, agent workflow, OCR, frontend, or cloud-storage migration.

The next milestone is the dedicated Citations and Evidence Foundation v0.9.
