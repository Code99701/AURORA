# AURORA

## AURORA: Multilingual RAG Platform

AURORA is a secure multilingual AI knowledge-discovery and
research-assistance platform based on Retrieval-Augmented Generation (RAG).

## Project Foundation

**V Semester Cornerstone Project**

**Topic #16 — Design and Development of Multilingual RAG Chatbot**

## Core Pipeline

Document Ingestion
→ Extraction
→ Cleaning
→ Chunking
→ Embeddings
→ Vector Storage
→ Retrieval
→ RAG
→ Citations
→ Multilingual Answer

## Planned Architecture

- Frontend: Next.js + TypeScript
- Backend: FastAPI + Python
- Database: PostgreSQL + pgvector
- AI: Gemini initially
- Authentication: Server-side sessions
- Authorization: RBAC
- Architecture: Modular monolith

## Development Principle

Learn
→ Build
→ Understand
→ Integrate
→ Test
→ Document
→ Viva

## Project Structure

```text
AURORA/
├── backend/
├── frontend/
├── docs/
├── learning/
├── tests/
└── scripts/
```

## Running the Backend (v0.1)

1. Activate the environment:
   ```powershell
   .\backend\aurora-env\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r backend\requirements.txt
   ```
3. Run the application:
   ```powershell
   cd backend
   uvicorn app.main:app --reload
   ```
4. Run tests:
   ```powershell
   cd backend
   pytest tests/
   ```
