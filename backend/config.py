from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Enterprise Chat App"
    APP_ENV: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str
    API_VERSION: str = "v1"
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    
    # Redis
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    BCRYPT_ROUNDS: int = 12
    
    # 2FA
    TWO_FACTOR_APP_NAME: str = "ChatApp"
    
    # File Storage
    STORAGE_TYPE: str = "local"  # local, s3, gcs, azure
    AWS_ACCESS_KEY: Optional[str] = None
    AWS_SECRET_KEY: Optional[str] = None
    AWS_BUCKET_NAME: Optional[str] = None
    GCP_BUCKET_NAME: Optional[str] = None
    AZURE_CONNECTION_STRING: Optional[str] = None
    
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".gif", ".mp4", ".pdf", ".doc", ".docx"]
    
    # Rate Limiting
    RATE_LIMIT_MESSAGES: int = 30
    RATE_LIMIT_WINDOW: int = 60
    RATE_LIMIT_LOGIN: int = 5
    
    # WebRTC (Agora)
    AGORA_APP_ID: Optional[str] = None
    AGORA_APP_CERTIFICATE: Optional[str] = None
    
    # AI Features
    OPENAI_API_KEY: Optional[str] = None
    ENABLE_AI_ASSISTANT: bool = True
    ENABLE_SPAM_DETECTION: bool = True
    ENABLE_SENTIMENT_ANALYSIS: bool = True
    
    # Payment (Stripe)
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    
    # Notifications
    FIREBASE_CREDENTIALS: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None
    EMAIL_FROM: str = "noreply@chatapp.com"
    
    # Webhooks
    WEBHOOK_SECRET: str
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    
    # WebSocket
    WS_MAX_MESSAGE_SIZE: int = 10485760
    WS_PING_INTERVAL: int = 20
    WS_PING_TIMEOUT: int = 60
    
    # Features Toggle
    ENABLE_GROUP_CHAT: bool = True
    ENABLE_VOICE_CALLS: bool = True
    ENABLE_VIDEO_CALLS: bool = True
    ENABLE_FILE_SHARING: bool = True
    ENABLE_MESSAGE_REACTIONS: bool = True
    ENABLE_MESSAGE_EDIT: bool = True
    ENABLE_MESSAGE_DELETE: bool = True
    ENABLE_TYPING_INDICATOR: bool = True
    ENABLE_READ_RECEIPTS: bool = True
    ENABLE_SCREEN_SHARE: bool = True
    ENABLE_BOT: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
