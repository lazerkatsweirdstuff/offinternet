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

class SmartWebsiteDownloader:
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
        self.max_pages = 500  # Reduced for stability
        self.crawl_delay = random.uniform(2, 5)  # Random delay between requests
        self.max_retries = 3
        self.respect_robots = True
        
        # Domain-specific settings
        self.domain_limits = {}
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ Created directory: {self.output_dir}")

    def update_session_headers(self):
        """Update session headers with random user agent"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)

    def setup_chrome_stealth(self):
        """Setup Chrome with stealth options"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--incognito")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1400,1000")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            
            # Additional stealth options
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--allow-running-insecure-content")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            
            print("🔄 Starting Chrome in stealth mode...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Additional stealth scripts
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.ua.random})
            
            self.driver.implicitly_wait(10)
            print("✅ Chrome started successfully in stealth mode")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            return False

    def is_valid_url(self, url, base_domain):
        """Check if URL is valid for crawling"""
        try:
            parsed = urlparse(url)
            base_parsed = urlparse(base_domain)
            
            # Must have http or https
            if not url.startswith(('http://', 'https://')):
                return False
            
            # Should be same domain
            if parsed.netloc != base_parsed.netloc:
                return False
            
            # Avoid common non-content URLs
            excluded_extensions = ['.pdf', '.zip', '.exe', '.dmg', '.mp4', '.mp3', '.avi', '.mov']
            if any(parsed.path.lower().endswith(ext) for ext in excluded_extensions):
                return False
            
            # Avoid URLs with certain patterns
            excluded_patterns = ['/cdn-cgi/', '/api/', '/ajax/', '/admin/', '/login/', '/signin/']
            if any(pattern in url.lower() for pattern in excluded_patterns):
                return False
            
            return True
            
        except Exception:
            return False

    def extract_quality_links(self, html, base_url):
        """Extract high-quality links likely to be actual content pages"""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        base_domain = urlparse(base_url).netloc
        
        # Get all anchor tags with href
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                full_url = urljoin(base_url, href)
                
                # Clean URL - remove fragments and common tracking parameters
                clean_url = self.clean_url(full_url)
                
                if self.is_valid_url(clean_url, base_url):
                    # Prioritize links that look like content
                    text = link.get_text().strip().lower()
                    parent_classes = ' '.join(link.parent.get('class', [])).lower() if link.parent else ''
                    
                    # Skip navigation, footer, sidebar links often
                    skip_indicators = ['nav', 'menu', 'footer', 'sidebar', 'breadcrumb', 'pagination']
                    if any(indicator in parent_classes for indicator in skip_indicators):
                        continue
                    
                    # Skip very short link text (often icons)
                    if len(text) < 2:
                        continue
                        
                    links.add(clean_url)
        
        return links

    def clean_url(self, url):
        """Clean URL by removing fragments and common tracking parameters"""
        try:
            parsed = urlparse(url)
            
            # Remove fragment
            cleaned = parsed._replace(fragment='')
            
            # Remove common tracking parameters
            query_params = []
            if parsed.query:
                for param in parsed.query.split('&'):
                    key = param.split('=')[0].lower()
                    # Keep important parameters, remove tracking ones
                    if key in ['id', 'page', 'view', 'article', 'product']:
                        query_params.append(param)
                    elif not any(track in key for track in ['utm_', 'source', 'medium', 'campaign', 'fbclid', 'gclid']):
                        query_params.append(param)
            
            cleaned = cleaned._replace(query='&'.join(query_params))
            return cleaned.geturl()
            
        except Exception:
            return url

    def download_with_retry(self, url, retry_count=0):
        """Download with retry logic and smart error handling"""
        if retry_count >= self.max_retries:
            self.failed_urls.add(url)
            return None
        
        try:
            # Random delay between requests
            time.sleep(random.uniform(1, 3))
            
            # Rotate user agent occasionally
            if random.random() < 0.3:  # 30% chance to rotate UA
                self.update_session_headers()
            
            response = self.session.get(url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"    🚫 403 Forbidden: {url}")
                # Wait longer for 403 errors
                time.sleep(10)
                return self.download_with_retry(url, retry_count + 1)
            elif response.status_code == 404:
                print(f"    ❓ 404 Not Found: {url}")
                self.failed_urls.add(url)
                return None
            elif response.status_code == 429:  # Too Many Requests
                print(f"    🐢 429 Rate Limited: {url} - Waiting 30 seconds...")
                time.sleep(30)
                return self.download_with_retry(url, retry_count + 1)
            else:
                print(f"    ⚠️ HTTP {response.status_code} for {url}")
                time.sleep(5)
                return self.download_with_retry(url, retry_count + 1)
                
        except requests.exceptions.Timeout:
            print(f"    ⏰ Timeout for {url}")
            time.sleep(10)
            return self.download_with_retry(url, retry_count + 1)
        except requests.exceptions.ConnectionError:
            print(f"    🔌 Connection error for {url}")
            time.sleep(15)
            return self.download_with_retry(url, retry_count + 1)
        except Exception as e:
            print(f"    ❌ Error downloading {url}: {e}")
            time.sleep(5)
            return self.download_with_retry(url, retry_count + 1)

    def crawl_website_smart(self, start_url, downloaded_content):
        """Smarter website crawling with error handling"""
        print("🕷️ Starting SMART website crawl...")
        
        self.pages_to_crawl.append(start_url)
        self.visited_urls.add(start_url)
        
        crawled_pages = 0
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while self.pages_to_crawl and crawled_pages < self.max_pages:
            if consecutive_failures >= max_consecutive_failures:
                print("    🚨 Too many consecutive failures, stopping crawl")
                break
                
            current_url = self.pages_to_crawl.popleft()
            
            print(f"📄 Crawling [{crawled_pages+1}/{self.max_pages}]: {current_url}")
            
            # Download the page with retry logic
            page_data = self.download_page_smart(current_url)
            if page_data:
                downloaded_content['pages'][current_url] = page_data
                crawled_pages += 1
                consecutive_failures = 0
                
                # Extract QUALITY links from this page
                new_links = self.extract_quality_links(page_data['content'], current_url)
                for link in new_links:
                    if link not in self.visited_urls and link not in self.failed_urls:
                        self.visited_urls.add(link)
                        self.pages_to_crawl.append(link)
                        print(f"    🔗 Found quality page: {os.path.basename(link) or link[:60]}")
                
                # Download resources for this page
                self.download_all_resources_smart(page_data['content'], current_url, downloaded_content)
                
                # Random delay between pages
                time.sleep(random.uniform(2, 4))
            else:
                consecutive_failures += 1
                print(f"    ❌ Failed to download (failure #{consecutive_failures}): {current_url}")
        
        print(f"✅ Crawl complete: {crawled_pages} pages downloaded, {len(self.failed_urls)} failed")

    def download_page_smart(self, url):
        """Download a single page with smart error handling"""
        response = self.download_with_retry(url)
        if response and response.status_code == 200:
            return {
                'url': response.url,
                'content': response.text,
                'content_type': response.headers.get('content-type', 'text/html'),
                'status_code': 200,
                'downloaded_with': 'session'
            }
        return None

    def download_all_resources_smart(self, html, base_url, downloaded_content):
        """Smart resource downloading with filtering"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find resources but filter out likely CDN/blocked URLs
        resource_urls = set()
        base_domain = urlparse(base_url).netloc
        
        # CSS files - only from same domain
        for link in soup.find_all('link', href=True):
            href = link.get('href')
            if href and not href.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, href)
                if base_domain in full_url:  # Only same domain CSS
                    resource_urls.add(full_url)
        
        # JavaScript files - only from same domain
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                if base_domain in full_url:  # Only same domain JS
                    resource_urls.add(full_url)
        
        # Images - be more permissive
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                resource_urls.add(full_url)
        
        print(f"    📦 Found {len(resource_urls)} resources to download")
        
        # Download resources with concurrency control
        successful = 0
        for i, resource_url in enumerate(resource_urls):
            if resource_url in downloaded_content['assets']:
                continue
                
            name = os.path.basename(resource_url) or resource_url[:50]
            print(f"    [{i+1}/{len(resource_urls)}] Downloading: {name}")
            
            asset_data = self.download_resource_smart(resource_url)
            if asset_data:
                downloaded_content['assets'][resource_url] = asset_data
                successful += 1
            else:
                print(f"      ❌ Failed to download: {name}")
            
            # Small delay between resource downloads
            time.sleep(0.5)
        
        print(f"    ✅ Successfully downloaded: {successful}/{len(resource_urls)} assets")

    def download_resource_smart(self, url):
        """Download resource with smart error handling"""
        try:
            response = self.session.get(url, timeout=10, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # Skip very large files
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB limit
                    print(f"      ⚠️ Skipping large file: {url}")
                    return None
                
                # Handle binary content
                if any(ct in content_type for ct in ['image', 'font', 'binary', 'video', 'audio', 'octet-stream']):
                    content = response.content
                    encoded = base64.b64encode(content).decode('utf-8')
                    encoding = 'base64'
                else:
                    # Text content
                    encoded = response.text
                    encoding = 'text'
                
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
        """Main download method with better error handling"""
        print(f"⬇️ Target: {url}")
        
        # Manual Cloudflare solve
        if not self.manual_cloudflare_solve(url):
            print("❌ Failed to setup Chrome session")
            return None
        
        # Download with session AND SMART CRAWLING
        result = self.download_with_session_smart(url)
        
        # Cleanup
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        return result

    def download_with_session_smart(self, url):
        """Download using captured session with smart crawling"""
        print("⬇️ Downloading with SMART session and crawling...")
        
        downloaded_content = {
            'main_url': url,
            'pages': {},
            'assets': {},
            'timestamp': time.time(),
        }
        
        # Reset crawling state
        self.visited_urls.clear()
        self.pages_to_crawl.clear()
        self.failed_urls.clear()
        
        # Start SMART crawling from the main URL
        self.crawl_website_smart(url, downloaded_content)
        
        print(f"    📊 Total pages downloaded: {len(downloaded_content['pages'])}")
        print(f"    📊 Total assets downloaded: {len(downloaded_content['assets'])}")
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
                    'failed_urls': list(self.failed_urls),
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
        """Manual Cloudflare solving - same as before"""
        print("🚨 CLOUDFLARE SOLVER - STEALTH MODE")
        print("="*50)
        
        if not self.setup_chrome_stealth():
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
    print("🚀 SMART WEBSITE DOWNLOADER - STEALTH MODE")
    print("📥 Downloads quality pages with error handling")
    print("🌐 Avoids blocks and handles failures gracefully")
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
    
    downloader = SmartWebsiteDownloader()
    files = downloader.download_from_list(sites)
    
    if files:
        print(f"\n🎉 Success! Downloaded sites with quality pages and assets")
        print("💡 Now run the browser.py to view your downloaded sites!")
    else:
        print(f"\n❌ No sites downloaded")
