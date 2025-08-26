from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import secrets
import hashlib
from cryptography.fernet import Fernet
import base64

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 加密密钥（用于敏感数据加密）
ENCRYPTION_KEY = base64.urlsafe_b64encode(settings.SECRET_KEY.encode()[:32].ljust(32, b'0'))
cipher_suite = Fernet(ENCRYPTION_KEY)


class PasswordManager:
    """密码管理器"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_password(length: int = 12) -> str:
        """生成随机密码"""
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))


class TokenManager:
    """JWT令牌管理器"""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """创建刷新令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """验证令牌"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            
            # 检查令牌类型
            if payload.get("type") != token_type:
                raise AuthenticationError("无效的令牌类型")
            
            # 检查过期时间
            exp = payload.get("exp")
            if exp is None:
                raise AuthenticationError("令牌缺少过期时间")
            
            if datetime.utcnow() > datetime.fromtimestamp(exp):
                raise AuthenticationError("令牌已过期")
            
            return payload
            
        except JWTError as e:
            raise AuthenticationError(f"令牌验证失败: {str(e)}")
    
    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """解码令牌（不验证）"""
        try:
            # 即使不验证签名，也需要提供key参数，这里使用一个占位符密钥
            return jwt.decode(token, "", options={"verify_signature": False})
        except JWTError:
            return None


class DataEncryption:
    """数据加密工具"""
    
    @staticmethod
    def encrypt_data(data: str) -> str:
        """加密数据"""
        if not data:
            return ""
        return cipher_suite.encrypt(data.encode()).decode()
    
    @staticmethod
    def decrypt_data(encrypted_data: str) -> str:
        """解密数据"""
        if not encrypted_data:
            return ""
        try:
            return cipher_suite.decrypt(encrypted_data.encode()).decode()
        except Exception:
            raise ValueError("数据解密失败")
    
    @staticmethod
    def hash_data(data: str) -> str:
        """哈希数据（不可逆）"""
        return hashlib.sha256(data.encode()).hexdigest()


class SecurityValidator:
    """安全验证器"""
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """验证密码强度"""
        result = {
            "is_valid": True,
            "score": 0,
            "errors": [],
            "suggestions": []
        }
        
        # 长度检查
        if len(password) < 8:
            result["errors"].append("密码长度至少8位")
            result["is_valid"] = False
        else:
            result["score"] += 20
        
        # 复杂性检查
        if not any(c.islower() for c in password):
            result["errors"].append("密码必须包含小写字母")
            result["is_valid"] = False
        else:
            result["score"] += 20
        
        if not any(c.isupper() for c in password):
            result["errors"].append("密码必须包含大写字母")
            result["is_valid"] = False
        else:
            result["score"] += 20
        
        if not any(c.isdigit() for c in password):
            result["errors"].append("密码必须包含数字")
            result["is_valid"] = False
        else:
            result["score"] += 20
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            result["suggestions"].append("建议包含特殊字符以提高安全性")
        else:
            result["score"] += 20
        
        # 常见弱密码检查
        weak_passwords = ["123456", "password", "123456789", "qwerty", "abc123"]
        if password.lower() in weak_passwords:
            result["errors"].append("密码过于简单，请使用更复杂的密码")
            result["is_valid"] = False
            result["score"] = 0
        
        return result
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """验证邮箱格式"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_username(username: str) -> Dict[str, Any]:
        """验证用户名"""
        result = {
            "is_valid": True,
            "errors": []
        }
        
        # 长度检查
        if len(username) < 3:
            result["errors"].append("用户名长度至少3位")
            result["is_valid"] = False
        elif len(username) > 50:
            result["errors"].append("用户名长度不能超过50位")
            result["is_valid"] = False
        
        # 字符检查
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            result["errors"].append("用户名只能包含字母、数字、下划线和横线")
            result["is_valid"] = False
        
        # 保留字检查
        reserved_words = ["admin", "root", "system", "api", "www", "mail", "ftp"]
        if username.lower() in reserved_words:
            result["errors"].append("用户名不能使用保留字")
            result["is_valid"] = False
        
        return result


class RateLimiter:
    """简单的速率限制器"""
    
    def __init__(self):
        self.attempts = {}
    
    def is_allowed(self, key: str, max_attempts: int, window_seconds: int) -> bool:
        """检查是否允许请求"""
        now = datetime.utcnow()
        
        if key not in self.attempts:
            self.attempts[key] = []
        
        # 清理过期的尝试记录
        cutoff = now - timedelta(seconds=window_seconds)
        self.attempts[key] = [attempt for attempt in self.attempts[key] if attempt > cutoff]
        
        # 检查是否超过限制
        if len(self.attempts[key]) >= max_attempts:
            return False
        
        # 记录新的尝试
        self.attempts[key].append(now)
        return True
    
    def get_remaining_attempts(self, key: str, max_attempts: int, window_seconds: int) -> int:
        """获取剩余尝试次数"""
        now = datetime.utcnow()
        
        if key not in self.attempts:
            return max_attempts
        
        # 清理过期的尝试记录
        cutoff = now - timedelta(seconds=window_seconds)
        self.attempts[key] = [attempt for attempt in self.attempts[key] if attempt > cutoff]
        
        return max(0, max_attempts - len(self.attempts[key]))


# 全局实例
password_manager = PasswordManager()
token_manager = TokenManager()
data_encryption = DataEncryption()
security_validator = SecurityValidator()
rate_limiter = RateLimiter()