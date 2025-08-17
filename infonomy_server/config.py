"""
Configuration settings for the Infonomy server
"""

import os
from typing import Optional

# BotSeller Configuration
BOTSELLER_TIMEOUT_SECONDS = int(os.getenv("BOTSELLER_TIMEOUT_SECONDS", "30"))
BOTSELLER_MAX_WAIT_TIME = int(os.getenv("BOTSELLER_MAX_WAIT_TIME", "60"))
BOTSELLER_POLL_INTERVAL_FAST = int(os.getenv("BOTSELLER_POLL_INTERVAL_FAST", "1"))
BOTSELLER_POLL_INTERVAL_SLOW = int(os.getenv("BOTSELLER_POLL_INTERVAL_SLOW", "3"))

# LLM Configuration
DEFAULT_LLM_MAX_TOKENS = int(os.getenv("DEFAULT_LLM_MAX_TOKENS", "500"))
DEFAULT_LLM_TEMPERATURE = float(os.getenv("DEFAULT_LLM_TEMPERATURE", "0.7"))

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./infonomy_server.db")

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Security Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# API Configuration
API_V1_STR = "/api/v1"
PROJECT_NAME = "Infonomy Information Market API"
VERSION = "1.0.0"
DESCRIPTION = "An information market platform supporting human and bot sellers" 