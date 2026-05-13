from pydantic_settings import BaseSettings
from typing import Optional, List
import os

class ProductionConfig(BaseSettings):
    """Hey MIN - Production Configuration"""
    
    # App Info
    APP_NAME: str = "Hey MIN"
    APP_VERSION: str = "2.0.0"
    APP_ENV: str = "production"
    DEBUG: bool = False
    
    # URLs
    APP_URL: str = "https://hey-min.onrender.com"
    API_URL: str = "https://hey-min.onrender.com/api"
    WS_URL: str = "wss://hey-min.onrender.com/ws"
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    
    # Redis
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Security
    SECRET_KEY: str
    JWT_SECRET: str
    WEBHOOK_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    
    # Rate Limiting
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_LOGIN: int = 5
    RATE_LIMIT_WINDOW: int = 60
    
    # File Upload
    MAX_FILE_SIZE: int = 10485760
    ALLOWED_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".pdf"]
    UPLOAD_PATH: str = "uploads"
    
    # Features
    ENABLE_2FA: bool = True
    ENABLE_VOICE_CALLS: bool = True
    ENABLE_VIDEO_CALLS: bool = True
    ENABLE_GROUP_CHAT: bool = True
    ENABLE_AI_ASSISTANT: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "https://hey-min.onrender.com",
        "https://www.heymin.com"
    ]
    
    # Health Check
    HEALTH_CHECK_DATABASE_TIMEOUT: int = 5
    HEALTH_CHECK_REDIS_TIMEOUT: int = 3
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # অতিরিক্ত env ভ্যারিয়েবল ইগনোর করবে

production_config = ProductionConfig()
