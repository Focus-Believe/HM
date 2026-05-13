from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import json
from datetime import datetime, timedelta
from typing import Optional
import redis.asyncio as redis
import sentry_sdk

from backend.config import settings
from backend.database import db
from backend.auth import *
from backend.websocket_manager import manager
from backend.message_handler import message_handler
from backend.voice_video import voice_video_manager
from backend.rate_limiter import limiter, AdvancedRateLimiter
from backend.webhooks import webhook_manager
from backend.ai_assistant import AIAssistant
from backend.tasks import celery_app
from backend.analytics import analytics
from backend.payments import payment_manager
from backend.health_check import router as health_router  # ✅ নতুন যোগ করো

# ==================== SENTRY ERROR MONITORING ====================
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        traces_sample_rate=1.0
    )

# ==================== RATE LIMITER INIT ====================
rate_limiter = AdvancedRateLimiter(None)

# ==================== LIFESPAN MANAGER ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Hey MIN Application...")
    
    # Connect to database
    await db.connect()
    print("✅ Database connected")
    
    # Connect to Redis
    redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
    manager.redis_client = redis_client
    await manager.init_redis()
    print("✅ Redis connected")
    
    # Initialize rate limiter with Redis
    rate_limiter.redis = redis_client
    
    # Initialize webhook manager
    global webhook_manager
    webhook_manager = WebhookManager(redis_client)
    
    # Start background workers
    asyncio.create_task(cleanup_expired_messages())
    asyncio.create_task(cleanup_expired_stories())
    asyncio.create_task(update_analytics())
    
    print(f"✅ Hey MIN started on {settings.APP_ENV} mode")
    print(f"📊 Features: AI={settings.ENABLE_AI_ASSISTANT}, Calls={settings.ENABLE_VOICE_CALLS}")
    
    yield
    
    # Shutdown
    await db.close()
    await redis_client.close()
    print("👋 Hey MIN shutdown")

# ==================== FASTAPI APP ====================
app = FastAPI(
    title="Hey MIN",
    description="Enterprise Chat Application",
    version="2.0.0",
    lifespan=lifespan
)

# ==================== HEALTH CHECK ROUTER ====================
app.include_router(health_router)  # ✅ নতুন যোগ করো

# ==================== RATE LIMITING ====================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ==================== CORS MIDDLEWARE ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== STATIC FILES ====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ==================== BACKGROUND TASKS ====================

async def cleanup_expired_messages():
    """Clean up expired messages"""
    while True:
        await asyncio.sleep(3600)  # Every hour
        async with db.pool.acquire() as conn:
            await conn.execute("DELETE FROM messages WHERE expires_at < CURRENT_TIMESTAMP")
            print("🧹 Cleaned expired messages")

async def cleanup_expired_stories():
    """Clean up expired stories"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        async with db.pool.acquire() as conn:
            await conn.execute("DELETE FROM stories WHERE expires_at < CURRENT_TIMESTAMP")
            print("🧹 Cleaned expired stories")

async def update_analytics():
    """Update analytics data"""
    while True:
        await asyncio.sleep(3600)
        if analytics:
            await analytics.update_daily_stats()
            print("📊 Updated analytics")

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post("/api/auth/register")
@limiter.limit(f"{settings.RATE_LIMIT_LOGIN}/minute")
async def register(request: Request, username: str, email: str, password: str, full_name: str = None):
    """Register new user"""
    # Validation
    if len(username) < 3 or len(username) > 50:
        raise HTTPException(400, "Username must be 3-50 characters")
    
    if len(password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    if "@" not in email:
        raise HTTPException(400, "Invalid email")
    
    # Create user
    password_hash = get_password_hash(password)
    user = await db.create_user(username, email, password_hash, full_name)
    
    if not user:
        raise HTTPException(400, "Username or email already exists")
    
    # Create access token
    token = create_access_token({"user_id": user["id"], "username": user["username"]})
    
    return {
        "ok": True,
        "user": user,
        "access_token": token,
        "token_type": "bearer"
    }

@app.post("/api/auth/login")
@limiter.limit(f"{settings.RATE_LIMIT_LOGIN}/minute")
async def login(request: Request, username: str, password: str, two_factor_code: str = None):
    """Login user"""
    # Check rate limit
    if not await rate_limiter.check_login_attempts(username):
        raise HTTPException(429, "Too many login attempts. Try again later.")
    
    # Get user
    user = await db.get_user(username=username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    
    # Check if account is locked
    if user.get("account_locked"):
        raise HTTPException(403, "Account is locked. Contact support")
    
    # 2FA verification
    if user.get("is_2fa_enabled"):
        if not two_factor_code or not verify_2fa(user["two_factor_secret"], two_factor_code):
            return JSONResponse({
                "ok": False,
                "requires_2fa": True,
                "message": "2FA code required"
            }, status_code=401)
    
    # Update last login
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP, login_attempts = 0 WHERE id = $1", user["id"])
    
    # Create token
    token = create_access_token({
        "user_id": user["id"],
        "username": user["username"],
        "email": user["email"]
    })
    
    return {
        "ok": True,
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "full_name": user.get("full_name"),
            "avatar_url": user.get("avatar_url", "/static/default-avatar.png")
        }
    }

@app.post("/api/auth/2fa/enable")
async def enable_2fa(user_id: int):
    """Enable 2FA for user"""
    user = await db.get_user(user_id=user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    secret = generate_2fa_secret()
    qr_code = get_2fa_qr_code(secret, user["username"])
    
    return {
        "secret": secret,
        "qr_code": qr_code
    }

@app.post("/api/auth/2fa/verify")
async def verify_2fa_setup(user_id: int, secret: str, code: str):
    """Verify and enable 2FA"""
    if verify_2fa(secret, code):
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET two_factor_secret = $1, is_2fa_enabled = TRUE WHERE id = $2",
                secret, user_id
            )
        return {"ok": True}
    return {"ok": False, "error": "Invalid code"}

@app.post("/api/auth/logout")
async def logout(user_id: int):
    """Logout user"""
    await db.update_online_status(user_id, False)
    return {"ok": True}

# ==================== USER ENDPOINTS ====================

@app.get("/api/users")
@limiter.limit("30/minute")
async def get_users(request: Request, user_id: int, search: str = None):
    """Get all users or search users"""
    if search:
        users = await db.search_users(search, user_id)
    else:
        users = await db.get_all_users(user_id)
    
    # Add online status
    online_users = manager.get_online_users()
    for user in users:
        user["is_online"] = user["id"] in online_users
    
    return JSONResponse(users)

@app.get("/api/users/{user_id}/profile")
async def get_user_profile(user_id: int, current_user_id: int):
    """Get user profile"""
    user = await db.get_user(user_id=user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    # Remove sensitive info
    user.pop("password_hash", None)
    user.pop("two_factor_secret", None)
    
    # Check if blocked
    is_blocked = await db.is_blocked(current_user_id, user_id)
    user["is_blocked"] = is_blocked
    
    return user

@app.put("/api/users/profile")
async def update_profile(user_id: int, full_name: str = None, bio: str = None, avatar_url: str = None):
    """Update user profile"""
    async with db.pool.acquire() as conn:
        if full_name:
            await conn.execute("UPDATE users SET full_name = $1 WHERE id = $2", full_name, user_id)
        if bio:
            await conn.execute("UPDATE users SET bio = $1 WHERE id = $2", bio, user_id)
        if avatar_url:
            await conn.execute("UPDATE users SET avatar_url = $1 WHERE id = $2", avatar_url, user_id)
    
    return {"ok": True}

# ==================== MESSAGE ENDPOINTS ====================

@app.get("/api/messages/{user1_id}/{user2_id}")
@limiter.limit("60/minute")
async def get_messages(request: Request, user1_id: int, user2_id: int, limit: int = 50, offset: int = 0):
    """Get message history between two users"""
    # Check if blocked
    if await db.is_blocked(user1_id, user2_id):
        raise HTTPException(403, "You are blocked by this user")
    
    messages = await db.get_messages(user1_id, user2_id, limit, offset)
    return JSONResponse(messages)

@app.delete("/api/messages/{message_id}")
async def delete_message(message_id: int, user_id: int, delete_for_everyone: bool = False):
    """Delete a message"""
    await message_handler.handle_delete_message(user_id, {
        "message_id": message_id,
        "delete_for_everyone": delete_for_everyone
    })
    return {"ok": True}

@app.put("/api/messages/{message_id}")
async def edit_message(message_id: int, user_id: int, text: str):
    """Edit a message"""
    await message_handler.handle_edit_message(user_id, {
        "message_id": message_id,
        "text": text
    })
    return {"ok": True}

@app.post("/api/messages/{message_id}/react")
async def add_reaction(message_id: int, user_id: int, emoji: str):
    """Add reaction to message"""
    await message_handler.handle_reaction(user_id, {
        "message_id": message_id,
        "emoji": emoji
    })
    return {"ok": True}

@app.get("/api/messages/search")
async def search_messages(user_id: int, query: str):
    """Search messages"""
    results = await db.search_messages(user_id, query)
    return JSONResponse(results)

# ==================== GROUP ENDPOINTS ====================

@app.post("/api/groups")
async def create_group(user_id: int, name: str, description: str = None, members: list = None):
    """Create a new group"""
    group_id = await db.create_group(name, user_id, description)
    
    if members:
        for member_name in members:
            member = await db.get_user(username=member_name)
            if member and member["id"] != user_id:
                await db.add_group_member(group_id, member["id"])
    
    return {"group_id": group_id, "name": name}

@app.get("/api/groups/{group_id}")
async def get_group(group_id: int, user_id: int):
    """Get group details"""
    group = await db.get_group(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    
    members = await db.get_group_members(group_id)
    group["members"] = members
    
    return group

@app.post("/api/groups/{group_id}/members")
async def add_group_member(group_id: int, user_id: int, member_username: str):
    """Add member to group"""
    member = await db.get_user(username=member_username)
    if not member:
        raise HTTPException(404, "User not found")
    
    await db.add_group_member(group_id, member["id"])
    return {"ok": True}

# ==================== CALL ENDPOINTS ====================

@app.post("/api/calls/initiate")
async def initiate_call(user_id: int, receiver_name: str, call_type: str):
    """Initiate voice/video call"""
    receiver = await db.get_user(username=receiver_name)
    if not receiver:
        raise HTTPException(404, "User not found")
    
    call_data = await voice_video_manager.initiate_call(user_id, receiver["id"], call_type)
    
    # Notify receiver
    await manager.send_to_user(receiver["id"], {
        "type": "incoming_call",
        "call_id": call_data["call_id"],
        "caller_id": user_id,
        "call_type": call_type,
        "channel_name": call_data["channel_name"],
        "token": call_data["caller_token"]
    })
    
    return call_data

@app.post("/api/calls/{call_id}/accept")
async def accept_call(call_id: str, user_id: int):
    """Accept incoming call"""
    call = await voice_video_manager.accept_call(call_id, user_id)
    if not call:
        raise HTTPException(404, "Call not found")
    
    return call

@app.post("/api/calls/{call_id}/end")
async def end_call(call_id: str, user_id: int):
    """End active call"""
    call = await voice_video_manager.end_call(call_id)
    return call

# ==================== STORY ENDPOINTS ====================

@app.post("/api/stories")
async def create_story(user_id: int, media_url: str, media_type: str, caption: str = None):
    """Create a story/status"""
    story_id = await db.create_story(user_id, media_url, media_type, caption)
    
    # Notify all online users
    await manager.broadcast({
        "type": "new_story",
        "user_id": user_id,
        "story_id": story_id
    }, exclude_user=user_id)
    
    return {"story_id": story_id}

@app.get("/api/stories")
async def get_stories(user_id: int):
    """Get active stories"""
    stories = await db.get_active_stories(user_id)
    return JSONResponse(stories)

# ==================== BLOCK ENDPOINTS ====================

@app.post("/api/block/{blocked_username}")
async def block_user(user_id: int, blocked_username: str):
    """Block a user"""
    blocked = await db.get_user(username=blocked_username)
    if not blocked:
        raise HTTPException(404, "User not found")
    
    await db.block_user(user_id, blocked["id"])
    return {"ok": True}

@app.delete("/api/block/{blocked_username}")
async def unblock_user(user_id: int, blocked_username: str):
    """Unblock a user"""
    blocked = await db.get_user(username=blocked_username)
    if not blocked:
        raise HTTPException(404, "User not found")
    
    await db.unblock_user(user_id, blocked["id"])
    return {"ok": True}

# ==================== NOTIFICATION ENDPOINTS ====================

@app.get("/api/notifications")
async def get_notifications(user_id: int, limit: int = 20):
    """Get user notifications"""
    notifications = await db.get_notifications(user_id, limit)
    return JSONResponse(notifications)

# ==================== AI ASSISTANT ====================

@app.post("/api/ai/chat")
async def ai_chat(user_id: int, message: str):
    """Chat with AI assistant"""
    ai = AIAssistant()
    response = await ai.get_response(user_id, message)
    return {"response": response}

# ==================== FILE UPLOAD ====================

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user_id: int = None):
    """Upload file (image/video/document)"""
    # Validate file size
    content = await file.read()
    
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large. Max size: {settings.MAX_FILE_SIZE / 1024 / 1024}MB")
    
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type not allowed. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")
    
    # Generate unique filename
    filename = f"{user_id}_{datetime.now().timestamp()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(filepath, "wb") as f:
        f.write(content)
    
    # Generate URL
    file_url = f"/uploads/{filename}"
    
    return {
        "file_url": file_url,
        "file_name": file.filename,
        "file_size": len(content),
        "file_type": ext[1:]
    }

# ==================== WEBSOCKET ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for real-time communication"""
    # Authenticate
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    user_id = payload.get("user_id")
    username = payload.get("username")
    
    if not user_id:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    # Accept connection
    await websocket.accept()
    await manager.connect(user_id, websocket, {"username": username})
    await db.update_online_status(user_id, True)
    
    # Send online status to all
    await manager.broadcast({
        "type": "user_online",
        "user_id": user_id,
        "username": username
    }, exclude_user=user_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            # Route message based on type
            if msg_type == "dm":
                await message_handler.handle_text_message(user_id, username, data, websocket)
            
            elif msg_type == "typing":
                await message_handler.handle_typing_indicator(user_id, data)
            
            elif msg_type == "seen":
                await message_handler.handle_seen(user_id, data)
            
            elif msg_type == "react":
                await message_handler.handle_reaction(user_id, data)
            
            elif msg_type == "delete":
                await message_handler.handle_delete_message(user_id, data)
            
            elif msg_type == "edit":
                await message_handler.handle_edit_message(user_id, data)
            
            elif msg_type == "group_message":
                await message_handler.handle_group_message(user_id, username, data)
            
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
            
            elif msg_type == "webrtc_offer" or msg_type == "webrtc_answer":
                # WebRTC signaling
                target_id = data.get("target_id")
                await manager.send_to_user(target_id, data)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # Cleanup
        await manager.disconnect(user_id, websocket)
        await db.update_online_status(user_id, False)
        await manager.broadcast({
            "type": "user_offline",
            "user_id": user_id,
            "username": username
        })

# ==================== SIMPLE HEALTH CHECK (Render-এর জন্য) ====================

@app.get("/health")
async def simple_health():
    """Simple health check for Render"""
    return {
        "status": "ok",
        "app": "Hey MIN",
        "timestamp": datetime.now().isoformat()
    }

# ==================== FRONTEND ROUTES ====================

@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/chat")
async def chat():
    return FileResponse(os.path.join(FRONTEND_DIR, "chat.html"))

@app.get("/groups")
async def groups():
    return FileResponse(os.path.join(FRONTEND_DIR, "groups.html"))

@app.get("/profile")
async def profile():
    return FileResponse(os.path.join(FRONTEND_DIR, "profile.html"))

@app.get("/calls")
async def calls():
    return FileResponse(os.path.join(FRONTEND_DIR, "calls.html"))

# ==================== RUN SERVER ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
)
