from celery import Celery
from backend.config import settings
import redis
import json
from datetime import datetime

celery_app = Celery(
    "chat_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

@celery_app.task
def process_message_async(sender_id: int, receiver_id: int, message: str):
    """Process message in background"""
    # Update message count
    redis_client.hincrby(f"stats:user:{sender_id}", "messages_sent", 1)
    redis_client.hincrby(f"stats:user:{receiver_id}", "messages_received", 1)
    
    # Store for analytics
    redis_client.lpush("analytics:messages", json.dumps({
        "sender": sender_id,
        "receiver": receiver_id,
        "message": message[:100],
        "timestamp": datetime.now().isoformat()
    }))

@celery_app.task
def cleanup_expired_messages():
    """Delete expired messages"""
    from backend.database import db
    import asyncio
    asyncio.run(db.delete_expired_messages())

@celery_app.task
def generate_daily_report():
    """Generate daily analytics report"""
    stats = {
        "date": datetime.now().date().isoformat(),
        "total_messages": redis_client.get("stats:daily:messages") or 0,
        "active_users": redis_client.scard("stats:daily:active_users") or 0,
        "new_users": redis_client.get("stats:daily:new_users") or 0
    }
    
    # Save to database or send email
    redis_client.set(f"report:{datetime.now().date()}", json.dumps(stats))
    return stats
