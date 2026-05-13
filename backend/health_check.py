from fastapi import APIRouter, HTTPException
from datetime import datetime
import asyncio
import os
import psutil
from backend.database import db
from backend.websocket_manager import manager

router = APIRouter()

def get_uptime():
    """সিস্টেম কতক্ষণ চালু আছে"""
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            return f"{days}d {hours}h {minutes}m"
    except:
        return "Unknown"

def get_online_users():
    """অনলাইনে কত ইউজার আছে"""
    return manager.get_user_count() if manager else 0

@router.get("/health")
async def health_check():
    """হেলথ চেক এন্ডপয়েন্ট - Render-এর জন্য"""
    
    health_status = {
        "status": "healthy",
        "app": "Hey MIN",
        "version": "2.0.0",
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "metrics": {},
        "alerts": []
    }
    
    # 1. Database Check
    try:
        async with db.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        health_status["services"]["database"] = "✅ connected"
    except Exception as e:
        health_status["services"]["database"] = f"❌ disconnected: {str(e)}"
        health_status["status"] = "unhealthy"
        health_status["alerts"].append(f"Database error: {str(e)}")
    
    # 2. Redis Check
    try:
        if manager and manager.redis_client:
            await manager.redis_client.ping()
            health_status["services"]["redis"] = "✅ connected"
        else:
            health_status["services"]["redis"] = "⚠️ not initialized"
    except Exception as e:
        health_status["services"]["redis"] = f"❌ disconnected: {str(e)}"
        health_status["status"] = "unhealthy"
        health_status["alerts"].append(f"Redis error: {str(e)}")
    
    # 3. System Metrics
    try:
        health_status["metrics"] = {
            "online_users": get_online_users(),
            "uptime": get_uptime(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent if os.name != 'nt' else 0
        }
        
        # Check thresholds
        if health_status["metrics"]["cpu_percent"] > 80:
            health_status["alerts"].append("⚠️ High CPU usage")
        if health_status["metrics"]["memory_percent"] > 80:
            health_status["alerts"].append("⚠️ High memory usage")
            
    except Exception as e:
        health_status["metrics"]["error"] = str(e)
    
    # 4. WebSocket Status
    health_status["services"]["websocket"] = "✅ active" if manager else "⚠️ inactive"
    
    return health_status

@router.get("/health/simple")
async def simple_health():
    """সিম্পল হেলথ চেক (Render-এর জন্য)"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@router.get("/metrics")
async def get_metrics():
    """Prometheus মেট্রিক্স এন্ডপয়েন্ট"""
    return {
        "online_users": get_online_users(),
        "database_pool_size": db.pool.get_size() if db.pool else 0,
        "timestamp": datetime.now().isoformat()
    }
