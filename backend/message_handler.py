from datetime import datetime, timedelta
import json
from typing import Dict, Any
from backend.database import db
from backend.websocket_manager import manager
from backend.tasks import celery_app
from backend.ai_assistant import AIAssistant
import asyncio

class MessageHandler:
    def __init__(self):
        self.typing_users = {}
        self.ai_assistant = AIAssistant()
    
    async def handle_text_message(self, sender_id: int, sender_name: str, data: Dict, websocket) -> Dict:
        """Handle text message with all features"""
        receiver_name = data.get("to")
        message_text = data.get("msg", "").strip()
        message_type = data.get("message_type", "text")
        
        # Spam detection
        if await self.is_spam(message_text):
            return {"error": "Message blocked due to spam"}
        
        # Get receiver info
        receiver = await db.get_user(username=receiver_name)
        if not receiver:
            return {"error": "User not found"}
        
        receiver_id = receiver["id"]
        
        # Check if blocked
        if await db.is_blocked(sender_id, receiver_id):
            return {"error": "You are blocked by this user"}
        
        # Process message
        reply_to = data.get("reply_to")
        expires_in = data.get("expires_in")  # Self-destruct after seconds
        
        # Save to database
        msg_data = await db.save_message(
            sender_id, receiver_id, message_text, 
            message_type=message_type,
            reply_to_id=reply_to,
            expires_in=expires_in
        )
        
        # Prepare payload
        payload = {
            "type": "message",
            "id": msg_data["id"],
            "message_id": msg_data["message_id"],
            "sender_id": sender_id,
            "sender_name": sender_name,
            "receiver_id": receiver_id,
            "receiver_name": receiver_name,
            "text": message_text,
            "message_type": message_type,
            "time": datetime.now().strftime("%H:%M"),
            "timestamp": datetime.now().isoformat(),
            "delivered": True
        }
        
        if reply_to:
            payload["reply_to"] = reply_to
        
        if expires_in:
            payload["expires_at"] = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
        
        # Send to receiver if online
        await manager.send_to_user(receiver_id, payload)
        
        # Send to sender
        await websocket.send_json(payload)
        
        # Process in background
        celery_app.send_task("process_message_async", args=[sender_id, receiver_id, message_text])
        
        # AI response if bot is mentioned
        if "@ai" in message_text.lower() and settings.ENABLE_AI_ASSISTANT:
            asyncio.create_task(self.handle_ai_response(sender_id, message_text, websocket))
        
        return payload
    
    async def handle_file_message(self, sender_id: int, sender_name: str, data: Dict, websocket) -> Dict:
        """Handle file/image/video messages"""
        file_url = data.get("file_url")
        file_name = data.get("file_name")
        file_type = data.get("file_type")
        file_size = data.get("file_size")
        
        # Save file info to database
        # Upload to cloud storage (handled separately)
        
        return {
            "type": "file",
            "file_url": file_url,
            "file_name": file_name,
            "file_type": file_type,
            "file_size": file_size
        }
    
    async def handle_voice_message(self, sender_id: int, sender_name: str, data: Dict, websocket):
        """Handle voice message"""
        voice_url = data.get("voice_url")
        duration = data.get("duration")
        
        return {
            "type": "voice",
            "voice_url": voice_url,
            "duration": duration
        }
    
    async def handle_typing_indicator(self, sender_id: int, data: Dict):
        """Handle typing indicator with debounce"""
        receiver_name = data.get("to")
        is_typing = data.get("is_typing", True)
        
        receiver = await db.get_user(username=receiver_name)
        if receiver:
            # Debounce typing events
            key = f"typing:{sender_id}:{receiver['id']}"
            if is_typing:
                await manager.redis_client.setex(key, 2, "1")
                await manager.send_to_user(receiver["id"], {
                    "type": "typing",
                    "from": sender_id,
                    "is_typing": True
                })
            else:
                await manager.redis_client.delete(key)
    
    async def handle_seen(self, user_id: int, data: Dict):
        """Handle message read receipts"""
        message_id = data.get("message_id")
        if message_id:
            await db.mark_message_as_read(message_id, user_id)
            
            # Notify sender
            message = await db.get_message(message_id)
            if message:
                await manager.send_to_user(message["sender_id"], {
                    "type": "seen",
                    "message_id": message_id,
                    "user_id": user_id,
                    "timestamp": datetime.now().isoformat()
                })
    
    async def handle_reaction(self, user_id: int, data: Dict):
        """Handle message reactions (emoji)"""
        message_id = data.get("message_id")
        emoji = data.get("emoji")
        
        await db.add_reaction(message_id, user_id, emoji)
        
        # Broadcast reaction to both users
        message = await db.get_message(message_id)
        if message:
            payload = {
                "type": "reaction",
                "message_id": message_id,
                "user_id": user_id,
                "emoji": emoji
            }
            await manager.send_to_user(message["sender_id"], payload)
            await manager.send_to_user(message["receiver_id"], payload)
    
    async def handle_delete_message(self, user_id: int, data: Dict):
        """Handle message deletion"""
        message_id = data.get("message_id")
        delete_for_everyone = data.get("delete_for_everyone", False)
        
        if delete_for_everyone:
            await db.soft_delete_message(message_id)
        else:
            await db.delete_for_me(message_id, user_id)
        
        # Notify other user
        message = await db.get_message(message_id)
        if message:
            await manager.send_to_user(
                message["sender_id"] if message["sender_id"] != user_id else message["receiver_id"],
                {"type": "message_deleted", "message_id": message_id}
            )
    
    async def handle_edit_message(self, user_id: int, data: Dict):
        """Handle message editing"""
        message_id = data.get("message_id")
        new_text = data.get("text")
        
        await db.edit_message(message_id, new_text)
        
        # Notify both users
        message = await db.get_message(message_id)
        if message:
            payload = {
                "type": "message_edited",
                "message_id": message_id,
                "new_text": new_text
            }
            await manager.send_to_user(message["sender_id"], payload)
            await manager.send_to_user(message["receiver_id"], payload)
    
    async def handle_forward_message(self, user_id: int, data: Dict):
        """Handle message forwarding"""
        original_message_id = data.get("message_id")
        to_user = data.get("to")
        
        original = await db.get_message(original_message_id)
        if original:
            receiver = await db.get_user(username=to_user)
            if receiver:
                await db.save_message(
                    user_id, receiver["id"],
                    original["message"],
                    message_type="forwarded",
                    forwarded_from=original_message_id
                )
    
    async def handle_poll(self, sender_id: int, data: Dict):
        """Handle polls/surveys"""
        question = data.get("question")
        options = data.get("options", [])
        expires_in = data.get("expires_in", 86400)  # 24 hours default
        
        poll_id = await db.create_poll(sender_id, question, options, expires_in)
        
        # Send to receiver
        receiver_name = data.get("to")
        receiver = await db.get_user(username=receiver_name)
        
        if receiver:
            await manager.send_to_user(receiver["id"], {
                "type": "poll",
                "poll_id": poll_id,
                "question": question,
                "options": options,
                "expires_at": (datetime.now() + timedelta(seconds=expires_in)).isoformat()
            })
    
    async def handle_poll_vote(self, user_id: int, data: Dict):
        """Handle poll votes"""
        poll_id = data.get("poll_id")
        option_index = data.get("option")
        
        await db.vote_poll(poll_id, user_id, option_index)
    
    async def handle_story(self, user_id: int, data: Dict):
        """Handle story/status update"""
        media_url = data.get("media_url")
        media_type = data.get("media_type")
        caption = data.get("caption")
        
        story_id = await db.create_story(user_id, media_url, media_type, caption)
        
        # Notify all online users
        await manager.broadcast({
            "type": "new_story",
            "user_id": user_id,
            "story_id": story_id
        }, exclude_user=user_id)
    
    async def handle_story_view(self, user_id: int, data: Dict):
        """Handle story view"""
        story_id = data.get("story_id")
        await db.view_story(story_id, user_id)
        
        # Notify story owner
        story = await db.get_story(story_id)
        if story:
            await manager.send_to_user(story["user_id"], {
                "type": "story_viewed",
                "story_id": story_id,
                "viewer_id": user_id
            })
    
    async def handle_create_group(self, user_id: int, data: Dict):
        """Handle group creation"""
        group_name = data.get("name")
        description = data.get("description")
        members = data.get("members", [])
        
        group_id = await db.create_group(group_name, user_id, description)
        
        for member_name in members:
            member = await db.get_user(username=member_name)
            if member:
                await db.add_group_member(group_id, member["id"])
        
        # Notify all group members
        for member in members:
            member_data = await db.get_user(username=member)
            if member_data:
                await manager.send_to_user(member_data["id"], {
                    "type": "group_created",
                    "group_id": group_id,
                    "name": group_name,
                    "created_by": user_id
                })
    
    async def handle_group_message(self, user_id: int, user_name: str, data: Dict):
        """Handle group message"""
        group_id = data.get("group_id")
        message_text = data.get("msg", "").strip()
        
        # Save group message
        msg_data = await db.save_group_message(group_id, user_id, message_text)
        
        # Get all group members
        members = await db.get_group_members(group_id)
        
        payload = {
            "type": "group_message",
            "id": msg_data["id"],
            "group_id": group_id,
            "sender_id": user_id,
            "sender_name": user_name,
            "text": message_text,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to all members
        for member in members:
            await manager.send_to_user(member["id"], payload)
    
    async def is_spam(self, message: str) -> bool:
        """Check if message is spam"""
        if not settings.ENABLE_SPAM_DETECTION:
            return False
        
        spam_keywords = ['viagra', 'casino', 'lottery', 'winner', 'click here', 'investment']
        return any(keyword in message.lower() for keyword in spam_keywords)
    
    async def handle_ai_response(self, user_id: int, message: str, websocket):
        """Handle AI assistant response"""
        response = await self.ai_assistant.get_response(user_id, message)
        await websocket.send_json({
            "type": "ai_response",
            "text": response,
            "sender": "AI Assistant"
        })

message_handler = MessageHandler()
