import redis.asyncio as redis
from datetime import datetime, timedelta
import json
from backend.config import settings

class Analytics:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def track_message(self, user_id: int, receiver_id: int):
        """Track message sent"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        await self.redis.hincrby(f"stats:user:{user_id}:daily:{today}", "messages_sent", 1)
        await self.redis.hincrby(f"stats:user:{receiver_id}:daily:{today}", "messages_received", 1)
        await self.redis.sadd(f"stats:active:{today}", user_id)
        await self.redis.sadd(f"stats:active:{today}", receiver_id)
    
    async def track_login(self, user_id: int):
        """Track user login"""
        today = datetime.now().strftime("%Y-%m-%d")
        await self.redis.hincrby(f"stats:user:{user_id}:daily:{today}", "logins", 1)
    
    async def get_user_stats(self, user_id: int, days: int = 7) -> dict:
        """Get user statistics for last N days"""
        stats = {}
        
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            data = await self.redis.hgetall(f"stats:user:{user_id}:daily:{date}")
            if data:
                stats[date] = {k.decode(): int(v) for k, v in data.items()}
        
        return stats
    
    async def get_global_stats(self) -> dict:
        """Get global statistics"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        return {
            "active_users": await self.redis.scard(f"stats:active:{today}"),
            "total_messages": await self.redis.get("stats:total:messages") or 0,
            "total_users": await self.redis.get("stats:total:users") or 0
        }
    
    async def update_daily_stats(self):
        """Update daily aggregated stats"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        active_count = await self.redis.scard(f"stats:active:{yesterday}")
        await self.redis.set(f"stats:daily:active:{yesterday}", active_count)

analytics = None
