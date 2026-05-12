from agora_token_builder import RtcTokenBuilder
import random
from typing import Dict
from backend.config import settings

class VoiceVideoManager:
    def __init__(self):
        self.active_calls: Dict[str, Dict] = {}
        self.call_sessions: Dict[int, str] = {}  # user_id -> call_id
    
    def generate_agora_token(self, channel_name: str, user_id: int, role: str = "publisher") -> str:
        """Generate Agora token for voice/video calls"""
        if not settings.AGORA_APP_ID or not settings.AGORA_APP_CERTIFICATE:
            return None
        
        app_id = settings.AGORA_APP_ID
        app_certificate = settings.AGORA_APP_CERTIFICATE
        expiry = 3600  # 1 hour
        
        role_num = 1 if role == "publisher" else 2  # 1: publisher, 2: subscriber
        
        token = RtcTokenBuilder.buildTokenWithUid(
            app_id, app_certificate, channel_name, user_id, role_num, expiry
        )
        return token
    
    async def initiate_call(self, caller_id: int, receiver_id: int, call_type: str) -> Dict:
        """Initiate voice or video call"""
        call_id = f"call_{caller_id}_{receiver_id}_{int(datetime.now().timestamp())}"
        channel_name = f"channel_{call_id}"
        
        token = self.generate_agora_token(channel_name, caller_id)
        
        call_data = {
            "call_id": call_id,
            "caller_id": caller_id,
            "receiver_id": receiver_id,
            "call_type": call_type,  # "voice" or "video"
            "channel_name": channel_name,
            "status": "initiated",
            "started_at": datetime.now().isoformat(),
            "caller_token": token
        }
        
        self.active_calls[call_id] = call_data
        self.call_sessions[caller_id] = call_id
        
        return call_data
    
    async def accept_call(self, call_id: str, receiver_id: int) -> Dict:
        """Accept incoming call"""
        if call_id in self.active_calls:
            call = self.active_calls[call_id]
            call["status"] = "connected"
            call["accepted_at"] = datetime.now().isoformat()
            
            token = self.generate_agora_token(call["channel_name"], receiver_id)
            self.call_sessions[receiver_id] = call_id
            
            return {
                "call_id": call_id,
                "channel_name": call["channel_name"],
                "token": token,
                "call_type": call["call_type"]
            }
        return None
    
    async def reject_call(self, call_id: str, receiver_id: int):
        """Reject incoming call"""
        if call_id in self.active_calls:
            call = self.active_calls[call_id]
            call["status"] = "rejected"
            call["ended_at"] = datetime.now().isoformat()
            await self.end_call(call_id)
    
    async def end_call(self, call_id: str):
        """End active call"""
        if call_id in self.active_calls:
            call = self.active_calls[call_id]
            call["status"] = "ended"
            call["ended_at"] = datetime.now().isoformat()
            
            # Calculate duration
            start = datetime.fromisoformat(call["started_at"])
            end = datetime.fromisoformat(call["ended_at"])
            call["duration"] = int((end - start).total_seconds())
            
            # Remove from active calls
            del self.active_calls[call_id]
            
            # Clear sessions
            if call["caller_id"] in self.call_sessions:
                del self.call_sessions[call["caller_id"]]
            if call["receiver_id"] in self.call_sessions:
                del self.call_sessions[call["receiver_id"]]
            
            return call
        return None
    
    async def is_user_in_call(self, user_id: int) -> bool:
        """Check if user is currently in a call"""
        return user_id in self.call_sessions
    
    async def get_active_call(self, user_id: int) -> Dict:
        """Get active call for user"""
        if user_id in self.call_sessions:
            call_id = self.call_sessions[user_id]
            return self.active_calls.get(call_id)
        return None

voice_video_manager = VoiceVideoManager()
