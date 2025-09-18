import os
import sys
import sqlite3
import shutil
from pathlib import Path
import tempfile
import json
from datetime import datetime

COOKIES_TEMP_DIR = os.path.join(tempfile.gettempdir(), 'YouTubeDownloader_Cookies')
os.makedirs(COOKIES_TEMP_DIR, exist_ok=True)

class CookieCollectorStandalone:
    def __init__(self):
        self.collected_cookies = []
        self.browser_paths = self._get_browser_paths()

    def _get_browser_paths(self):
        paths = {}
        home = Path.home()
        if sys.platform == "win32":
            appdata = os.environ.get('APPDATA', '')
            localappdata = os.environ.get('LOCALAPPDATA', '')
            paths = {
                'chrome': Path(localappdata) / 'Google' / 'Chrome' / 'User Data',
                'edge': Path(localappdata) / 'Microsoft' / 'Edge' / 'User Data',
                'firefox': Path(appdata) / 'Mozilla' / 'Firefox' / 'Profiles',
                'opera': Path(appdata) / 'Opera Software' / 'Opera Stable',
                'brave': Path(localappdata) / 'BraveSoftware' / 'Brave-Browser' / 'User Data',
            }
        return {k: str(v) for k, v in paths.items() if v.exists()}

    def collect_all_cookies(self):
        self.collected_cookies = []
        for browser, path in self.browser_paths.items():
            try:
                if browser in ['chrome', 'edge', 'brave']:
                    self._collect_chrome_cookies(browser, path)
                elif browser == 'firefox':
                    self._collect_firefox_cookies(browser, path)
            except Exception as e:
                print(f"Failed to collect cookies from {browser}: {e}")
        self._save_cookies_to_temp()
        return len(self.collected_cookies)

    def _collect_chrome_cookies(self, browser, path):
        cookie_db = os.path.join(path, 'Default', 'Cookies')
        if not os.path.exists(cookie_db):
            return
        try:
            temp_db = os.path.join(COOKIES_TEMP_DIR, f'{browser}_cookies.db')
            shutil.copy2(cookie_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            query = "SELECT name, value, host_key, path, expires_utc, is_secure, is_httponly FROM cookies"
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                name, value, domain, path, expires, secure, httponly = row
                if expires > 0:
                    expires = (expires - 11644473600000000) / 1000000
                else:
                    expires = 0
                cookie = {
                    'name': name,
                    'value': value,
                    'domain': domain,
                    'path': path or '/',
                    'expires': expires,
                    'secure': bool(secure),
                    'httponly': bool(httponly)
                }
                self.collected_cookies.append(cookie)
            conn.close()
            os.remove(temp_db)
        except Exception as e:
            print(f"Error collecting Chrome cookies: {e}")

    def _collect_firefox_cookies(self, browser, path):
        profiles = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
        if not profiles:
            return
        profile_path = os.path.join(path, profiles[0])
        cookie_db = os.path.join(profile_path, 'cookies.sqlite')
        if not os.path.exists(cookie_db):
            return
        try:
            conn = sqlite3.connect(cookie_db)
            cursor = conn.cursor()
            query = "SELECT name, value, host, path, expiry, isSecure, isHttpOnly FROM moz_cookies"
            cursor.execute(query)
            rows = cursor.fetchall()
            for row in rows:
                name, value, domain, path, expires, secure, httponly = row
                cookie = {
                    'name': name,
                    'value': value,
                    'domain': domain,
                    'path': path or '/',
                    'expires': expires or 0,
                    'secure': bool(secure),
                    'httponly': bool(httponly)
                }
                self.collected_cookies.append(cookie)
            conn.close()
        except Exception as e:
            print(f"Error collecting Firefox cookies: {e}")

    def _save_cookies_to_temp(self):
        if not self.collected_cookies:
            print("No cookies found.")
            return
        cookies_txt = os.path.join(COOKIES_TEMP_DIR, 'cookies.txt')
        with open(cookies_txt, 'w', encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write(f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for cookie in self.collected_cookies:
                domain = cookie['domain']
                domain_flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = cookie['path']
                secure = 'TRUE' if cookie['secure'] else 'FALSE'
                expires = str(int(cookie['expires'])) if cookie['expires'] > 0 else '0'
                name = cookie['name']
                value = cookie['value']
                f.write(f"{domain}\t{domain_flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        cookies_json = os.path.join(COOKIES_TEMP_DIR, 'cookies.json')
        with open(cookies_json, 'w', encoding='utf-8') as f:
            json.dump(self.collected_cookies, f, indent=2, ensure_ascii=False)
        print(f"Collected {len(self.collected_cookies)} cookies. Saved to {cookies_txt}")

if __name__ == "__main__":
    cc = CookieCollectorStandalone()
    count = cc.collect_all_cookies()
    print(f"Total cookies collected: {count}")
