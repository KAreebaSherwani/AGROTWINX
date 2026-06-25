# src/security/security_manager.py

"""
Security hardening for AgroTwinX
"""

import hashlib
import secrets
import re
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database

class SecurityManager:
    """
    Centralized security management
    """
    
    def __init__(self):
        self.db = Database()
        self._create_security_tables()
    
    def _create_security_tables(self):
        """Create security-related tables"""
        
        # API access logs
        self.db.query("""
            CREATE TABLE IF NOT EXISTS api_access_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                ip_address TEXT,
                endpoint TEXT,
                method TEXT,
                user_id INTEGER,
                status_code INTEGER,
                response_time REAL
            )
        """)
        
        # Rate limiting
        self.db.query("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                limit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                endpoint TEXT,
                request_count INTEGER DEFAULT 0,
                window_start TIMESTAMP NOT NULL,
                blocked BOOLEAN DEFAULT 0
            )
        """)
        
        # Admin users
        self.db.query("""
            CREATE TABLE IF NOT EXISTS admin_users (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                active BOOLEAN DEFAULT 1,
                last_login TIMESTAMP,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    # ============================================
    # PASSWORD SECURITY
    # ============================================
    
    def hash_password(self, password):
        """
        Hash password with salt
        Returns (hash, salt)
        """
        salt = secrets.token_hex(32)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        
        return (pwd_hash.hex(), salt)
    
    def verify_password(self, password, stored_hash, salt):
        """Verify password against stored hash"""
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        
        return pwd_hash.hex() == stored_hash
    
    def validate_password_strength(self, password):
        """
        Validate password meets security requirements
        Returns (valid, issues)
        """
        issues = []
        
        if len(password) < 8:
            issues.append("Password must be at least 8 characters")
        
        if not re.search(r'[A-Z]', password):
            issues.append("Password must contain uppercase letter")
        
        if not re.search(r'[a-z]', password):
            issues.append("Password must contain lowercase letter")
        
        if not re.search(r'[0-9]', password):
            issues.append("Password must contain number")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            issues.append("Password must contain special character")
        
        return (len(issues) == 0, issues)
    
    # ============================================
    # INPUT VALIDATION
    # ============================================
    
    def validate_phone_number(self, phone):
        """Validate Pakistani phone number"""
        pattern = r'^\+92[0-9]{10}$'
        return bool(re.match(pattern, phone))
    
    def sanitize_input(self, text):
        """Sanitize user input to prevent injection"""
        # Remove dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', ';', '--', '/*', '*/']
        
        sanitized = text
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')
        
        return sanitized.strip()
    
    def validate_coordinates(self, lat, lon):
        """Validate GPS coordinates for Pakistan"""
        # Pakistan bounds
        pakistan_bounds = {
            'lat_min': 23.5,
            'lat_max': 37.5,
            'lon_min': 60.5,
            'lon_max': 77.5
        }
        
        if not (pakistan_bounds['lat_min'] <= lat <= pakistan_bounds['lat_max']):
            return False
        
        if not (pakistan_bounds['lon_min'] <= lon <= pakistan_bounds['lon_max']):
            return False
        
        return True
    
    # ============================================
    # RATE LIMITING
    # ============================================
    
    def check_rate_limit(self, identifier, endpoint, limit=100, window_minutes=60):
        """
        Check if request is within rate limit
        Returns (allowed, remaining)
        """
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Get or create rate limit record
        existing = self.db.query(
            """
            SELECT * FROM rate_limits 
            WHERE identifier = ? AND endpoint = ?
            AND window_start >= ?
            """,
            (identifier, endpoint, window_start.isoformat())
        )
        
        if existing:
            record = existing[0]
            
            # Check if blocked
            if record['blocked']:
                return (False, 0)
            
            # Check count
            if record['request_count'] >= limit:
                # Block
                self.db.update(
                    'rate_limits',
                    'limit_id',
                    record['limit_id'],
                    {'blocked': 1}
                )
                return (False, 0)
            
            # Increment count
            new_count = record['request_count'] + 1
            self.db.update(
                'rate_limits',
                'limit_id',
                record['limit_id'],
                {'request_count': new_count}
            )
            
            return (True, limit - new_count)
        
        else:
            # Create new record
            self.db.insert('rate_limits', {
                'identifier': identifier,
                'endpoint': endpoint,
                'request_count': 1,
                'window_start': now.isoformat(),
                'blocked': 0
            })
            
            return (True, limit - 1)
    
    # ============================================
    # ACCESS LOGGING
    # ============================================
    
    def log_api_access(self, ip_address, endpoint, method, user_id=None, status_code=200, response_time=0):
        """Log API access"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'ip_address': ip_address,
            'endpoint': endpoint,
            'method': method,
            'user_id': user_id,
            'status_code': status_code,
            'response_time': response_time
        }
        
        self.db.insert('api_access_logs', log_data)
    
    def get_suspicious_activity(self, hours=24):
        """Get suspicious activity patterns"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # Multiple failed attempts
        failed_attempts = self.db.query(
            """
            SELECT ip_address, COUNT(*) as attempts
            FROM api_access_logs
            WHERE timestamp >= ? AND status_code >= 400
            GROUP BY ip_address
            HAVING attempts > 10
            ORDER BY attempts DESC
            """,
            (cutoff,)
        )
        
        return failed_attempts
    
    # ============================================
    # ADMIN MANAGEMENT
    # ============================================
    
    def create_admin(self, username, password, role='admin'):
        """Create admin user"""
        # Validate password
        valid, issues = self.validate_password_strength(password)
        if not valid:
            return (False, issues)
        
        # Check if username exists
        existing = self.db.query(
            "SELECT * FROM admin_users WHERE username = ?",
            (username,)
        )
        
        if existing:
            return (False, ["Username already exists"])
        
        # Hash password
        pwd_hash, salt = self.hash_password(password)
        
        # Create admin
        admin_data = {
            'username': username,
            'password_hash': pwd_hash,
            'salt': salt,
            'role': role,
            'active': 1
        }
        
        admin_id = self.db.insert('admin_users', admin_data)
        
        return (True, f"Admin created: {admin_id}")
    
    def authenticate_admin(self, username, password):
        """Authenticate admin user"""
        admin = self.db.query(
            "SELECT * FROM admin_users WHERE username = ? AND active = 1",
            (username,)
        )
        
        if not admin:
            return (False, "Invalid credentials")
        
        admin = admin[0]
        
        # Verify password
        if self.verify_password(password, admin['password_hash'], admin['salt']):
            # Update last login
            self.db.update(
                'admin_users',
                'admin_id',
                admin['admin_id'],
                {'last_login': datetime.now().isoformat()}
            )
            
            return (True, admin)
        
        return (False, "Invalid credentials")
    
    # ============================================
    # DATA ENCRYPTION
    # ============================================
    
    def encrypt_sensitive_data(self, data):
        """Encrypt sensitive data (simplified)"""
        # In production, use proper encryption library like cryptography
        import base64
        
        return base64.b64encode(data.encode()).decode()
    
    def decrypt_sensitive_data(self, encrypted_data):
        """Decrypt sensitive data"""
        import base64
        
        return base64.b64decode(encrypted_data.encode()).decode()

# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='AgroTwinX Security Manager')
    parser.add_argument('--create-admin', nargs=2, metavar=('USERNAME', 'PASSWORD'), help='Create admin user')
    parser.add_argument('--check-suspicious', action='store_true', help='Check for suspicious activity')
    parser.add_argument('--test-rate-limit', type=str, help='Test rate limiting for identifier')
    
    args = parser.parse_args()
    
    security = SecurityManager()
    
    if args.create_admin:
        username, password = args.create_admin
        success, result = security.create_admin(username, password)
        
        if success:
            print(f"✅ {result}")
        else:
            print(f"❌ Failed to create admin:")
            for issue in result:
                print(f"  - {issue}")
    
    elif args.check_suspicious:
        suspicious = security.get_suspicious_activity(hours=24)
        
        if suspicious:
            print(f"\n⚠️  Suspicious Activity (last 24h):")
            for activity in suspicious:
                print(f"  {activity['ip_address']}: {activity['attempts']} failed attempts")
        else:
            print("✅ No suspicious activity detected")
    
    elif args.test_rate_limit:
        identifier = args.test_rate_limit
        
        print(f"\n🧪 Testing rate limit for: {identifier}")
        
        for i in range(105):
            allowed, remaining = security.check_rate_limit(identifier, '/api/test', limit=100)
            
            if i % 10 == 0:
                print(f"  Request {i+1}: {'✅ Allowed' if allowed else '❌ Blocked'} (Remaining: {remaining})")
    
    else:
        print("Usage:")
        print("  python security_manager.py --create-admin admin password123")
        print("  python security_manager.py --check-suspicious")
        print("  python security_manager.py --test-rate-limit '192.168.1.1'")
        