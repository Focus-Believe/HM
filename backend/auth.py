from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import pyotp
import qrcode
from io import BytesIO
import base64
import random
import string
from typing import Optional, Dict
from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: Dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=settings.JWT_EXPIRY_HOURS))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None

def generate_2fa_secret() -> str:
    return pyotp.random_base32()

def get_2fa_qr_code(secret: str, user_name: str) -> str:
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user_name, issuer_name=settings.TWO_FACTOR_APP_NAME)
    qr = qrcode.make(uri)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def verify_2fa(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def generate_reset_token() -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

def generate_verification_code() -> str:
    return ''.join(random.choices(string.digits, k=6))

# Session management
class SessionManager:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def create_session(self, user_id: int, token: str, device_info: Dict = None) -> str:
        session_id = generate_reset_token()
        await self.redis.hset(f"session:{session_id}", mapping={
            "user_id": str(user_id),
            "token": token,
            "device": json.dumps(device_info),
            "created_at": datetime.now().isoformat()
        })
        await self.redis.expire(f"session:{session_id}", 86400 * 7)  # 7 days
        return session_id
    
    async def validate_session(self, session_id: str) -> Optional[int]:
        data = await self.redis.hgetall(f"session:{session_id}")
        if data:
            return int(data.get(b"user_id", 0))
        return None
    
    async def revoke_session(self, session_id: str):
        await self.redis.delete(f"session:{session_id}")
    
    async def revoke_all_sessions(self, user_id: int):
        keys = await self.redis.keys(f"session:*")
        for key in keys:
            data = await self.redis.hgetall(key)
            if data and int(data.get(b"user_id", 0)) == user_id:
                await self.redis.delete(key)
