"""
用户认证模块 - JWT 认证
"""
import logging
import jwt
import bcrypt
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from database import db, Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean

logger = logging.getLogger(__name__)

# JWT 配置
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

class User(Base):
    """用户表"""
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime)
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"

class AuthManager:
    """认证管理器"""
    
    def __init__(self):
        # 初始化用户表（安全模式，只创建不存在的表）
        from database import db
        try:
            Base.metadata.create_all(db.engine, checkfirst=True)
        except Exception as e:
            # 如果表已存在或有重复索引错误，忽略
            if "Duplicate key name" in str(e) or "already exists" in str(e):
                logger.info(f"用户表已存在，跳过创建: {e}")
            else:
                raise
    
    def create_user(self, username: str, email: str, password: str, full_name: str = "") -> bool:
        """创建新用户"""
        try:
            # 检查用户名是否已存在
            with db.get_session() as session:
                if session.query(User).filter_by(username=username).first():
                    logger.warning(f"用户名已存在: {username}")
                    return False
                
                if session.query(User).filter_by(email=email).first():
                    logger.warning(f"邮箱已存在: {email}")
                    return False
                
                # 创建用户
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                user = User(
                    username=username,
                    email=email,
                    password_hash=password_hash.decode('utf-8'),
                    full_name=full_name
                )
                session.add(user)
                session.commit()
                logger.info(f"用户创建成功: {username}")
                return True
        except Exception as e:
            logger.error(f"创建用户失败: {e}")
            return False
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """验证用户登录（单点登录）"""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(username=username).first()
                if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                    user.last_login = datetime.now()
                    session.commit()
                    logger.info(f"用户登录成功: {username}")
                    return user
                logger.warning(f"登录失败: {username}")
                return None
        except Exception as e:
            logger.error(f"认证失败: {e}")
            return None
    
    def create_token(self, user: User) -> str:
        """创建 JWT Token（单点登录：同时创建会话并使旧会话失效）"""
        expires_at = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        payload = {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'exp': expires_at,
            'jti': str(uuid.uuid4())  # 添加唯一ID确保每次token都不同
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        
        # 创建会话（单点登录：自动使旧会话失效）
        db.create_user_session(user.id, token, expires_at)
        
        return token
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 JWT Token（单点登录验证）"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            # 额外验证会话是否有效（单点登录检查）
            user_id = payload.get('user_id')
            if user_id is not None:
                valid_user_id = db.validate_session(token)
                if valid_user_id is None:
                    logger.warning("会话已失效（单点登录）")
                    return None
            
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token 已过期")
            return None
        except jwt.InvalidTokenError:
            logger.warning("无效的 Token")
            return None
        except Exception as e:
            logger.error(f"Token 验证失败: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """根据用户ID获取用户信息"""
        try:
            with db.get_session() as session:
                return session.query(User).filter_by(id=user_id).first()
        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            return None

    def update_profile(self, user_id: int, username: str = None, email: str = None, full_name: str = None) -> Dict[str, Any]:
        """更新用户资料"""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return {'success': False, 'message': '用户不存在'}

                if username and username != user.username:
                    if session.query(User).filter_by(username=username).first():
                        return {'success': False, 'message': '用户名已被占用'}
                    user.username = username

                if email and email != user.email:
                    if session.query(User).filter_by(email=email).first():
                        return {'success': False, 'message': '邮箱已被占用'}
                    user.email = email

                if full_name is not None:
                    user.full_name = full_name

                session.commit()
                logger.info(f"用户 {user_id} 资料更新成功")
                return {'success': True, 'message': '资料更新成功',
                        'username': user.username, 'email': user.email, 'full_name': user.full_name}
        except Exception as e:
            logger.error(f"更新用户资料失败: {e}")
            return {'success': False, 'message': str(e)}

    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
        """修改密码"""
        try:
            with db.get_session() as session:
                user = session.query(User).filter_by(id=user_id).first()
                if not user:
                    return {'success': False, 'message': '用户不存在'}

                if not bcrypt.checkpw(old_password.encode('utf-8'), user.password_hash.encode('utf-8')):
                    return {'success': False, 'message': '原密码错误'}

                user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                session.commit()
                logger.info(f"用户 {user_id} 密码修改成功")
                return {'success': True, 'message': '密码修改成功'}
        except Exception as e:
            logger.error(f"修改密码失败: {e}")
            return {'success': False, 'message': str(e)}

# 全局认证管理器实例
auth_manager = AuthManager()

# 初始化默认用户
def init_default_users():
    """初始化默认用户（首次运行时）"""
    with db.get_session() as session:
        if not session.query(User).filter_by(username='admin').first():
            auth_manager.create_user('admin', 'admin@example.com', 'admin123', '管理员')
            logger.info("默认管理员用户已创建: admin/admin123")

# 初始化默认用户
init_default_users()
