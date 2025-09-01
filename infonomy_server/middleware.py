"""
FastAPI middleware for comprehensive API request/response logging.
"""

import time
import json
from typing import Callable, Dict, Any
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from infonomy_server.logging_config import api_logger, log_api_request, log_api_response

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses with detailed context."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Record start time
        start_time = time.time()
        
        # Extract request information
        method = request.method
        path = request.url.path
        query_params = dict(request.query_params)
        
        # Get user ID if available
        user_id = None
        try:
            # Try to get user from request state (set by auth middleware)
            if hasattr(request.state, 'user') and request.state.user:
                user_id = request.state.user.id
        except Exception:
            pass
        
        # Extract request body for logging (be careful with sensitive data)
        body = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                # Only log body for non-sensitive endpoints
                if not any(sensitive in path.lower() for sensitive in ['auth', 'password', 'token']):
                    body_bytes = await request.body()
                    if body_bytes:
                        try:
                            body = json.loads(body_bytes.decode())
                        except:
                            body = "[Non-JSON body]"
            except Exception:
                body = "[Error reading body]"
        
        # Log request
        request_params = {
            "query_params": query_params,
            "headers": dict(request.headers),
            "body": body
        }
        log_api_request(api_logger, method, path, user_id, request_params)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Log response
            log_api_response(api_logger, method, path, response.status_code, response_time, user_id)
            
            return response
            
        except Exception as e:
            # Log error response
            response_time = time.time() - start_time
            log_api_response(api_logger, method, path, 500, response_time, user_id)
            
            # Re-raise the exception
            raise

def setup_logging_middleware(app):
    """Add logging middleware to FastAPI app."""
    app.add_middleware(LoggingMiddleware) 