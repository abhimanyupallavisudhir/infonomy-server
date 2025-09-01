# Comprehensive Logging System for Infonomy Information Market Server

## Overview

This logging system provides extensive, structured logging for the Infonomy Information Market Server. Every log entry includes detailed context information including source file, line number, function name, and relevant parameters to make debugging and monitoring much easier.

## Features

- **Rotating File Logs**: Automatic log rotation when files reach 10MB, keeping 5 backup files
- **Component-Specific Logs**: Separate log files for different system components
- **Structured Logging**: JSON-formatted parameters for easy parsing and analysis
- **Context Tracking**: Every log entry includes source file, line number, and function name
- **Performance Monitoring**: Built-in timing for API calls, LLM calls, and function execution
- **Error Tracking**: Comprehensive error logging with full stack traces
- **Business Event Logging**: Specialized logging for business logic events

## Log Files

All logs are stored in the `.logs/` directory with the following files:

- `general.log` - General application events and system messages
- `api.log` - All API requests and responses with timing
- `database.log` - Database operations and initialization
- `llm.log` - LLM API calls with performance metrics
- `celery.log` - Celery task execution and background jobs
- `auth.log` - Authentication and user management events
- `bot_sellers.log` - Bot seller operations and offer generation
- `inspection.log` - Information inspection and purchase decisions
- `debug.log` - Debug-level messages (empty by default)

## Log Format

Each log entry follows this structured format:

```
TIMESTAMP | LEVEL | COMPONENT | SOURCE_FILE:LINE | FUNCTION | PARAMETERS | MESSAGE
```

Example:
```
2025-08-31T17:41:17.831933 | INFO | api | logging_config.py:189 | log_api_request | {"method": "GET", "path": "/api/test", "user_id": 123} | API Request
```

## Usage

### Basic Logging

```python
from infonomy_server.logging_config import general_logger, log_business_event

# Simple logging
general_logger.info("User action completed")

# Business event logging
log_business_event(general_logger, "user_purchase", user_id=123, parameters={
    "item_id": 456,
    "amount": 10.50,
    "currency": "USD"
})
```

### API Logging

The system automatically logs all API requests and responses through middleware:

```python
# Automatically logged by middleware
@router.get("/users/{user_id}")
def get_user(user_id: int):
    # This request/response will be automatically logged
    return {"user_id": user_id}
```

### LLM Call Logging

```python
from infonomy_server.logging_config import log_llm_call

start_time = time.time()
response = llm_client.chat.completions.create(...)
end_time = time.time()

log_llm_call(llm_logger, "gpt-4", len(prompt), len(response), 
             end_time - start_time, {
                 "context_id": 123,
                 "user_id": 456
             })
```

### Database Operation Logging

```python
from infonomy_server.logging_config import log_database_operation

log_database_operation(database_logger, "SELECT", "users", 
                      record_id=123, parameters={
                          "query": "SELECT * FROM users WHERE id = 123"
                      })
```

### Celery Task Logging

```python
from infonomy_server.logging_config import log_celery_task

@celery.task
def my_task(param1, param2):
    task_id = my_task.request.id
    log_celery_task(celery_logger, "my_task", task_id, {
        "param1": param1,
        "param2": param2
    })
    # Task logic here
```

### Function Logging Decorator

```python
from infonomy_server.logging_config import logged_function

@logged_function("my_component")
def my_function(arg1, arg2):
    # This function will be automatically logged
    return arg1 + arg2
```

## Configuration

### Log Levels

Log levels can be configured in `infonomy_server/logging_config.py`:

```python
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
```

### File Rotation

Log file rotation settings:

```python
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5  # Keep 5 backup files
```

## Integration Points

### FastAPI Middleware

The logging middleware is automatically added to the FastAPI app in `main.py`:

```python
from infonomy_server.middleware import setup_logging_middleware

app = FastAPI(title="Q&A Platform API", version="1.0.0")
setup_logging_middleware(app)
```

### Database Operations

Database initialization and operations are logged in `database.py`:

```python
from infonomy_server.logging_config import database_logger, log_business_event

def create_db_and_tables():
    log_business_event(database_logger, "database_initialization", parameters={
        "database_url": DATABASE_URL
    })
    # Database creation logic
```

### Authentication Events

User authentication events are logged in `auth.py`:

```python
from infonomy_server.logging_config import auth_logger, log_business_event

async def on_after_register(self, user: User, request: Optional[Request] = None):
    log_business_event(auth_logger, "user_registered", user_id=user.id, parameters={
        "email": user.email,
        "is_active": user.is_active
    })
```

### Celery Tasks

Background tasks are logged in `tasks.py`:

```python
from infonomy_server.logging_config import celery_logger, log_celery_task

@celery.task
def process_bot_sellers_for_context(context_id: int):
    task_id = process_bot_sellers_for_context.request.id
    log_celery_task(celery_logger, "process_bot_sellers_for_context", task_id, {
        "context_id": context_id
    })
    # Task logic
```

## Monitoring and Analysis

### Log Analysis Tools

The structured format makes it easy to analyze logs with tools like:

- **grep/awk**: For simple text-based analysis
- **jq**: For JSON parameter parsing
- **ELK Stack**: For advanced log aggregation and visualization
- **Python scripts**: For custom analysis

### Example Analysis Script

```python
import json
import re
from datetime import datetime

def analyze_api_performance(log_file):
    """Analyze API response times from logs."""
    with open(log_file, 'r') as f:
        for line in f:
            if 'API Response' in line:
                # Extract parameters
                match = re.search(r'(\{.*\}) \| API Response', line)
                if match:
                    params = json.loads(match.group(1))
                    print(f"{params['path']}: {params['response_time_ms']}ms")

# Usage
analyze_api_performance('.logs/api.log')
```

### Performance Monitoring

The system automatically tracks:

- API response times
- LLM call durations
- Function execution times
- Database operation timing
- Celery task execution times

### Error Tracking

All errors are logged with:

- Full stack traces
- Function parameters at time of error
- Source file and line number
- Context information

## Best Practices

1. **Use Appropriate Log Levels**: Use DEBUG for detailed debugging, INFO for general events, ERROR for errors
2. **Include Relevant Parameters**: Always include context that would be useful for debugging
3. **Avoid Sensitive Data**: Never log passwords, tokens, or other sensitive information
4. **Use Business Events**: Use `log_business_event` for important business logic events
5. **Monitor Log Sizes**: Check log file sizes regularly and adjust rotation settings if needed

## Troubleshooting

### Common Issues

1. **Log Files Not Created**: Ensure the `.logs/` directory exists and is writable
2. **Permission Errors**: Check file permissions on the `.logs/` directory
3. **Large Log Files**: Adjust `MAX_LOG_SIZE` or `BACKUP_COUNT` in configuration
4. **Missing Context**: Ensure all logging calls include appropriate parameters

### Testing the Logging System

Run the test script to verify the logging system is working:

```bash
python test_logging.py
```

This will create sample log entries in all log files to verify the system is functioning correctly.

## Future Enhancements

Potential improvements to consider:

1. **Log Aggregation**: Integration with centralized logging systems
2. **Metrics Export**: Export performance metrics to monitoring systems
3. **Log Compression**: Compress old log files to save space
4. **Custom Formatters**: Additional log formats for different use cases
5. **Log Filtering**: Filter sensitive information from logs
6. **Real-time Monitoring**: Web-based log viewer for real-time monitoring 