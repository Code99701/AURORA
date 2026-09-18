from pathlib import Path
from typing import List, Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, SecretStr, computed_field, model_validator
from pydantic_core import MultiHostUrl


PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    """
    Application settings managed by pydantic-settings.
    Values can be overridden by environment variables (e.g., PROJECT_NAME="My App").
    """
    PROJECT_NAME: str = "AURORA"
    ENVIRONMENT: str = "development"
    
    # API prefix for all v1 routes
    API_V1_STR: str = "/api/v1"
    
    # CORS Origins
    # In development, we typically allow localhost. In production, this should be restricted.
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Security & Cookie Configuration
    AUTH_COOKIE_NAME: str = "aurora_session"
    SESSION_EXPIRY_DAYS: int = 7
    COOKIE_SECURE: bool = False  # False for local dev (HTTP), True for prod (HTTPS)
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    # Optional Google OpenID Connect login. The callback URI is public, but the
    # client secret is consumed only by FastAPI during the server-side exchange.
    GOOGLE_OAUTH_ENABLED: bool = False
    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_OAUTH_REDIRECT_URI: str | None = None
    GOOGLE_OAUTH_TRANSACTION_TTL_SECONDS: int = 600

    # Document storage and validation
    DOCUMENT_STORAGE_PROVIDER: Literal["local"] = "local"
    DOCUMENT_STORAGE_ROOT: Path = Path("storage/uploads")
    DOCUMENT_MAX_SIZE_BYTES: int = 10 * 1024 * 1024

    # Canonical multi-format ingestion and bounded local PDF OCR.
    PDF_MAX_PAGES: int = 250
    PDF_RENDER_DPI: int = 300
    PDF_MAX_RENDERED_PIXELS_PER_PAGE: int = 40_000_000
    PDF_MAX_TOTAL_RENDERED_PIXELS: int = 900_000_000
    OCR_MAX_PAGES: int = 100
    OCR_TIMEOUT_SECONDS_PER_PAGE: float = 30.0
    OCR_LANGUAGES: str = "eng+hin"
    TESSERACT_EXECUTABLE: str | None = None
    NATIVE_TEXT_MIN_CHARACTERS: int = 8
    OCR_TEXT_MIN_CHARACTERS: int = 12
    EXTRACTION_MIN_PRINTABLE_RATIO: float = 0.85
    OCR_MIN_CONFIDENCE: float = 0.25
    EXTRACTION_MAX_CHARACTERS: int = 5_000_000
    INGESTION_MAX_UNITS: int = 10_000
    TABULAR_MAX_ROWS: int = 50_000
    TABULAR_MAX_COLUMNS: int = 500
    TABULAR_MAX_CELLS: int = 250_000
    TABULAR_MAX_FIELD_CHARACTERS: int = 100_000
    TABULAR_ROWS_PER_UNIT: int = 50
    OOXML_MAX_ARCHIVE_ENTRIES: int = 10_000
    OOXML_MAX_UNCOMPRESSED_BYTES: int = 100 * 1024 * 1024
    DOCX_MAX_PARAGRAPHS: int = 20_000
    PPTX_MAX_SLIDES: int = 1_000
    XLSX_MAX_SHEETS: int = 250

    # RAG indexing and embedding configuration. The database vector dimension is
    # deliberately fixed for v0.7 so provider output cannot silently drift.
    GEMINI_API_KEY: str | None = None
    EMBEDDING_PROVIDER: Literal["gemini"] = "gemini"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIMENSION: int = 768
    CHUNK_SIZE_CHARACTERS: int = 1000
    CHUNK_OVERLAP_CHARACTERS: int = 150
    RETRIEVAL_MAX_TOP_K: int = 20
    RETRIEVAL_CANDIDATE_MULTIPLIER: int = 4

    # One-shot grounded RAG generation. Generation and embedding models are
    # independent configuration because they serve different workloads.
    LLM_PROVIDER: Literal["gemini"] = "gemini"
    LLM_MODEL: str = "gemini-3.6-flash"
    LLM_MAX_OUTPUT_TOKENS: int = 1024
    RAG_CONTEXT_MAX_CHARACTERS: int = 12000
    RAG_MIN_SIMILARITY: float = 0.30
    CONVERSATION_HISTORY_MAX_MESSAGES: int = 8
    CONVERSATION_HISTORY_MAX_CHARACTERS: int = 6000
    STREAMING_MAX_RESPONSE_CHARACTERS: int = 32768


    # Database Configuration
    POSTGRES_USER: str = "aurora"
    POSTGRES_PASSWORD: str = "aurora_password"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aurora_db"

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    @model_validator(mode="after")
    def validate_cookie_security(self) -> "Settings":
        environment = self.ENVIRONMENT.casefold()
        if environment == "production" and not self.COOKIE_SECURE:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError("SameSite=None cookies must also be Secure")
        if not 60 <= self.GOOGLE_OAUTH_TRANSACTION_TTL_SECONDS <= 900:
            raise ValueError("GOOGLE_OAUTH_TRANSACTION_TTL_SECONDS must be between 60 and 900")
        if self.GOOGLE_OAUTH_ENABLED:
            if not self.GOOGLE_OAUTH_CLIENT_ID or not self.GOOGLE_OAUTH_CLIENT_ID.strip():
                raise ValueError("GOOGLE_OAUTH_CLIENT_ID is required when Google OAuth is enabled")
            if self.GOOGLE_OAUTH_CLIENT_SECRET is None or not self.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value().strip():
                raise ValueError("GOOGLE_OAUTH_CLIENT_SECRET is required when Google OAuth is enabled")
            if not self.GOOGLE_OAUTH_REDIRECT_URI:
                raise ValueError("GOOGLE_OAUTH_REDIRECT_URI is required when Google OAuth is enabled")
            redirect = urlparse(self.GOOGLE_OAUTH_REDIRECT_URI)
            expected_path = f"{self.API_V1_STR}/auth/google/callback"
            if (
                not redirect.scheme
                or not redirect.netloc
                or redirect.username
                or redirect.password
                or redirect.query
                or redirect.fragment
                or redirect.path != expected_path
            ):
                raise ValueError(
                    f"GOOGLE_OAUTH_REDIRECT_URI must be an absolute URL ending in {expected_path} "
                    "without credentials, a query, or a fragment"
                )
            if environment == "production" and redirect.scheme != "https":
                raise ValueError("GOOGLE_OAUTH_REDIRECT_URI must use HTTPS in production")
            if redirect.scheme == "http" and redirect.hostname not in {"localhost", "127.0.0.1"}:
                raise ValueError("HTTP Google OAuth redirect URIs are allowed only for local development")
            if redirect.scheme not in {"http", "https"}:
                raise ValueError("GOOGLE_OAUTH_REDIRECT_URI must use HTTP or HTTPS")
        if self.DOCUMENT_MAX_SIZE_BYTES <= 0:
            raise ValueError("DOCUMENT_MAX_SIZE_BYTES must be greater than zero")
        if not 1 <= self.PDF_MAX_PAGES <= 2000:
            raise ValueError("PDF_MAX_PAGES must be between 1 and 2000")
        if not 72 <= self.PDF_RENDER_DPI <= 400:
            raise ValueError("PDF_RENDER_DPI must be between 72 and 400")
        if self.PDF_MAX_RENDERED_PIXELS_PER_PAGE <= 0:
            raise ValueError("PDF_MAX_RENDERED_PIXELS_PER_PAGE must be greater than zero")
        if self.PDF_MAX_TOTAL_RENDERED_PIXELS < self.PDF_MAX_RENDERED_PIXELS_PER_PAGE:
            raise ValueError(
                "PDF_MAX_TOTAL_RENDERED_PIXELS must cover at least one rendered page"
            )
        if not 1 <= self.OCR_MAX_PAGES <= self.PDF_MAX_PAGES:
            raise ValueError("OCR_MAX_PAGES must be between 1 and PDF_MAX_PAGES")
        if not 1 <= self.OCR_TIMEOUT_SECONDS_PER_PAGE <= 300:
            raise ValueError("OCR_TIMEOUT_SECONDS_PER_PAGE must be between 1 and 300")
        if not self.OCR_LANGUAGES.strip():
            raise ValueError("OCR_LANGUAGES must not be blank")
        if self.NATIVE_TEXT_MIN_CHARACTERS <= 0 or self.OCR_TEXT_MIN_CHARACTERS <= 0:
            raise ValueError("Extraction character thresholds must be greater than zero")
        if not 0 <= self.EXTRACTION_MIN_PRINTABLE_RATIO <= 1:
            raise ValueError("EXTRACTION_MIN_PRINTABLE_RATIO must be between 0 and 1")
        if not 0 <= self.OCR_MIN_CONFIDENCE <= 1:
            raise ValueError("OCR_MIN_CONFIDENCE must be between 0 and 1")
        if self.EXTRACTION_MAX_CHARACTERS <= 0:
            raise ValueError("EXTRACTION_MAX_CHARACTERS must be greater than zero")
        if not 1 <= self.INGESTION_MAX_UNITS <= 100_000:
            raise ValueError("INGESTION_MAX_UNITS must be between 1 and 100000")
        if not 1 <= self.TABULAR_MAX_ROWS <= 1_000_000:
            raise ValueError("TABULAR_MAX_ROWS must be between 1 and 1000000")
        if not 1 <= self.TABULAR_MAX_COLUMNS <= 16_384:
            raise ValueError("TABULAR_MAX_COLUMNS must be between 1 and 16384")
        if self.TABULAR_MAX_CELLS < self.TABULAR_MAX_COLUMNS:
            raise ValueError("TABULAR_MAX_CELLS must cover at least one maximum-width row")
        if self.TABULAR_MAX_FIELD_CHARACTERS <= 0:
            raise ValueError("TABULAR_MAX_FIELD_CHARACTERS must be greater than zero")
        if not 1 <= self.TABULAR_ROWS_PER_UNIT <= 1000:
            raise ValueError("TABULAR_ROWS_PER_UNIT must be between 1 and 1000")
        if self.OOXML_MAX_ARCHIVE_ENTRIES <= 0:
            raise ValueError("OOXML_MAX_ARCHIVE_ENTRIES must be greater than zero")
        if self.OOXML_MAX_UNCOMPRESSED_BYTES < self.DOCUMENT_MAX_SIZE_BYTES:
            raise ValueError(
                "OOXML_MAX_UNCOMPRESSED_BYTES must be at least DOCUMENT_MAX_SIZE_BYTES"
            )
        if self.DOCX_MAX_PARAGRAPHS <= 0:
            raise ValueError("DOCX_MAX_PARAGRAPHS must be greater than zero")
        if self.PPTX_MAX_SLIDES <= 0:
            raise ValueError("PPTX_MAX_SLIDES must be greater than zero")
        if self.XLSX_MAX_SHEETS <= 0:
            raise ValueError("XLSX_MAX_SHEETS must be greater than zero")
        if self.EMBEDDING_DIMENSION != 768:
            raise ValueError("EMBEDDING_DIMENSION must be 768 for the v0.7 database schema")
        if self.CHUNK_SIZE_CHARACTERS <= 0:
            raise ValueError("CHUNK_SIZE_CHARACTERS must be greater than zero")
        if not 0 <= self.CHUNK_OVERLAP_CHARACTERS < self.CHUNK_SIZE_CHARACTERS:
            raise ValueError(
                "CHUNK_OVERLAP_CHARACTERS must be nonnegative and smaller than chunk size"
            )
        if not 1 <= self.RETRIEVAL_MAX_TOP_K <= 100:
            raise ValueError("RETRIEVAL_MAX_TOP_K must be between 1 and 100")
        if not 1 <= self.RETRIEVAL_CANDIDATE_MULTIPLIER <= 10:
            raise ValueError("RETRIEVAL_CANDIDATE_MULTIPLIER must be between 1 and 10")
        if not self.LLM_MODEL.strip():
            raise ValueError("LLM_MODEL must not be blank")
        if not 1 <= self.LLM_MAX_OUTPUT_TOKENS <= 8192:
            raise ValueError("LLM_MAX_OUTPUT_TOKENS must be between 1 and 8192")
        if not 1000 <= self.RAG_CONTEXT_MAX_CHARACTERS <= 100000:
            raise ValueError("RAG_CONTEXT_MAX_CHARACTERS must be between 1000 and 100000")
        if not -1.0 <= self.RAG_MIN_SIMILARITY <= 1.0:
            raise ValueError("RAG_MIN_SIMILARITY must be between -1 and 1")
        if not 0 <= self.CONVERSATION_HISTORY_MAX_MESSAGES <= 50:
            raise ValueError("CONVERSATION_HISTORY_MAX_MESSAGES must be between 0 and 50")
        if not 0 <= self.CONVERSATION_HISTORY_MAX_CHARACTERS <= 50000:
            raise ValueError("CONVERSATION_HISTORY_MAX_CHARACTERS must be between 0 and 50000")
        if not 1000 <= self.STREAMING_MAX_RESPONSE_CHARACTERS <= 200000:
            raise ValueError(
                "STREAMING_MAX_RESPONSE_CHARACTERS must be between 1000 and 200000"
            )
        return self

    @computed_field
    @property
    def DOCUMENT_STORAGE_PATH(self) -> Path:
        if self.DOCUMENT_STORAGE_ROOT.is_absolute():
            return self.DOCUMENT_STORAGE_ROOT.resolve()
        return (PROJECT_ROOT / self.DOCUMENT_STORAGE_ROOT).resolve()

    # Configuration for loading environment variables from a .env file (if present)
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# Instantiate a global settings object to be used throughout the app
settings = Settings()
