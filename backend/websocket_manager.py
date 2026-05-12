from typing import Dict, Set, Optional, Any
from fastapi import WebSocket
import asyncio
import json
from datetime import datetime
import redis.asyncio as redis
from backend.config import settings

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.user_metadata: Dict[int, Dict] = {}
        self.room_subscribers: Dict[str, Set[int]] = {}
        self._lock = asyncio.Lock()
        self.redis_client = None
    
    async def init_redis(self):
        self.redis_client = await redis.from_url(settings.REDIS_URL, decode_responses=True)
        # Start pub/sub listener
        asyncio.create_task(self._listen_pubsub())
    
    async def connect(self, user_id: int, websocket: WebSocket, metadata: Dict = None):
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
            self.user_metadata[user_id] = metadata or {}
            
            # Subscribe to user's private channel in Redis
            await self.redis_client.subscribe(f"user:{user_id}")
    
    async def disconnect(self, user_id: int, websocket: WebSocket):
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
                    del self.user_metadata[user_id]
                    await self.redis_client.unsubscribe(f"user:{user_id}")
    
    async def send_to_user(self, user_id: int, data: Dict, exclude_ws: WebSocket = None):
        """Send message to a specific user across all their devices"""
        if user_id in self.active_connections:
            for ws in self.active_connections[user_id]:
                if ws != exclude_ws:
                    try:
                        await ws.send_json(data)
                    except Exception as e:
                        print(f"Error sending to user {user_id}: {e}")
    
    async def send_to_room(self, room_id: str, data: Dict, exclude_user: int = None):
        """Send message to all users in a room/channel"""
        if room_id in self.room_subscribers:
            for user_id in self.room_subscribers[room_id]:
                if user_id != exclude_user:
                    await self.send_to_user(user_id, data)
    
    async def broadcast(self, data: Dict, exclude_user: int = None):
        """Broadcast to all connected users"""
        async with self._lock:
            for user_id in list(self.active_connections.keys()):
                if user_id != exclude_user:
                    await self.send_to_user(user_id, data)
    
    async def join_room(self, user_id: int, room_id: str):
        async with self._lock:
            if room_id not in self.room_subscribers:
                self.room_subscribers[room_id] = set()
            self.room_subscribers[room_id].add(user_id)
    
    async def leave_room(self, user_id: int, room_id: str):
        async with self._lock:
            if room_id in self.room_subscribers:
                self.room_subscribers[room_id].discard(user_id)
                if not self.room_subscribers[room_id]:
                    del self.room_subscribers[room_id]
    
    async def publish_to_redis(self, channel: str, data: Dict):
        """Publish message to Redis for cross-instance communication"""
        await self.redis_client.publish(channel, json.dumps(data))
    
    async def _listen_pubsub(self):
        """Listen to Redis pub/sub for cross-instance messages"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe("global")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                await self.broadcast(data)
    
    def get_online_users(self) -> List[int]:
        return list(self.active_connections.keys())
    
    def get_user_count(self) -> int:
        return len(self.active_connections)
    
    async def is_user_online(self, user_id: int) -> bool:
        return user_id in self.active_connections

manager = WebSocketManager()
