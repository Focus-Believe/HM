from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    APP_NAME: str = "Hey MIN"
    APP_ENV: str = "production"
    DEBUG: bool = False
    
    DATABASE_URL: str
    REDIS_URL: str
    
    SECRET_KEY: str
    JWT_SECRET: str
    WEBHOOK_SECRET: str
    
    ENABLE_2FA: bool = True
    ENABLE_VOICE_CALLS: bool = True
    ENABLE_VIDEO_CALLS: bool = True
    ENABLE_GROUP_CHAT: bool = True
    ENABLE_MESSAGE_REACTIONS: bool = True
    ENABLE_MESSAGE_EDIT: bool = True
    ENABLE_TYPING_INDICATOR: bool = True
    ENABLE_READ_RECEIPTS: bool = True
    ENABLE_FILE_SHARING: bool = True
    ENABLE_STORIES: bool = True
    ENABLE_AI_ASSISTANT: bool = True
    ENABLE_BLOCK_USERS: bool = True
    ENABLE_DARK_MODE: bool = True
    
    MAX_FILE_SIZE: int = 20971520
    RATE_LIMIT_MESSAGES: int = 50
    RATE_LIMIT_WINDOW: int = 60
    
    OPENAI_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()
