from pydantic import BaseModel
from datetime import datetime

class HealthResponse(BaseModel):
    """
    Schema for the /health endpoint response.
    """
    status: str
    service: str
    version: str

class DatabaseHealthResponse(BaseModel):
    """
    Schema for the database health response.
    """
    status: str
    database: str
