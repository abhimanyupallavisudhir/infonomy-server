"""
Comprehensive logging configuration for the Infonomy Information Market Server.
Provides structured logging with rotating files, detailed context tracking, and
clear source identification for all log entries.
"""

import os
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json
import traceback
import inspect
from functools import wraps

# Create logs directory if it doesn't exist
LOGS_DIR = Path(".logs")
LOGS_DIR.mkdir(exist_ok=True)

# Log file configuration
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5

# Log levels for different components
LOG_LEVELS = {
    "general": logging.INFO,
    "api": logging.INFO,
    "database": logging.INFO,
    "llm": logging.INFO,
    "celery": logging.INFO,
    "auth": logging.INFO,
    "bot_sellers": logging.INFO,
    "inspection": logging.INFO,
    "debug": logging.DEBUG,
}

class ContextualFormatter(logging.Formatter):
    """Custom formatter that includes detailed context information."""
    
    def format(self, record):
        # Add timestamp
        record.timestamp = datetime.now().isoformat()
        
        # Add source information
        if hasattr(record, 'source_file') and hasattr(record, 'source_line'):
            record.source = f"{record.source_file}:{record.source_line}"
        else:
            record.source = "unknown"
        
        # Add function information
        if hasattr(record, 'function_name'):
            record.function = record.function_name
        else:
            record.function = "unknown"
        
        # Format parameters if present
        if hasattr(record, 'parameters'):
            if isinstance(record.parameters, dict):
                record.params_str = json.dumps(record.parameters, default=str)
            else:
                record.params_str = str(record.parameters)
        else:
            record.params_str = "{}"
        
        # Add exception info if present
        if record.exc_info:
            record.exception_trace = self.formatException(record.exc_info)
        else:
            record.exception_trace = ""
        
        return super().format(record)

def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with rotating file handler and console handler."""
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = ContextualFormatter(
        fmt='%(timestamp)s | %(levelname)-8s | %(name)-20s | %(source)-30s | %(function)-25s | %(params_str)s | %(message)s'
    )
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / log_file,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Create loggers for different components
loggers = {}

def get_logger(component: str) -> logging.Logger:
    """Get or create a logger for a specific component."""
    if component not in loggers:
        log_file = f"{component}.log"
        level = LOG_LEVELS.get(component, logging.INFO)
        loggers[component] = setup_logger(component, log_file, level)
    return loggers[component]

def log_with_context(logger: logging.Logger, level: int, message: str, 
                    parameters: Optional[Dict[str, Any]] = None, 
                    exception: Optional[Exception] = None):
    """Log a message with detailed context information."""
    
    # Get caller information with improved detection
    filename = "unknown"
    line_number = 0
    function_name = "unknown"
    
    # Walk up the call stack to find the actual caller
    frame = inspect.currentframe()
    while frame:
        frame = frame.f_back
        if frame:
            # Skip logging-related frames
            frame_filename = frame.f_code.co_filename
            if ('logging_config.py' not in frame_filename and 
                'middleware.py' not in frame_filename):
                filename = os.path.basename(frame_filename)
                line_number = frame.f_lineno
                function_name = frame.f_code.co_name
                break
    
    # Create log record with extra attributes
    extra = {
        'source_file': filename,
        'source_line': line_number,
        'function_name': function_name,
        'parameters': parameters or {}
    }
    
    if exception:
        logger.log(level, message, extra=extra, exc_info=True)
    else:
        logger.log(level, message, extra=extra)

def log_function_call(logger: logging.Logger, func_name: str, parameters: Dict[str, Any]):
    """Log function entry with parameters."""
    log_with_context(
        logger, 
        logging.DEBUG, 
        f"Function call: {func_name}",
        parameters=parameters
    )

def log_function_return(logger: logging.Logger, func_name: str, return_value: Any):
    """Log function return with result."""
    log_with_context(
        logger, 
        logging.DEBUG, 
        f"Function return: {func_name}",
        parameters={"return_value": return_value}
    )

def log_function_error(logger: logging.Logger, func_name: str, error: Exception, parameters: Dict[str, Any] = None):
    """Log function error with exception details."""
    log_with_context(
        logger, 
        logging.ERROR, 
        f"Function error: {func_name}",
        parameters=parameters or {},
        exception=error
    )

def log_api_request(logger: logging.Logger, method: str, path: str, user_id: Optional[int] = None, 
                   parameters: Dict[str, Any] = None):
    """Log API request details."""
    params = {
        "method": method,
        "path": path,
        "user_id": user_id,
    }
    if parameters:
        params.update(parameters)
    log_with_context(logger, logging.INFO, "API Request", parameters=params)

def log_api_response(logger: logging.Logger, method: str, path: str, status_code: int, 
                    response_time: float, user_id: Optional[int] = None):
    """Log API response details."""
    params = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "response_time_ms": round(response_time * 1000, 2),
        "user_id": user_id
    }
    log_with_context(logger, logging.INFO, "API Response", parameters=params)

def log_database_operation(logger: logging.Logger, operation: str, table: str, 
                          record_id: Optional[int] = None, parameters: Dict[str, Any] = None):
    """Log database operations."""
    params = {
        "operation": operation,
        "table": table,
        "record_id": record_id,
    }
    if parameters:
        params.update(parameters)
    log_with_context(logger, logging.DEBUG, "Database Operation", parameters=params)

def log_llm_call(logger: logging.Logger, model: str, prompt_length: int, 
                 response_length: int, duration: float, parameters: Dict[str, Any] = None):
    """Log LLM API calls."""
    params = {
        "model": model,
        "prompt_length": prompt_length,
        "response_length": response_length,
        "duration_ms": round(duration * 1000, 2),
    }
    if parameters:
        params.update(parameters)
    log_with_context(logger, logging.INFO, "LLM Call", parameters=params)

def log_celery_task(logger: logging.Logger, task_name: str, task_id: str, 
                   parameters: Dict[str, Any] = None):
    """Log Celery task execution."""
    params = {
        "task_name": task_name,
        "task_id": task_id,
    }
    if parameters:
        params.update(parameters)
    log_with_context(logger, logging.INFO, "Celery Task", parameters=params)

def log_business_event(logger: logging.Logger, event_type: str, 
                      user_id: Optional[int] = None, parameters: Dict[str, Any] = None):
    """Log business logic events."""
    params = {
        "event_type": event_type,
        "user_id": user_id,
    }
    if parameters:
        params.update(parameters)
    log_with_context(logger, logging.INFO, "Business Event", parameters=params)

# Decorator for automatic function logging
def logged_function(component: str):
    """Decorator to automatically log function calls, returns, and errors."""
    def decorator(func):
        logger = get_logger(component)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Log function entry
            params = {
                "args": str(args),
                "kwargs": kwargs
            }
            log_function_call(logger, func_name, params)
            
            try:
                # Execute function
                start_time = datetime.now()
                result = func(*args, **kwargs)
                end_time = datetime.now()
                
                # Log function return
                execution_time = (end_time - start_time).total_seconds()
                log_function_return(logger, func_name, {
                    "result": str(result),
                    "execution_time_ms": round(execution_time * 1000, 2)
                })
                
                return result
                
            except Exception as e:
                # Log function error
                log_function_error(logger, func_name, e, params)
                raise
        
        return wrapper
    return decorator

# Initialize main loggers
general_logger = get_logger("general")
api_logger = get_logger("api")
database_logger = get_logger("database")
llm_logger = get_logger("llm")
celery_logger = get_logger("celery")
auth_logger = get_logger("auth")
bot_sellers_logger = get_logger("bot_sellers")
inspection_logger = get_logger("inspection")
debug_logger = get_logger("debug")

# Log system startup
general_logger.info("Logging system initialized", extra={
    'source_file': 'logging_config.py',
    'source_line': 0,
    'function_name': 'module_init',
    'parameters': {
        'logs_directory': str(LOGS_DIR),
        'max_log_size_mb': MAX_LOG_SIZE // (1024 * 1024),
        'backup_count': BACKUP_COUNT
    }
}) 