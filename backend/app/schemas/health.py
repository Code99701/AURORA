from pydantic import BaseModel

class HealthResponse(BaseModel):
    """
    Schema for the /health endpoint response.
    Pydantic ensures the outgoing JSON matches this structure and data types.
    """
    status: str
    service: str
    version: str
