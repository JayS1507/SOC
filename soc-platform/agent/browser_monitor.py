"""
Cross-Platform Browser History Monitor
Supports Chrome, Firefox, Edge, Brave on Windows and Linux
"""

import os
import sys
import sqlite3
import shutil
import glob
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

try:
    from shared.os_abstraction import get_os
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent))
    from shared.os_abstraction import get_os

class BrowserHistoryMonitor:
    """Cross-platform browser history monitoring"""
    
    def __init__(self, allowed_domains: List[str] = None, check_interval_hours: int = 1):
        """
        Initialize browser history monitor
        
        Args:
            allowed_domains: List of domains to collect (empty = all domains)
            check_interval_hours: How often to check browser history
        """
        self.os_helper = get_os()
        self.allowed_domains = allowed_domains or []
        self.check_interval_hours = check_interval_hours
        self.browser_paths = self.os_helper.get_browser_history_paths()
        self.last_check = {}
        self.temp_dir = Path(self.os_helper.get_temp_dir()) / "soc_browser"
        self.temp_dir.mkdir(exist_ok=True)
    
    def collect_history(self, browsers: List[str] = None) -> List[Dict]:
        """
        Collect browser history
        
        Args:
            browsers: List of browser names (chrome, firefox, edge, brave) or None for all
        
        Returns:
            List of history entries
        """
        if browsers is None:
            browsers = list(self.browser_paths.keys())
        
        all_history = []
        
        for browser in browsers:
            if browser not in self.browser_paths:
                continue
            
            try:
                history = self._collect_browser_history(browser)
                all_history.extend(history)
            except Exception as e:
                print(f"[BrowserHistory] Error collecting {browser}: {e}")
        
        return all_history
    
    def _collect_browser_history(self, browser: str) -> List[Dict]:
        """Collect history from specific browser"""
        history = []
        paths = self.browser_paths.get(browser, [])
        
        for path_pattern in paths:
            # Expand glob patterns
            if '*' in path_pattern:
                matched_paths = glob.glob(path_pattern)
            else:
                matched_paths = [path_pattern] if os.path.exists(path_pattern) else []
            
            for db_path in matched_paths:
                if not os.path.exists(db_path):
                    continue
                
                try:
                    # Copy database to temp (browsers lock the DB)
                    temp_db = self.temp_dir / f"{browser}_{Path(db_path).name}_{os.getpid()}.db"
                    shutil.copy2(db_path, temp_db)
                    
                    # Query history
                    if browser in ['chrome', 'edge', 'brave']:
                        entries = self._query_chromium_history(str(temp_db), browser)
                    elif browser == 'firefox':
                        entries = self._query_firefox_history(str(temp_db))
                    else:
                        entries = []
                    
                    history.extend(entries)
                    
                    # Clean up temp file
                    temp_db.unlink(missing_ok=True)
                
                except Exception as e:
                    print(f"[BrowserHistory] Error reading {db_path}: {e}")
        
        return history
    
    def _query_chromium_history(self, db_path: str, browser: str) -> List[Dict]:
        """Query Chromium-based browser history"""
        entries = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get last check time for this browser
            last_timestamp = self.last_check.get(browser, 0)
            
            # Chromium stores timestamps as microseconds since 1601-01-01
            # Convert to Unix timestamp: (chromium_time / 1000000) - 11644473600
            query = """
                SELECT url, title, visit_count, last_visit_time
                FROM urls
                WHERE last_visit_time > ?
                ORDER BY last_visit_time DESC
                LIMIT 1000
            """
            
            cursor.execute(query, (last_timestamp,))
            
            for row in cursor.fetchall():
                url, title, visit_count, chromium_time = row
                
                # Convert Chromium timestamp to Unix timestamp
                unix_timestamp = (chromium_time / 1000000.0) - 11644473600
                timestamp = datetime.fromtimestamp(unix_timestamp).isoformat()
                
                # Filter by domain if specified
                if self.allowed_domains and not self._is_allowed_domain(url):
                    continue
                
                entries.append({
                    "timestamp": timestamp,
                    "browser": browser,
                    "url": url,
                    "title": title or "(No title)",
                    "visit_count": visit_count
                })
                
                # Update last check correctly to be the absolute maximum seen
                if chromium_time > self.last_check.get(browser, 0):
                    self.last_check[browser] = chromium_time
            
            conn.close()
        
        except Exception as e:
            print(f"[BrowserHistory] Error querying Chromium DB: {e}")
        
        return entries
    
    def _query_firefox_history(self, db_path: str) -> List[Dict]:
        """Query Firefox history"""
        entries = []
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get last check time
            last_timestamp = self.last_check.get('firefox', 0)
            
            # Firefox stores timestamps as microseconds since Unix epoch
            query = """
                SELECT url, title, visit_count, last_visit_date
                FROM moz_places
                WHERE last_visit_date > ?
                ORDER BY last_visit_date DESC
                LIMIT 1000
            """
            
            cursor.execute(query, (last_timestamp,))
            
            for row in cursor.fetchall():
                url, title, visit_count, firefox_time = row
                
                if firefox_time is None:
                    continue
                
                # Convert Firefox timestamp (microseconds) to seconds
                unix_timestamp = firefox_time / 1000000.0
                timestamp = datetime.fromtimestamp(unix_timestamp).isoformat()
                
                # Filter by domain
                if self.allowed_domains and not self._is_allowed_domain(url):
                    continue
                
                entries.append({
                    "timestamp": timestamp,
                    "browser": "firefox",
                    "url": url,
                    "title": title or "(No title)",
                    "visit_count": visit_count
                })
                
                # Update last check correctly
                if firefox_time > self.last_check.get('firefox', 0):
                    self.last_check['firefox'] = firefox_time
            
            conn.close()
        
        except Exception as e:
            print(f"[BrowserHistory] Error querying Firefox DB: {e}")
        
        return entries
    
    def _is_allowed_domain(self, url: str) -> bool:
        """Check if URL matches allowed domains"""
        if not self.allowed_domains:
            return True  # No filter = allow all
        
        url_lower = url.lower()
        for domain in self.allowed_domains:
            if domain.lower() in url_lower:
                return True
        
        return False
    
    def cleanup_temp_files(self):
        """Clean up temporary database files"""
        try:
            for temp_file in self.temp_dir.glob("*.db"):
                temp_file.unlink(missing_ok=True)
        except Exception as e:
            print(f"[BrowserHistory] Cleanup error: {e}")

def format_for_soc(entry: Dict) -> str:
    """Format browser history entry for SOC platform"""
    return (
        f"[{entry['timestamp']}] "
        f"Browser={entry['browser']} "
        f"URL={entry['url'][:100]} "
        f"Title=\"{entry['title'][:50]}\""
    )

# Test
if __name__ == "__main__":
    print(f"[BrowserHistory] Running on {sys.platform}")
    
    monitor = BrowserHistoryMonitor()
    
    print("[BrowserHistory] Collecting history...")
    history = monitor.collect_history()
    
    print(f"[BrowserHistory] Found {len(history)} entries")
    
    # Show last 10 entries
    for entry in history[:10]:
        print(format_for_soc(entry))
    
    monitor.cleanup_temp_files()
    print("[BrowserHistory] Test completed")
