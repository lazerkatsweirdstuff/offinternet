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
import logging
from fake_useragent import UserAgent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BalancedWebsiteDownloader:
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
        self.max_pages = 300  # Reasonable limit
        self.crawl_delay = random.uniform(1, 3)  # Balanced delay
        self.max_retries = 2
        self.domain_assets = set()  # Track assets we've found
        
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

    def setup_chrome_balanced(self):
        """Setup Chrome with balanced options"""
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
            
            print("🔄 Starting Chrome...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Stealth modifications
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.driver.implicitly_wait(10)
            print("✅ Chrome started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            return False

    def extract_all_links_balanced(self, html, base_url):
        """Extract ALL links but filter obvious junk"""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        base_domain = urlparse(base_url).netloc
        
        # Get all anchor tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                full_url = urljoin(base_url, href)
                
                # Clean URL
                clean_url = self.clean_url(full_url)
                
                # Basic validation
                if (clean_url.startswith(('http://', 'https://')) and 
                    base_domain in clean_url and
                    not self.is_likely_junk(clean_url)):
                    links.add(clean_url)
        
        return links

    def is_likely_junk(self, url):
        """Filter out obviously junk URLs"""
        junk_patterns = [
            '/cdn-cgi/', '/wp-admin/', '/wp-json/', '/administrator/', 
            '/phpmyadmin/', '/server-status/', '.pdf', '.zip', '.exe',
            '/api/', '/ajax/', '/graphql', '/websocket', '/.env',
            'click', 'track', 'affiliate', 'promo', 'banner'
        ]
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in junk_patterns)

    def clean_url(self, url):
        """Clean URL but keep important parameters"""
        try:
            parsed = urlparse(url)
            
            # Remove fragment only
            cleaned = parsed._replace(fragment='')
            
            # Keep most parameters but remove obvious trackers
            if parsed.query:
                params = []
                for param in parsed.query.split('&'):
                    key = param.split('=')[0].lower()
                    # Remove only the worst trackers
                    if not any(tracker in key for tracker in ['utm_', 'fbclid', 'gclid', '_ga']):
                        params.append(param)
                cleaned = cleaned._replace(query='&'.join(params))
            
            return cleaned.geturl()
        except Exception:
            return url

    def download_with_retry_balanced(self, url, retry_count=0):
        """Download with balanced retry logic"""
        if retry_count >= self.max_retries:
            self.failed_urls.add(url)
            return None
        
        try:
            # Small random delay
            time.sleep(random.uniform(0.5, 1.5))
            
            # Rotate user agent occasionally
            if random.random() < 0.2:
                self.update_session_headers()
            
            response = self.session.get(url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"    🚫 403 Forbidden: {url}")
                time.sleep(5)
                return self.download_with_retry_balanced(url, retry_count + 1)
            elif response.status_code == 404:
                print(f"    ❓ 404 Not Found: {url}")
                self.failed_urls.add(url)
                return None
            elif response.status_code == 429:
                print(f"    🐢 429 Rate Limited - waiting 10s: {url}")
                time.sleep(10)
                return self.download_with_retry_balanced(url, retry_count + 1)
            else:
                print(f"    ⚠️ HTTP {response.status_code} for {url}")
                time.sleep(3)
                return self.download_with_retry_balanced(url, retry_count + 1)
                
        except requests.exceptions.Timeout:
            print(f"    ⏰ Timeout for {url}")
            time.sleep(5)
            return self.download_with_retry_balanced(url, retry_count + 1)
        except Exception as e:
            print(f"    ❌ Error: {e}")
            time.sleep(3)
            return self.download_with_retry_balanced(url, retry_count + 1)

    def crawl_website_balanced(self, start_url, downloaded_content):
        """Balanced crawling - gets content without being too aggressive"""
        print("🕷️ Starting BALANCED website crawl...")
        
        self.pages_to_crawl.append(start_url)
        self.visited_urls.add(start_url)
        
        crawled_pages = 0
        consecutive_failures = 0
        
        while self.pages_to_crawl and crawled_pages < self.max_pages:
            if consecutive_failures >= 8:
                print("    🚨 Too many failures, stopping crawl")
                break
                
            current_url = self.pages_to_crawl.popleft()
            
            print(f"📄 [{crawled_pages+1}/{self.max_pages}] {os.path.basename(current_url) or current_url[:80]}")
            
            # Download the page
            page_data = self.download_page_balanced(current_url)
            if page_data:
                downloaded_content['pages'][current_url] = page_data
                crawled_pages += 1
                consecutive_failures = 0
                
                # Extract links for further crawling
                new_links = self.extract_all_links_balanced(page_data['content'], current_url)
                for link in new_links:
                    if link not in self.visited_urls and link not in self.failed_urls:
                        self.visited_urls.add(link)
                        self.pages_to_crawl.append(link)
                
                # Download ALL important assets for this page
                self.download_all_assets_comprehensive(page_data['content'], current_url, downloaded_content)
                
                # Reasonable delay
                time.sleep(random.uniform(1, 2))
            else:
                consecutive_failures += 1
                print(f"    ❌ Failed (#{consecutive_failures})")
        
        print(f"✅ Crawl complete: {crawled_pages} pages, {len(self.failed_urls)} failed")

    def download_page_balanced(self, url):
        """Download a single page"""
        response = self.download_with_retry_balanced(url)
        if response and response.status_code == 200:
            return {
                'url': response.url,
                'content': response.text,
                'content_type': response.headers.get('content-type', 'text/html'),
                'status_code': 200,
                'downloaded_with': 'session'
            }
        return None

    def download_all_assets_comprehensive(self, html, base_url, downloaded_content):
        """Download ALL assets - comprehensive approach"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find ALL resource URLs
        all_resource_urls = set()
        base_domain = urlparse(base_url).netloc
        
        # CSS files - get ALL
        for link in soup.find_all('link', href=True):
            href = link.get('href')
            if href and not href.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, href)
                all_resource_urls.add(full_url)
        
        # JavaScript files - get ALL  
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                all_resource_urls.add(full_url)
        
        # Images - get ALL
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                all_resource_urls.add(full_url)
        
        # Meta tags (icons, etc.)
        for meta in soup.find_all('meta', content=True):
            if meta.get('property') in ['og:image', 'og:audio', 'og:video']:
                full_url = urljoin(base_url, meta['content'])
                all_resource_urls.add(full_url)
        
        # Source tags (videos, pictures)
        for source in soup.find_all('source', src=True):
            full_url = urljoin(base_url, source['src'])
            all_resource_urls.add(full_url)
        
        # CSS url() references
        for tag in soup.find_all(style=True):
            urls = re.findall(r'url\([\'"]?([^)"\']+)[\'"]?\)', tag['style'])
            for url in urls:
                if not url.startswith(('data:', 'blob:')):
                    full_url = urljoin(base_url, url)
                    all_resource_urls.add(full_url)
        
        # Style tag content
        for style in soup.find_all('style'):
            if style.string:
                urls = re.findall(r'url\([\'"]?([^)"\']+)[\'"]?\)', style.string)
                for url in urls:
                    if not url.startswith(('data:', 'blob:')):
                        full_url = urljoin(base_url, url)
                        all_resource_urls.add(full_url)
        
        # Script tag content (dynamic imports, etc.)
        for script in soup.find_all('script'):
            if script.string:
                # Look for common asset patterns in JS
                patterns = [
                    r'["\'](https?://[^"\']+\.(css|js|png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf|eot))["\']',
                    r'["\'](/[^"\']+\.(css|js|png|jpg|jpeg|gif|svg|ico|webp|woff|woff2|ttf|eot))["\']',
                    r'url\(["\']?(https?://[^"\'\)]+)["\']?\)',
                    r'url\(["\']?(/[^"\'\)]+)["\']?\)'
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, script.string)
                    for match in matches:
                        url = match[0] if isinstance(match, tuple) else match
                        full_url = urljoin(base_url, url)
                        all_resource_urls.add(full_url)
        
        print(f"    📦 Found {len(all_resource_urls)} total assets")
        
        # Download assets with priority
        successful = 0
        critical_assets = 0
        other_assets = 0
        
        for i, resource_url in enumerate(all_resource_urls):
            if resource_url in downloaded_content['assets']:
                continue
            
            # Skip if we've already failed this URL
            if resource_url in self.failed_urls:
                continue
            
            filename = os.path.basename(resource_url) or resource_url[:60]
            
            # Priority download for critical assets
            is_critical = any(resource_url.endswith(ext) for ext in 
                            ['.css', '.js', '.woff', '.woff2', '.ttf', '.eot'])
            
            if is_critical:
                critical_assets += 1
                print(f"    🎯 [{i+1}/{len(all_resource_urls)}] CRITICAL: {filename}")
            else:
                other_assets += 1
                print(f"    📁 [{i+1}/{len(all_resource_urls)}] Asset: {filename}")
            
            asset_data = self.download_asset_balanced(resource_url)
            if asset_data:
                downloaded_content['assets'][resource_url] = asset_data
                successful += 1
            else:
                print(f"      ❌ Failed: {filename}")
                self.failed_urls.add(resource_url)
            
            # Small delay between asset downloads
            time.sleep(0.3)
        
        print(f"    ✅ Downloaded: {successful}/{len(all_resource_urls)} assets ({critical_assets} critical)")

    def download_asset_balanced(self, url):
        """Download asset with good error handling"""
        try:
            response = self.session.get(url, timeout=10, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # Handle binary content
                if any(ct in content_type for ct in ['image', 'font', 'binary', 'octet-stream']):
                    content = response.content
                    # Skip very large files (>10MB)
                    if len(content) > 10 * 1024 * 1024:
                        print(f"      ⚠️ Skipping large file: {len(content)//1024}KB")
                        return None
                    encoded = base64.b64encode(content).decode('utf-8')
                    encoding = 'base64'
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
                    'filename': os.path.basename(urlparse(url).path) or 'resource'
                }
            else:
                return None
                
        except Exception as e:
            return None

    def download_website(self, url):
        """Main download method"""
        print(f"⬇️ Target: {url}")
        
        # Manual Cloudflare solve if needed
        if not self.manual_cloudflare_solve(url):
            print("❌ Failed to setup Chrome session")
            return None
        
        # Download with balanced approach
        result = self.download_with_session_balanced(url)
        
        # Cleanup
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        return result

    def download_with_session_balanced(self, url):
        """Download using balanced approach"""
        print("⬇️ Downloading with BALANCED approach...")
        
        downloaded_content = {
            'main_url': url,
            'pages': {},
            'assets': {},
            'timestamp': time.time(),
        }
        
        # Reset state
        self.visited_urls.clear()
        self.pages_to_crawl.clear()
        self.failed_urls.clear()
        
        # Start balanced crawling
        self.crawl_website_balanced(url, downloaded_content)
        
        print(f"    📊 Total pages: {len(downloaded_content['pages'])}")
        print(f"    📊 Total assets: {len(downloaded_content['assets'])}")
        print(f"    📊 Failed URLs: {len(self.failed_urls)}")
        
        # Save file
        domain = urlparse(url).netloc.replace(':', '_')
        filename = f"{domain}_{int(time.time())}.page"
        filepath = os.path.join(self.output_dir, filename)
        
        if self.save_page_file(filepath, downloaded_content):
            print(f"💾 Saved: {filename}")
            return filepath
        else:
            print(f"❌ Failed to save: {filename}")
            return None

    def save_page_file(self, filepath, content):
        """Save as .page file"""
        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Metadata
                metadata = {
                    'main_url': content['main_url'],
                    'timestamp': content['timestamp'],
                    'pages': len(content['pages']),
                    'assets': len(content['assets']),
                    'total_size': sum(len(asset['content']) for asset in content['assets'].values())
                }
                zipf.writestr('metadata.json', json.dumps(metadata, indent=2))
                
                # Pages
                for url, data in content['pages'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:10]
                    zipf.writestr(f"pages/{hash_val}.json", json.dumps(data, indent=2))
                
                # Assets
                for url, data in content['assets'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:10]
                    zipf.writestr(f"assets/{hash_val}.json", json.dumps(data, indent=2))
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            print(f"    💾 File size: {file_size:.2f} MB")
            return os.path.exists(filepath)
        except Exception as e:
            print(f"    ❌ Save error: {e}")
            return False

    def manual_cloudflare_solve(self, url):
        """Manual Cloudflare solving"""
        print("🚨 CLOUDFLARE SOLVER")
        print("="*50)
        
        if not self.setup_chrome_balanced():
            return False
            
        try:
            print(f"🌐 Opening: {url}")
            self.driver.get(url)
            
            print("\n" + "="*50)
            print("💡 CHROME IS OPEN!")
            print("Please:")
            print("1. Solve any security challenges")
            print("2. Wait for the page to fully load")
            print("3. Return here and press Enter")
            print("="*50)
            
            input("⏳ Press Enter when the page is fully loaded...")
            
            current_url = self.driver.current_url
            print(f"🔗 Current URL: {current_url}")
            print(f"📄 Page title: {self.driver.title}")
            
            # Capture cookies
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            print(f"✅ Captured {len(cookies)} cookies")
            return True
            
        except Exception as e:
            print(f"❌ Error during manual solve: {e}")
            return False

    def download_from_list(self, url_list):
        """Download multiple sites"""
        downloaded_files = []
        
        print(f"🎯 Downloading {len(url_list)} sites...")
        print(f"📁 Output: {self.output_dir}")
        
        for i, url in enumerate(url_list, 1):
            url = url.strip()
            if not url:
                continue
                
            print(f"\n{'='*50}")
            print(f"#{i}: {url}")
            print("="*50)
            
            try:
                filepath = self.download_website(url)
                if filepath:
                    downloaded_files.append(filepath)
                    print(f"✅ Success! Downloaded {len(downloaded_files)} sites")
                else:
                    print(f"❌ Failed")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print(f"\n{'='*50}")
        print(f"📊 Complete: {len(downloaded_files)}/{len(url_list)} sites")
        print(f"💾 Location: {self.output_dir}")
        
        return downloaded_files

if __name__ == "__main__":
    print("="*50)
    print("🚀 BALANCED WEBSITE DOWNLOADER")
    print("📥 Gets ALL important assets without being blocked")
    print("🌐 Comprehensive asset discovery")
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
    
    downloader = BalancedWebsiteDownloader()
    files = downloader.download_from_list(sites)
    
    if files:
        print(f"\n🎉 Success! Downloaded sites with COMPLETE assets")
        print("💡 Now run the browser.py to view your downloaded sites!")
    else:
        print(f"\n❌ No sites downloaded")
