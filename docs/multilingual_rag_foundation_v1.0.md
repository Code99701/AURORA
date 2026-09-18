# AURORA Multilingual RAG Foundation / Evaluation v1.0

## Implementation status

v1.0 validates technically meaningful cross-language RAG for English and Hindi
while preserving the existing v0.7-v0.9 architecture. No production schema,
embedding adapter, retrieval query, RAG endpoint, or citation model required a
change.

The validated flow is:

```text
Original-language document text
  -> Gemini RETRIEVAL_DOCUMENT embedding
  -> PostgreSQL vector(768)

Original user query in another language
  -> Gemini RETRIEVAL_QUERY embedding
  -> exact cosine retrieval
  -> original evidence text
  -> grounded answer in requested/query language
  -> citation to original chunk/page/document
```

## Architecture decision

AURORA already uses stable text model `gemini-embedding-001`, configured at 768
dimensions, with the asymmetric task pairing documented for search:

- indexed chunks: `RETRIEVAL_DOCUMENT`
- user queries: `RETRIEVAL_QUERY`

Documents and queries therefore enter the provider's shared semantic vector
space without an application translation step. Upgrading to a different model,
changing dimensions, or adding query translation would introduce migration and
quality risks without being required by the measured English/Hindi results.

The provider-neutral `EmbeddingProvider` interface remains unchanged. AURORA
does not claim support for every language advertised across Gemini model
families. v1.0 directly tests only English and Hindi.

## Query and answer behavior

- Retrieval embeds the original user query exactly as submitted.
- Source text is never translated or overwritten.
- When `answer_language` is supplied, Gemini is instructed to answer in it.
- When omitted, Gemini is instructed to answer in the query language where
  practical.
- Original Unicode filename, text, page, document ID, chunk ID, and persistent
  citation identity remain authoritative.

## Reproducible evaluation dataset

The versioned dataset is
`backend/tests/data/multilingual_evaluation_v1.0.json`. It contains four tiny,
controlled documents:

| Key | Language | Fact | Page |
|---|---|---|---:|
| `english_archive` | English | Archive code name is Blue Lotus | 2 |
| `hindi_solar` | Hindi | Surya research centre is in Jaipur | 4 |
| `english_garden` | English | Garden opens at sunrise | 1 |
| `hindi_river` | Hindi | River team checks water on Monday | 6 |

The six-case matrix covers:

1. English query → English document
2. Hindi query → Hindi document
3. English query → Hindi document
4. Hindi query → English document
5. English query → mixed English/Hindi corpus
6. Hindi query → mixed English/Hindi corpus

Every case specifies source/query language, corpus, expected chunk/document,
expected page, expected retrieval behavior, expected answer language, and an
answer marker.

## Evaluation methodology

### Deterministic automated evaluation

A test-only bilingual provider maps equivalent controlled English/Hindi concepts
onto the same vector axes. Documents are indexed through AURORA's real indexing
service, stored in PostgreSQL `vector(768)`, retrieved by the real exact-cosine SQL
service, passed through RAG, persisted, and fetched through the authorized API.

This proves application correctness and reproducibility; it does **not** estimate
Gemini's general multilingual quality.

Measured on 2026-08-13 over six cases:

| Metric | Measured result |
|---|---:|
| Top-1 retrieval accuracy | 100.00% (6/6) |
| Top-k relevant-chunk recall | 100.00% (6/6) |
| Answer-language correctness | 100.00% (6/6) |
| Citation provenance correctness | 100.00% (6/6) |
| Mean local search-plus-RAG latency | 32.70 ms |
| Median local search-plus-RAG latency | 32.65 ms |

Latency is environment-specific and includes local HTTP/API, pgvector retrieval,
fake generation, persistence, and test overhead. It excludes network providers.

### Explicit real Gemini evaluation

The opt-in test used the configured production adapters and private `.env` key
for two controlled cross-language cases:

- English query → Hindi Nakshatra-project source → English answer
- Hindi query → English Zephyr-laboratory source → Hindi answer

Measured on 2026-08-13:

| Metric | Measured result |
|---|---:|
| Top-1 retrieval accuracy | 100.00% (2/2) |
| Top-k relevant-chunk recall | 100.00% (2/2) |
| Answer-language and fact-marker correctness | 100.00% (2/2) |
| Citation provenance correctness | 100.00% (2/2) |
| Mean search-plus-RAG latency | 6,435.84 ms |
| Median search-plus-RAG latency | 6,435.84 ms |

These are real measured outcomes for two synthetic facts, not a statistically
representative language benchmark. A successful API request alone was not counted;
the expected source had to rank first, the answer language/fact marker had to
match, and persisted citation metadata had to point to the original source.

Run the quota-consuming check explicitly with:

```powershell
cd backend
$env:AURORA_RUN_REAL_MULTILINGUAL_TEST="1"
.\aurora-env\Scripts\python.exe -m pytest tests\test_multilingual_rag.py `
  -k real_gemini_cross_language_retrieval_generation_and_provenance -q -s
```

Normal pytest runs skip it and make no Gemini calls.

## Provenance and security

- Workspace membership is resolved before search or RAG.
- Exact pgvector retrieval filters workspace in SQL before context creation.
- The test matrix verifies original Hindi text survives indexing, retrieval,
  context, response persistence, and citation lookup.
- Citations remain server-generated and revalidated against live workspace rows.
- Cross-workspace and non-member access remains concealed.
- Clients still cannot submit document, chunk, response, or citation identities.
- The API key stays server-side in ignored `.env`; no secret is stored in the
  dataset, logs, source, documentation, or API responses.

## Known limitations

- Only English and Hindi are evaluated in v1.0.
- Six deterministic and two live cases are too small to establish broad quality.
- Test facts are short and unambiguous; long documents, domain terminology,
  code-switching, transliteration, dialects, and ambiguous queries need larger
  evaluation sets.
- Answer-language detection checks writing system plus expected fact markers,
  not linguistic fluency.
- Retrieval uses no reranking, query rewriting, hybrid search, or translation.
- The `0.30` evidence threshold is not yet calibrated per language.
- Latency measurements are single-machine observations, not production SLOs.

The next milestone is Full Frontend Foundation.
