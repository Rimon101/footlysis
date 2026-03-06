from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY_NAME = "X-Admin-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_admin_key(api_key_header: str = Security(api_key_header)):
    """Verify that the provided API key matches the ADMIN_API_KEY environment variable."""
    expected_key = os.getenv("ADMIN_API_KEY") or os.getenv("VITE_ADMIN_API_KEY")
    
    # If no key is set in production, deny access by default (fail-safe)
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin API Key is not configured on the server."
        )

    if api_key_header != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials."
        )
    return api_key_header
