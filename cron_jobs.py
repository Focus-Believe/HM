import asyncio
from datetime import datetime
from backend.database import db
from backend.config import settings

async def daily_cleanup():
    """প্রতিদিনের ক্লিনআপ কাজ"""
    print(f"[CRON] Running daily cleanup at {datetime.now()}")
    
    # ১. এক্সপায়ার্ড মেসেজ ডিলিট
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM messages WHERE expires_at < CURRENT_TIMESTAMP"
        )
        print(f"Deleted expired messages")
    
    # ২. এক্সপায়ার্ড স্টোরিজ ডিলিট
    async with db.pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM stories WHERE expires_at < CURRENT_TIMESTAMP"
        )
        print(f"Deleted expired stories")
    
    # ৩. ডেইলি অ্যানালিটিক্স জেনারেট
    from backend.analytics import analytics
    await analytics.update_daily_stats()
    
    # ৪. ইনঅ্যাক্টিভ ইউজারদের স্ট্যাটাস আপডেট
    async with db.pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_online = FALSE WHERE last_seen < NOW() - INTERVAL '1 day'"
        )
    
    print(f"[CRON] Cleanup completed at {datetime.now()}")

async def daily_backup():
    """ডাটাবেস ব্যাকআপ"""
    print(f"[CRON] Starting database backup at {datetime.now()}")
    # এখানে S3 বা অন্য জায়গায় ব্যাকআপ আপলোড করার কোড দিতে হবে
    print(f"[CRON] Backup completed")

async def main():
    await daily_cleanup()
    await daily_backup()

if __name__ == "__main__":
    asyncio.run(main())
