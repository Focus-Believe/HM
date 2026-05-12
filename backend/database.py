import asyncpg
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import json
from contextlib import asynccontextmanager
from backend.config import settings

class Database:
    def __init__(self):
        self.pool = None
        self.max_retries = 3
    
    async def connect(self):
        """Connect to database with retry logic"""
        for attempt in range(self.max_retries):
            try:
                self.pool = await asyncpg.create_pool(
                    settings.DATABASE_URL,
                    min_size=10,
                    max_size=settings.DATABASE_POOL_SIZE,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300,
                    command_timeout=60
                )
                await self.create_tables()
                await self.create_indexes()
                await self.create_triggers()
                print("✅ Database connected successfully")
                break
            except Exception as e:
                print(f"❌ Database connection attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2)
    
    async def create_tables(self):
        """Create all database tables"""
        async with self.pool.acquire() as conn:
            # Users table (enhanced)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE,
                    phone VARCHAR(20),
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(100),
                    avatar_url TEXT,
                    bio TEXT,
                    status VARCHAR(100),
                    is_online BOOLEAN DEFAULT FALSE,
                    last_seen TIMESTAMP,
                    is_verified BOOLEAN DEFAULT FALSE,
                    is_2fa_enabled BOOLEAN DEFAULT FALSE,
                    two_factor_secret VARCHAR(32),
                    email_verified BOOLEAN DEFAULT FALSE,
                    account_locked BOOLEAN DEFAULT FALSE,
                    login_attempts INTEGER DEFAULT 0,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_users_username (username),
                    INDEX idx_users_email (email),
                    INDEX idx_users_online (is_online)
                )
            """)
            
            # Messages table (enhanced)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    message_id UUID DEFAULT gen_random_uuid() UNIQUE,
                    sender_id INTEGER REFERENCES users(id),
                    receiver_id INTEGER REFERENCES users(id),
                    message TEXT,
                    message_type VARCHAR(20) DEFAULT 'text',
                    file_url TEXT,
                    file_name VARCHAR(255),
                    file_size INTEGER,
                    file_type VARCHAR(50),
                    thumbnail_url TEXT,
                    is_edited BOOLEAN DEFAULT FALSE,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    is_read BOOLEAN DEFAULT FALSE,
                    read_at TIMESTAMP,
                    delivered_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    reply_to_id INTEGER,
                    forwarded_from INTEGER,
                    reactions JSONB DEFAULT '{}',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_messages_users (sender_id, receiver_id, created_at),
                    INDEX idx_messages_search (message),
                    INDEX idx_messages_expiry (expires_at)
                )
            """)
            
            # Groups table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id SERIAL PRIMARY KEY,
                    group_id UUID DEFAULT gen_random_uuid() UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    avatar_url TEXT,
                    created_by INTEGER REFERENCES users(id),
                    is_private BOOLEAN DEFAULT FALSE,
                    max_members INTEGER DEFAULT 500,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Group members
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    role VARCHAR(20) DEFAULT 'member',
                    nickname VARCHAR(50),
                    muted_until TIMESTAMP,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (group_id, user_id)
                )
            """)
            
            # Group messages
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS group_messages (
                    id SERIAL PRIMARY KEY,
                    message_id UUID DEFAULT gen_random_uuid() UNIQUE,
                    group_id INTEGER REFERENCES groups(id),
                    sender_id INTEGER REFERENCES users(id),
                    message TEXT,
                    file_url TEXT,
                    reactions JSONB DEFAULT '{}',
                    is_deleted BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Calls table (Voice/Video)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    id SERIAL PRIMARY KEY,
                    call_id UUID DEFAULT gen_random_uuid() UNIQUE,
                    caller_id INTEGER REFERENCES users(id),
                    receiver_id INTEGER REFERENCES users(id),
                    call_type VARCHAR(10),
                    status VARCHAR(20),
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP,
                    duration INTEGER,
                    recording_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Blocks table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    blocker_id INTEGER REFERENCES users(id),
                    blocked_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (blocker_id, blocked_id)
                )
            """)
            
            # Friends/Contacts
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    user_id INTEGER REFERENCES users(id),
                    contact_id INTEGER REFERENCES users(id),
                    status VARCHAR(20) DEFAULT 'pending',
                    nickname VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, contact_id)
                )
            """)
            
            # Stories (Like WhatsApp Status)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stories (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    media_url TEXT,
                    media_type VARCHAR(10),
                    caption TEXT,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Story views
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS story_views (
                    story_id INTEGER REFERENCES stories(id),
                    user_id INTEGER REFERENCES users(id),
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (story_id, user_id)
                )
            """)
            
            # Notifications table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    type VARCHAR(50),
                    title VARCHAR(255),
                    body TEXT,
                    data JSONB,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_notifications_user (user_id, is_read, created_at)
                )
            """)
            
            # Bot conversations
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_conversations (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    bot_type VARCHAR(50),
                    context JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    async def create_indexes(self):
        """Create performance indexes"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_text_search 
                ON messages USING GIN (to_tsvector('english', message));
            """)
            
            await conn.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_full_text 
                ON users USING GIN (to_tsvector('english', username || ' ' || COALESCE(full_name, '')));
            """)
    
    async def create_triggers(self):
        """Create database triggers"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            await conn.execute("""
                DROP TRIGGER IF EXISTS update_users_updated_at ON users;
                CREATE TRIGGER update_users_updated_at
                    BEFORE UPDATE ON users
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at();
            """)
    
    # User CRUD operations
    async def create_user(self, username: str, email: str, password_hash: str, full_name: str = None) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            try:
                result = await conn.fetchrow(
                    """INSERT INTO users (username, email, password_hash, full_name) 
                       VALUES ($1, $2, $3, $4) 
                       RETURNING id, username, email, full_name, created_at""",
                    username, email, password_hash, full_name
                )
                return dict(result) if result else None
            except asyncpg.UniqueViolationError:
                return None
    
    async def get_user(self, user_id: int = None, username: str = None, email: str = None) -> Optional[Dict]:
        async with self.pool.acquire() as conn:
            if user_id:
                result = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            elif username:
                result = await conn.fetchrow("SELECT * FROM users WHERE username = $1", username)
            elif email:
                result = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
            else:
                return None
            return dict(result) if result else None
    
    async def update_online_status(self, user_id: int, is_online: bool):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET is_online = $1, last_seen = CURRENT_TIMESTAMP WHERE id = $2",
                is_online, user_id
            )
    
    # Message operations
    async def save_message(self, sender_id: int, receiver_id: int, message: str, 
                          message_type: str = 'text', file_url: str = None, 
                          reply_to_id: int = None, expires_in: int = None) -> Dict:
        async with self.pool.acquire() as conn:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in) if expires_in else None
            result = await conn.fetchrow(
                """INSERT INTO messages (sender_id, receiver_id, message, message_type, file_url, reply_to_id, expires_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id, message_id, created_at""",
                sender_id, receiver_id, message, message_type, file_url, reply_to_id, expires_at
            )
            return dict(result)
    
    async def get_messages(self, user1_id: int, user2_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT m.*, 
                          u1.username as sender_name, 
                          u2.username as receiver_name
                   FROM messages m
                   JOIN users u1 ON m.sender_id = u1.id
                   JOIN users u2 ON m.receiver_id = u2.id
                   WHERE (m.sender_id = $1 AND m.receiver_id = $2)
                      OR (m.sender_id = $2 AND m.receiver_id = $1)
                   AND m.is_deleted = FALSE
                   ORDER BY m.created_at DESC
                   LIMIT $3 OFFSET $4""",
                user1_id, user2_id, limit, offset
            )
            return [dict(row) for row in rows]
    
    async def add_reaction(self, message_id: int, user_id: int, emoji: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE messages 
                   SET reactions = jsonb_set(
                       COALESCE(reactions, '{}'::jsonb),
                       ARRAY[$1], 
                       COALESCE(reactions->$1, '0')::int + 1
                   )
                   WHERE id = $2""",
                emoji, message_id
            )
    
    async def search_messages(self, user_id: int, query: str) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT m.*, u.username as other_user
                   FROM messages m
                   JOIN users u ON (u.id = m.sender_id OR u.id = m.receiver_id) AND u.id != $1
                   WHERE (m.sender_id = $1 OR m.receiver_id = $1)
                   AND m.message ILIKE $2
                   AND m.is_deleted = FALSE
                   ORDER BY m.created_at DESC
                   LIMIT 100""",
                user_id, f"%{query}%"
            )
            return [dict(row) for row in rows]
    
    # Group operations
    async def create_group(self, name: str, created_by: int, description: str = None, is_private: bool = False) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "INSERT INTO groups (name, description, created_by, is_private) VALUES ($1, $2, $3, $4) RETURNING id",
                name, description, created_by, is_private
            )
            group_id = result['id']
            await conn.execute(
                "INSERT INTO group_members (group_id, user_id, role) VALUES ($1, $2, 'admin')",
                group_id, created_by
            )
            return group_id
    
    async def get_group_members(self, group_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT u.id, u.username, u.full_name, u.avatar_url, gm.role, gm.nickname
                   FROM group_members gm
                   JOIN users u ON gm.user_id = u.id
                   WHERE gm.group_id = $1""",
                group_id
            )
            return [dict(row) for row in rows]
    
    # Call operations
    async def create_call(self, caller_id: int, receiver_id: int, call_type: str) -> str:
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow(
                "INSERT INTO calls (caller_id, receiver_id, call_type, status) VALUES ($1, $2, $3, 'initiated') RETURNING call_id",
                caller_id, receiver_id, call_type
            )
            return result['call_id']
    
    async def update_call_status(self, call_id: str, status: str, duration: int = None):
        async with self.pool.acquire() as conn:
            if status in ['completed', 'missed', 'rejected']:
                await conn.execute(
                    "UPDATE calls SET status = $1, ended_at = CURRENT_TIMESTAMP, duration = $2 WHERE call_id = $3",
                    status, duration, call_id
                )
            else:
                await conn.execute(
                    "UPDATE calls SET status = $1 WHERE call_id = $2",
                    status, call_id
                )
    
    # Notification operations
    async def create_notification(self, user_id: int, notification_type: str, title: str, body: str, data: dict = None):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO notifications (user_id, type, title, body, data) VALUES ($1, $2, $3, $4, $5)",
                user_id, notification_type, title, body, json.dumps(data) if data else None
            )
    
    async def get_notifications(self, user_id: int, limit: int = 20) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM notifications WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id, limit
            )
            return [dict(row) for row in rows]
    
    # Story operations
    async def create_story(self, user_id: int, media_url: str, media_type: str, caption: str = None, expires_in_hours: int = 24):
        async with self.pool.acquire() as conn:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
            result = await conn.fetchrow(
                "INSERT INTO stories (user_id, media_url, media_type, caption, expires_at) VALUES ($1, $2, $3, $4, $5) RETURNING id",
                user_id, media_url, media_type, caption, expires_at
            )
            return result['id']
    
    async def get_active_stories(self, user_id: int) -> List[Dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT s.*, u.username, u.avatar_url,
                          EXISTS(SELECT 1 FROM story_views sv WHERE sv.story_id = s.id AND sv.user_id = $1) as viewed
                   FROM stories s
                   JOIN users u ON s.user_id = u.id
                   WHERE s.expires_at > CURRENT_TIMESTAMP
                   ORDER BY s.user_id, s.created_at DESC""",
                user_id
            )
            return [dict(row) for row in rows]
    
    async def view_story(self, story_id: int, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO story_views (story_id, user_id) VALUES ($1, $2) ON CON
