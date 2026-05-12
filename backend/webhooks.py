import httpx
import hmac
import hashlib
import json
from typing import Dict, List
from backend.config import settings
import redis.asyncio as redis

class WebhookManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.webhook_retry_queue = []
    
    async def register_webhook(self, user_id: int, url: str, events: List[str], secret: str = None):
        """Register a webhook endpoint for user"""
        webhook_data = {
            "url": url,
            "events": events,
            "secret": secret or settings.WEBHOOK_SECRET,
            "created_at": datetime.now().isoformat()
        }
        await self.redis.hset(f"webhook:{user_id}", "config", json.dumps(webhook_data))
        await self.redis.hset(f"webhook:{user_id}", "active", "1")
    
    async def unregister_webhook(self, user_id: int):
        """Unregister webhook"""
        await self.redis.delete(f"webhook:{user_id}")
    
    async def trigger_webhook(self, user_id: int, event: str, data: Dict):
        """Trigger webhook for user"""
        webhook_data = await self.redis.hgetall(f"webhook:{user_id}")
        
        if webhook_data and webhook_data.get(b"active", b"0") == b"1":
            config = json.loads(webhook_data.get(b"config", b"{}"))
            
            if event in config.get("events", []):
                asyncio.create_task(self._send_webhook(
                    config["url"],
                    config["secret"],
                    event,
                    data
                ))
    
    async def _send_webhook(self, url: str, secret: str, event: str, data: Dict):
        """Send webhook with retry logic"""
        payload = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        # Generate signature
        signature = hmac.new(
            secret.encode(),
            json.dumps(payload).encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event
        }
        
        for attempt in range(3):  # Retry 3 times
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, headers=headers, timeout=10)
                    if response.status_code == 200:
                        break
            except Exception as e:
                print(f"Webhook attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

webhook_manager = None
