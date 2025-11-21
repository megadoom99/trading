import bcrypt
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def ensure_admin_user(self, username: str, email: str, password: str) -> bool:
        """
        Ensure admin user exists. Creates it if not found.
        Called on app startup to initialize single-user system.
        """
        if not self.db.database_url:
            logger.warning("Database not available. Cannot create admin user.")
            return False
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM users WHERE username = %s
                    """, (username,))
                    
                    if cur.fetchone():
                        logger.info(f"Admin user '{username}' already exists")
                        return True
                    
                    logger.info(f"Creating admin user '{username}'...")
                    user_id = self.create_user(username, email, password)
                    
                    if user_id:
                        logger.info(f"Admin user created successfully (ID: {user_id})")
                        return True
                    else:
                        logger.error("Failed to create admin user")
                        return False
        except Exception as e:
            logger.error(f"Error ensuring admin user: {e}")
            return False
    
    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def create_user(self, username: str, email: str, password: str) -> Optional[int]:
        if not self.db.database_url:
            return None
        
        try:
            password_hash = self.hash_password(password)
            
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO users (username, email, password_hash)
                        VALUES (%s, %s, %s)
                        RETURNING id
                    """, (username, email, password_hash))
                    
                    user_id = cur.fetchone()[0]
                    
                    cur.execute("""
                        INSERT INTO user_settings (user_id)
                        VALUES (%s)
                    """, (user_id,))
                    
                    logger.info(f"Created user: {username} (ID: {user_id})")
                    return user_id
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None
    
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        if not self.db.database_url:
            return None
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, username, email, password_hash
                        FROM users
                        WHERE username = %s
                    """, (username,))
                    
                    result = cur.fetchone()
                    if not result:
                        logger.warning(f"Login attempt for non-existent user: {username}")
                        return None
                    
                    user_id, username, email, password_hash = result
                    
                    if not self.verify_password(password, password_hash):
                        logger.warning(f"Failed login attempt for user: {username}")
                        return None
                    
                    cur.execute("""
                        UPDATE users
                        SET last_login = %s
                        WHERE id = %s
                    """, (datetime.now(), user_id))
                    
                    logger.info(f"User logged in: {username}")
                    return {
                        'id': user_id,
                        'username': username,
                        'email': email
                    }
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_user_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        if not self.db.database_url:
            return None
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT openrouter_api_key, finnhub_api_key, preferred_model,
                               ibkr_host, ibkr_port, default_currency
                        FROM user_settings
                        WHERE user_id = %s
                    """, (user_id,))
                    
                    result = cur.fetchone()
                    if not result:
                        return None
                    
                    return {
                        'openrouter_api_key': result[0],
                        'finnhub_api_key': result[1],
                        'preferred_model': result[2],
                        'ibkr_host': result[3],
                        'ibkr_port': result[4],
                        'default_currency': result[5]
                    }
        except Exception as e:
            logger.error(f"Failed to get user settings: {e}")
            return None
    
    def update_user_settings(self, user_id: int, settings: Dict[str, Any]) -> bool:
        if not self.db.database_url:
            return False
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    fields = []
                    values = []
                    
                    if 'openrouter_api_key' in settings:
                        fields.append("openrouter_api_key = %s")
                        values.append(settings['openrouter_api_key'])
                    if 'finnhub_api_key' in settings:
                        fields.append("finnhub_api_key = %s")
                        values.append(settings['finnhub_api_key'])
                    if 'preferred_model' in settings:
                        fields.append("preferred_model = %s")
                        values.append(settings['preferred_model'])
                    if 'ibkr_host' in settings:
                        fields.append("ibkr_host = %s")
                        values.append(settings['ibkr_host'])
                    if 'ibkr_port' in settings:
                        fields.append("ibkr_port = %s")
                        values.append(settings['ibkr_port'])
                    if 'default_currency' in settings:
                        fields.append("default_currency = %s")
                        values.append(settings['default_currency'])
                    
                    if not fields:
                        return True
                    
                    fields.append("updated_at = %s")
                    values.append(datetime.now())
                    values.append(user_id)
                    
                    query = f"""
                        UPDATE user_settings
                        SET {', '.join(fields)}
                        WHERE user_id = %s
                    """
                    
                    cur.execute(query, values)
                    logger.info(f"Updated settings for user {user_id}")
                    return True
        except Exception as e:
            logger.error(f"Failed to update user settings: {e}")
            return False
