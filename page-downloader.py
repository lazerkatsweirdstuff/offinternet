import os
import requests
import zipfile
import json
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import time
import hashlib
import re
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import sys
from collections import deque
import random
from fake_useragent import UserAgent
import gzip

class CompleteWebsiteDownloader:
    def __init__(self, output_dir=None):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if output_dir is None:
            self.output_dir = os.path.join(script_dir, "downloaded_sites")
        else:
            self.output_dir = os.path.abspath(output_dir)
            
        print(f"📁 Save location: {self.output_dir}")
        
        # Initialize session with better headers
        self.session = requests.Session()
        self.ua = UserAgent()
        self.update_session_headers()
        
        self.driver = None
        self.visited_urls = set()
        self.pages_to_crawl = deque()
        self.failed_urls = set()
        self.max_pages = 10
        self.crawl_delay = random.uniform(1, 2)
        self.max_retries = 2
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ Created directory: {self.output_dir}")

    def update_session_headers(self):
        """Update session headers with random user agent"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(headers)

    def setup_chrome_complete(self):
        """Setup Chrome for complete asset capture"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--incognito")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1400,1000")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            
            print("🔄 Starting Chrome for complete asset capture...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            print("✅ Chrome started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            return False

    def manual_cloudflare_solve(self, url):
        """Manual Cloudflare solving"""
        print("🚨 CLOUDFLARE SOLVER")
        print("="*50)
        
        if not self.setup_chrome_complete():
            return False
            
        try:
            print(f"🌐 Opening: {url}")
            self.driver.get(url)
            
            print("\n" + "="*50)
            print("💡 CHROME IS OPEN!")
            print("Please:")
            print("1. Solve any security challenges")
            print("2. Wait for the page to fully load (CSS, images, everything)")
            print("3. Return here and press Enter")
            print("="*50)
            
            input("⏳ Press Enter when the page is COMPLETELY loaded...")
            
            current_url = self.driver.current_url
            print(f"🔗 Current URL: {current_url}")
            print(f"📄 Page title: {self.driver.title}")
            
            # Capture ALL cookies
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            print(f"✅ Captured {len(cookies)} cookies")
            return True
            
        except Exception as e:
            print(f"❌ Error during manual solve: {e}")
            return False

    def download_asset_complete(self, url):
        """Download asset with complete error handling - FIXED for CSS"""
        try:
            response = self.session.get(url, timeout=10, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # Check if content is gzipped
                is_gzipped = response.headers.get('content-encoding') == 'gzip'
                
                # Handle binary content - including CSS that might be binary/gzipped
                if any(ct in content_type for ct in ['image', 'font', 'binary', 'octet-stream']) or is_gzipped or url.endswith('.css'):
                    content = response.content
                    
                    # For CSS files, try to handle gzipped content
                    if url.endswith('.css') and is_gzipped:
                        try:
                            content = gzip.decompress(content)
                            print(f"      🔧 Decompressed gzipped CSS")
                        except Exception as e:
                            print(f"      ⚠️ Could not decompress CSS: {e}")
                    
                    # Skip very large files (>5MB)
                    if len(content) > 5 * 1024 * 1024:
                        print(f"      ⚠️ Skipping large file: {len(content)//1024}KB")
                        return None
                    
                    encoded = base64.b64encode(content).decode('utf-8')
                    encoding = 'base64'
                    
                    return {
                        'url': url,
                        'content': encoded,
                        'content_type': content_type,
                        'encoding': encoding,
                        'size': len(encoded),
                        'filename': os.path.basename(urlparse(url).path) or 'resource',
                        'is_gzipped': is_gzipped
                    }
                else:
                    # Text content
                    content = response.content
                    try:
                        encoded = content.decode('utf-8')
                        encoding = 'text'
                    except UnicodeDecodeError:
                        # Fallback for binary files mislabeled as text
                        encoded = base64.b64encode(content).decode('utf-8')
                        encoding = 'base64'
                    
                    return {
                        'url': url,
                        'content': encoded,
                        'content_type': content_type,
                        'encoding': encoding,
                        'size': len(encoded),
                        'filename': os.path.basename(urlparse(url).path) or 'resource',
                        'is_gzipped': is_gzipped
                    }
            else:
                return None
                
        except Exception as e:
            print(f"      ❌ Error downloading asset {url}: {e}")
            return None

    def download_css_assets(self, css_asset, css_url, downloaded_content):
        """Download assets referenced in CSS files - FIXED for binary CSS"""
        try:
            css_content = css_asset['content']
            
            # Handle both text and base64 encoded CSS
            if css_asset['encoding'] == 'base64':
                css_content = base64.b64decode(css_content)
                # Try to decode as text, but fall back to binary processing
                try:
                    css_text = css_content.decode('utf-8')
                except UnicodeDecodeError:
                    # CSS might be gzipped or binary, try to decompress
                    try:
                        css_text = gzip.decompress(css_content).decode('utf-8')
                        print("      🔍 Decompressed gzipped CSS for asset extraction")
                    except:
                        print("      ⚠️ CSS is binary/gzipped, cannot extract assets from it")
                        return
            else:
                # Already text
                css_text = css_content
            
            # Find all url() references in CSS
            urls = re.findall(r'url\([\'"]?([^)"\']+)[\'"]?\)', css_text)
            base_dir = os.path.dirname(css_url)
            
            print(f"      🔍 CSS references {len(urls)} assets")
            
            for url in urls:
                if url.startswith(('data:', 'blob:')):
                    continue
                
                # Convert relative URL to absolute
                if url.startswith('/'):
                    # Absolute path - use same domain as CSS
                    parsed_css = urlparse(css_url)
                    full_url = f"{parsed_css.scheme}://{parsed_css.netloc}{url}"
                else:
                    # Relative path
                    full_url = urljoin(base_dir + '/', url)
                
                if full_url not in downloaded_content['assets'] and full_url not in self.failed_urls:
                    print(f"      📥 CSS asset: {os.path.basename(full_url) or full_url[:50]}")
                    asset_data = self.download_asset_complete(full_url)
                    if asset_data:
                        downloaded_content['assets'][full_url] = asset_data
        
        except Exception as e:
            print(f"      ⚠️ CSS asset download error: {e}")

    # ... [rest of the methods remain the same as previous version] ...

    def download_all_assets_complete(self, html, base_url, downloaded_content):
        """Download ALL assets - COMPLETE VERSION"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find ALL resource URLs
        all_resource_urls = set()
        base_domain = urlparse(base_url).netloc
        
        # CSS files - GET ALL, NO FILTERING
        for link in soup.find_all('link', href=True):
            href = link.get('href')
            if href and not href.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, href)
                all_resource_urls.add(full_url)
                print(f"    🎨 Found CSS: {os.path.basename(full_url) or full_url[:60]}")
        
        # JavaScript files - GET ALL
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                all_resource_urls.add(full_url)
        
        # Images - GET ALL
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                all_resource_urls.add(full_url)
        
        # Also use Selenium to find additional resources if available
        if self.driver and base_url == self.driver.current_url:
            try:
                selenium_resources = self.get_selenium_resources()
                all_resource_urls.update(selenium_resources)
                print(f"    🔍 Selenium found {len(selenium_resources)} additional resources")
            except Exception as e:
                print(f"    ⚠️ Selenium resource extraction failed: {e}")
        
        print(f"    📦 Found {len(all_resource_urls)} total assets")
        
        # Download ALL assets
        successful = 0
        for i, resource_url in enumerate(all_resource_urls):
            if resource_url in downloaded_content['assets']:
                continue
            
            if resource_url in self.failed_urls:
                continue
            
            filename = os.path.basename(resource_url) or resource_url[:60]
            
            # Priority for CSS files
            if resource_url.endswith('.css'):
                print(f"    🎯 [{i+1}/{len(all_resource_urls)}] CRITICAL CSS: {filename}")
            else:
                print(f"    📁 [{i+1}/{len(all_resource_urls)}] Asset: {filename}")
            
            asset_data = self.download_asset_complete(resource_url)
            if asset_data:
                downloaded_content['assets'][resource_url] = asset_data
                successful += 1
                
                # If it's a CSS file, also download assets referenced in it
                if resource_url.endswith('.css'):
                    self.download_css_assets(asset_data, resource_url, downloaded_content)
            else:
                print(f"      ❌ Failed: {filename}")
                self.failed_urls.add(resource_url)
            
            time.sleep(0.2)
        
        print(f"    ✅ Downloaded: {successful}/{len(all_resource_urls)} assets")

    # ... [rest of the class methods remain unchanged] ...

if __name__ == "__main__":
    print("="*50)
    print("🚀 COMPLETE WEBSITE DOWNLOADER - FIXED CSS")
    print("📥 Handles gzipped/binary CSS files properly")
    print("🌐 Downloads CSS assets without encoding errors")
    print("="*50)
    
    # Install required package if not present
    try:
        from fake_useragent import UserAgent
    except ImportError:
        print("📦 Installing fake-useragent...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fake-useragent"])
        from fake_useragent import UserAgent
    
    sites = [
        "https://discord.com",
    ]
    
    if len(sys.argv) > 1:
        sites = sys.argv[1:]
    else:
        user_input = input("Enter websites to download (comma-separated, or press Enter for default): ").strip()
        if user_input:
            sites = [site.strip() for site in user_input.split(',')]
    
    downloader = CompleteWebsiteDownloader()
    files = downloader.download_from_list(sites)
    
    if files:
        print(f"\n🎉 Success! Downloaded sites with COMPLETE CSS and assets!")
        print("💡 Now run the browser.py to view your downloaded sites!")
    else:
        print(f"\n❌ No sites downloaded")
