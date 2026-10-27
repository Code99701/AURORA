# AURORA — Why the RAG keeps failing (root-cause report)

Date: 2026-10-27 · Evidence: backend code read + **live queries on your Postgres DB** (`aurora-postgres`). Nothing was modified.
Labels: `[DB]` = seen in your database · `[CODE]` = read in source · `[INFERRED]` = my reasoning, verify.

---

## 1. One-paragraph answer

The RAG is not broken. It is **too simple for the questions you ask**. It embeds your question once, grabs the **5 most similar chunks**, and asks the LLM to answer only from them. That works for narrow lookups ("what is present in mmvy.pdf") and fails for **overview, summary, page-based and "most often" questions**, which need more than 5 similar chunks. On your slide-deck PDF the chunks are also tiny and weak, so the 5 retrieved slides were unrelated. The LLM then correctly refused, and the UI still showed those 5 irrelevant sources.

---

## 2. Proof from your own data

### Your last failure [DB]
Query: *"give the explanation of first 5 pages of the pdf i attached"* → answer: *"I couldn't find enough information…"*, `insufficient_evidence = false`, `citation_count = 5`, model `gemini-3.6-flash`.

- Retrieved sources: **pages 47, 143, 162, 48, 135** (screenshot). **None is page 1–5.**
- Meaning: retrieval found 5 chunks, the threshold let them pass, the LLM read them, saw they did not answer "first 5 pages", and refused as its system prompt tells it to. **The refusal was correct given the evidence; retrieval was wrong.**

### Pattern across all your logged questions [DB]
| Question | Result | Why |
|---|---|---|
| what is present in mmvy.pdf | Works | Small doc (9 chunks), filename in the question |
| what is present in the document attached (resume) | Works | Tiny doc: 5 chunks, all fit in top-5 |
| what is present in my intern pdf, complete detailed summary | Partial ("available pages") | 21 chunks, top-5 sees a fraction |
| can you provide the pdf summary of the given pdf | Failed (no evidence) | Overview question, no topical match |
| Which skills appear most often? | Failed | Aggregation across the document |
| give the explanation of first 5 pages… | Failed | Positional question on a 168-page deck |

**Works:** small documents, specific questions. **Fails:** big documents, or anything about "the whole document / pages / most often / summarise".

---

## 3. Root causes (ranked)

### RC1 — Pure top-5 semantic search, nothing else [CODE]
`retrieval.py` does one cosine search; `top_k` defaults to 5 and the frontend hard-codes `top_k: 5` (`lib/api.ts` L116, L247, L274). There is:
- no page/position lookup ("first 5 pages", "page 12"),
- no summary/overview mode (needs broad coverage of the document),
- no aggregation mode ("most often", "list all"),
- no keyword search (filenames, exact terms),
- no history-aware rewriting: `query=content` is embedded as typed, so follow-ups like "Translate this answer to Hindi" or "Summarise the projects in 3 lines" retrieve nonsense (`conversation.py`: history is only pasted into the prompt, not used for retrieval).

### RC2 — The slide deck is chunked into junk [DB]
`ANN PPT UNIT 2.pdf`: **168 chunks, average 208 characters, 54 chunks (32%) under 80 characters.** One chunk per slide, e.g. "UNIT-II (ARTIFICIAL NEURAL NETWORKS) 1" (38 chars), "CONTD.. 9" (9 chars), "CONTD.. 12" (10 chars). Your design says 1000-char chunks; real slides never get merged. Tiny chunks give weak, noisy embeddings, and a repeated "CONTD.." title matches many unrelated queries.

### RC3 — Almost none of the context budget is used [CODE + DB]
The context limit is 12,000 characters (`RAG_CONTEXT_MAX_CHARACTERS`). Five slide chunks of ~200 characters is ~1,000 characters, **under 10% of the budget**. You could send 10–20× more evidence for free.

### RC4 — The similarity threshold does nothing [CODE + DB]
`RAG_MIN_SIMILARITY = 0.30`, but every stored citation has similarity **0.58–0.70** (min 0.58, avg 0.625, max 0.70). Irrelevant chunks routinely score ~0.6 with this embedding model, so the threshold never filters anything, and the LLM becomes the only judge. [Medium confidence: this is from the citations that were saved, not all candidates.]

### RC5 — A refusal still shows sources and is not flagged [CODE + DB]
`insufficient_evidence` is only set when *no* chunk passes the threshold (`rag.py`). When the LLM itself refuses, the record keeps `insufficient_evidence = false` and 5 citations, so the UI says "Grounded in 5 sources" under a refusal. Misleading.

### RC6 — The UI shows hard-coded follow-up questions [CODE + screenshot]
"Which skills appear most often?", "Summarise the projects in 3 lines", "Translate this answer to Hindi" appear under an ANN-deck refusal. They are the sample text from the mockup, not generated from the answer. Clicking them sends questions unrelated to the deck (the "skills" one is in your failure log).

### RC7 — Data hygiene problems [DB]
- Duplicates: 6 identical `sample-*.txt`, 2× `intern.pdf`, cornerstone deck as both PDF and PPTX. Duplicates across documents are not deduplicated, so they take top-5 slots.
- Stuck/failed ingestion: `the-hundred-page-machine-learning-book` has one row stuck in `INDEXING` (0 chunks), `ui_ux_design_styles.pdf` FAILED, `Nptel exam.pdf` NOT_INDEXED, `test_audit_notes.txt` stuck, `Adobe license…pdf` PARTIAL, 1 content unit `OCR_FAILED`.
- Note: this query covered all workspaces, not just "DEEP LEARNING".

### RC8 — Possible text-encoding noise [DB, low confidence]
Chunk text shows `ïƒ˜` and `â€“`. These are probably the PDF's private-use bullet glyph and an en dash being shown by my PowerShell output, so it may be display-only. **Verify in the app** by opening a chunk or asking for a quote. If real, strip private-use characters (U+E000–U+F8FF) and fix the decode step.

---

## 4. What is NOT the problem
- Embeddings/DB: working, dimension matches, vectors present for all 168 pages.
- OCR: this deck used native text (`NATIVE`, 168 units), no OCR issue.
- Gemini/LLM: responds fine on easy questions.
- Security/authorization: working as designed.

---

## 5. Fix plan (in this order, for Antigravity)

1. **Query router** in `prepare_question`:
   - Page questions ("first 5 pages", "page 12", "pages 3–7") → fetch chunks **by `page_number`** with a SQL `WHERE page_number BETWEEN` for the target document, ordered, not by similarity.
   - Overview/summary ("summarise", "what's in", "explain the document") → sample the document evenly (first chunks + evenly spaced + headings), up to ~20–30 chunks, or map-reduce summarise by sections.
   - Aggregation ("most often", "list all", "how many") → higher top_k (20+).
   - Otherwise normal semantic search.
2. **History-aware query rewrite**: before embedding, rewrite the question into a standalone one using the last few messages (one short LLM call, or rule-based for "this/that/it").
3. **Hybrid search**: add Postgres full-text search (`tsvector`) and fuse with vector results (reciprocal rank fusion). Helps filenames, terms and numbers.
4. **Fix chunking for slides**: merge consecutive small pages into ~800–1000-char chunks with `page_start/page_end`; drop chunks like "CONTD.. 9"; prefix each chunk with filename + section title. Then **re-index** existing documents.
5. **Use the budget**: default `top_k` 12 (frontend + schema); fill the 12,000-char context; replace the absolute 0.30 threshold with a relative cut (drop chunks far below the best score).
6. **Honest refusals**: if the LLM returns the refusal text, set `insufficient_evidence = true`, hide sources, and show a helpful message ("Try naming a page or topic, or ask for a summary").
7. **Remove hard-coded follow-ups** in the UI, or generate them from the real answer.
8. **Data cleanup**: dedupe on upload by content hash; reset stuck `INDEXING` rows; surface FAILED/PARTIAL documents in the UI with a Retry.
9. **Evaluation**: create 20–30 test questions across 3 documents (specific, page, summary, aggregation, follow-up) and track hit rate before/after each change. Add as pytest.

**Expected result:** the page, summary and aggregation questions that fail today should start working after steps 1, 4 and 5; follow-ups after step 2.

---

## 6. What I could not verify
- I did not re-run your failing question against a live server with debug output; conclusions come from the saved DB records plus code. The 5 retrieved page numbers come from your screenshot.
- Whether the odd characters are real corruption (RC8).
- Whether the other workspaces behave differently.
