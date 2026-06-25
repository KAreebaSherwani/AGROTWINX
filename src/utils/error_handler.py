# src/utils/error_handler.py

import time
import functools
import traceback
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database

class ErrorHandler:
    """
    Centralized error handling and recovery system
    """
    
    def __init__(self):
        self.db = Database()
        self._create_error_log_table()
    
    def _create_error_log_table(self):
        """Create error log table if doesn't exist"""
        self.db.query("""
            CREATE TABLE IF NOT EXISTS error_logs (
                error_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                error_type TEXT,
                error_message TEXT,
                stack_trace TEXT,
                context TEXT,
                severity TEXT,
                resolved BOOLEAN DEFAULT 0
            )
        """)
    
    def log_error(self, error, context="", severity="medium"):
        """Log error to database"""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'context': context,
            'severity': severity,
            'resolved': 0
        }
        
        try:
            self.db.insert('error_logs', error_data)
        except:
            # If DB insert fails, at least print to console
            print(f"❌ ERROR: {error_data}")
    
    def get_recent_errors(self, hours=24):
        """Get recent errors"""
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        return self.db.query(
            "SELECT * FROM error_logs WHERE timestamp >= ? ORDER BY timestamp DESC",
            (cutoff,)
        )

def retry_on_failure(max_retries=3, delay=5, backoff=2):
    """
    Decorator for automatic retry with exponential backoff
    
    Usage:
        @retry_on_failure(max_retries=3, delay=5, backoff=2)
        def my_function():
            # code that might fail
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                
                except Exception as e:
                    retries += 1
                    
                    if retries >= max_retries:
                        print(f"❌ {func.__name__} failed after {max_retries} attempts")
                        raise
                    
                    print(f"⚠️  {func.__name__} failed (attempt {retries}/{max_retries}): {e}")
                    print(f"   Retrying in {current_delay} seconds...")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        
        return wrapper
    return decorator

def safe_execute(func, *args, **kwargs):
    """
    Execute function safely with error handling
    Returns (success, result_or_error)
    """
    try:
        result = func(*args, **kwargs)
        return (True, result)
    except Exception as e:
        error_handler = ErrorHandler()
        error_handler.log_error(e, context=f"safe_execute: {func.__name__}")
        return (False, e)

# Example usage
@retry_on_failure(max_retries=3, delay=2)
def fetch_satellite_data_with_retry(lat, lon):
    """Example function with retry logic"""
    from src.satellite.gee_connector import GEEConnector
    
    gee = GEEConnector()
    return gee.get_observation_for_point(lat, lon, datetime.now())

# Test
if __name__ == "__main__":
    error_handler = ErrorHandler()
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_handler.log_error(e, context="Test", severity="low")
    
    # Show recent errors
    recent = error_handler.get_recent_errors(hours=24)
    print(f"\nRecent errors: {len(recent)}")
    
    for error in recent[:5]:
        print(f"\n{error['timestamp']}: {error['error_type']}")
        print(f"  Message: {error['error_message']}")
        print(f"  Context: {error['context']}")