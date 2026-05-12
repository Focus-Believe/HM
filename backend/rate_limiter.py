from fastapi import HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis.asyncio as redis
from datetime import datetime, timedelta
from backend.config import settings

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

class AdvancedRateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        """Check rate limit using sliding window"""
        now = datetime.now().timestamp()
        window_start = now - window
        
        # Remove old entries
        await self.redis.zremrangebyscore(key, 0, window_start)
        
        # Count recent requests
        count = await self.redis.zcard(key)
        
        if count >= limit:
            return False
        
        # Add current request
        await self.redis.zadd(key, {str(now): now})
        await self.redis.expire(key, window)
        
        return True
    
    async def check_message_spam(self, user_id: int) -> bool:
        """Check if user is sending too many messages"""
        key = f"msg_limit:{user_id}"
        return await self.check_rate_limit(
            key, 
            settings.RATE_LIMIT_MESSAGES, 
            settings.RATE_LIMIT_WINDOW
        )
    
    async def check_login_attempts(self, username: str) -> bool:
        """Check login attempts to prevent brute force"""
        key = f"login_limit:{username}"
        return await self.check_rate_limit(key, settings.RATE_LIMIT_LOGIN, 300)
    
    async def block_ip(self, ip: str, duration: int = 3600):
        """Block IP address for specified duration"""
        key = f"blocked_ip:{ip}"
        await self.redis.setex(key, duration, "1")
    
    async def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        key = f"blocked_ip:{ip}"
        return await self.redis.exists(key) > 0

rate_limiter = None  # Will be initialized in main
