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
import brotli
from PIL import Image
import io

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
        self.max_pages = 10  # Increased limit
        self.crawl_delay = random.uniform(1, 2)
        self.max_retries = 3  # More retries
        
        # Asset type priorities
        self.critical_assets = ['.css', '.js']
        self.important_assets = ['.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2', '.ttf']
        self.other_assets = ['.gif', '.webp', '.mp4', '.webm', '.json', '.xml']
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ Created directory: {self.output_dir}")

    def update_session_headers(self):
        """Update session headers with random user agent"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(headers)

    def setup_chrome_complete(self):
        """Setup Chrome for complete asset capture with enhanced capabilities"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--incognito")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            
            # Enable performance logging for network requests
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            print("🔄 Starting Chrome for complete asset capture...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(15)
            print("✅ Chrome started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            return False

    def manual_cloudflare_solve(self, url):
        """Enhanced manual Cloudflare solving"""
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
            print("3. Scroll down to trigger lazy loading")
            print("4. Return here and press Enter")
            print("="*50)
            
            input("⏳ Press Enter when the page is COMPLETELY loaded...")
            
            current_url = self.driver.current_url
            print(f"🔗 Current URL: {current_url}")
            print(f"📄 Page title: {self.driver.title}")
            
            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            
            # Capture ALL cookies
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            print(f"✅ Captured {len(cookies)} cookies")
            
            # Also capture local storage
            try:
                local_storage = self.driver.execute_script("return window.localStorage;")
                print(f"✅ Captured {len(local_storage)} local storage items")
            except:
                print("⚠️ Could not capture local storage")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during manual solve: {e}")
            return False

    def extract_all_links_complete(self, html, base_url):
        """Extract ALL links for comprehensive crawling with enhanced discovery"""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        base_domain = urlparse(base_url).netloc
        
        # Get all anchor tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                full_url = urljoin(base_url, href)
                clean_url = self.clean_url(full_url)
                
                if self.is_valid_internal_url(clean_url, base_domain):
                    links.add(clean_url)
        
        # Also extract from meta tags, scripts, etc.
        for meta in soup.find_all('meta', content=True):
            content = meta.get('content', '')
            if 'url=' in content.lower():
                url_match = re.search(r'url=([^"\'&]+)', content)
                if url_match:
                    full_url = urljoin(base_url, url_match.group(1))
                    clean_url = self.clean_url(full_url)
                    if self.is_valid_internal_url(clean_url, base_domain):
                        links.add(clean_url)
        
        return links

    def is_valid_internal_url(self, url, base_domain):
        """Check if URL is valid and internal"""
        if not url.startswith(('http://', 'https://')):
            return False
            
        if base_domain not in url:
            return False
            
        if self.is_likely_junk(url):
            return False
            
        return True

    def is_likely_junk(self, url):
        """Enhanced junk URL filtering"""
        junk_patterns = [
            '/cdn-cgi/', '/wp-admin/', '/wp-json/', '/administrator/', 
            '.pdf', '.zip', '.exe', '.dmg', '.tar.gz',
            '/api/', '/ajax/', '/graphql', '/websocket', '/.well-known/',
            'logout', 'signout', 'delete', 'remove'
        ]
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in junk_patterns)

    def clean_url(self, url):
        """Clean URL but keep important parameters"""
        try:
            parsed = urlparse(url)
            # Remove fragment only, keep query parameters
            cleaned = parsed._replace(fragment='')
            return cleaned.geturl()
        except Exception:
            return url

    def download_with_retry_complete(self, url, retry_count=0, method='get', data=None):
        """Enhanced download with complete retry logic and multiple methods"""
        if retry_count >= self.max_retries:
            self.failed_urls.add(url)
            return None
        
        try:
            time.sleep(random.uniform(0.5, 1.5))
            
            if random.random() < 0.3:
                self.update_session_headers()
            
            if method == 'post' and data:
                response = self.session.post(url, data=data, timeout=20, allow_redirects=True)
            else:
                response = self.session.get(url, timeout=20, allow_redirects=True)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"    🚫 403 Forbidden: {url}")
                # Try with different approach
                return self.try_alternative_download(url, retry_count)
            elif response.status_code == 429:
                wait_time = 15 + (retry_count * 10)
                print(f"    🐢 429 Rate Limited - waiting {wait_time}s: {url}")
                time.sleep(wait_time)
                return self.download_with_retry_complete(url, retry_count + 1)
            elif response.status_code in [404, 410]:
                print(f"    ❌ {response.status_code} Not Found: {url}")
                return None
            else:
                print(f"    ⚠️ HTTP {response.status_code} for {url}")
                time.sleep(5)
                return self.download_with_retry_complete(url, retry_count + 1)
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            time.sleep(3)
            return self.download_with_retry_complete(url, retry_count + 1)

    def try_alternative_download(self, url, retry_count):
        """Try alternative download methods"""
        print(f"    🔄 Trying alternative download for: {url}")
        
        # Method 1: Try with Selenium if available
        if self.driver and url == self.driver.current_url:
            try:
                # Use JavaScript to fetch the resource
                js_fetch = f"""
                fetch('{url}').then(r => r.text()).then(t => window.fetchedContent = t);
                """
                self.driver.execute_script(js_fetch)
                time.sleep(2)
                content = self.driver.execute_script("return window.fetchedContent || ''")
                if content:
                    # Create a mock response
                    class MockResponse:
                        def __init__(self, content):
                            self.content = content.encode('utf-8')
                            self.text = content
                            self.status_code = 200
                            self.headers = {'content-type': 'text/html'}
                    return MockResponse(content)
            except:
                pass
        
        # Method 2: Try with different headers
        original_headers = self.session.headers.copy()
        try:
            self.session.headers.update({
                'Accept': '*/*',
                'Referer': self.driver.current_url if self.driver else url,
                'Sec-Fetch-Dest': 'document' if url.endswith(('.html', '.htm')) else 'style' if url.endswith('.css') else 'script' if url.endswith('.js') else 'image'
            })
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                return response
        except:
            pass
        finally:
            self.session.headers.update(original_headers)
        
        return self.download_with_retry_complete(url, retry_count + 1)

    def crawl_website_complete(self, start_url, downloaded_content):
        """Complete website crawling with enhanced asset capture"""
        print("🕷️ Starting COMPREHENSIVE website crawl...")
        
        self.pages_to_crawl.append(start_url)
        self.visited_urls.add(start_url)
        
        crawled_pages = 0
        consecutive_failures = 0
        
        while self.pages_to_crawl and crawled_pages < self.max_pages:
            if consecutive_failures >= 3:
                print("    🚨 Too many failures, trying recovery...")
                if not self.recover_from_failures():
                    break
                consecutive_failures = 0
                
            current_url = self.pages_to_crawl.popleft()
            
            print(f"📄 [{crawled_pages+1}/{self.max_pages}] {self.get_url_display_name(current_url)}")
            
            # Download the page with multiple approaches
            page_data = self.download_page_enhanced(current_url)
            if page_data:
                downloaded_content['pages'][current_url] = page_data
                crawled_pages += 1
                consecutive_failures = 0
                
                # Extract links for further crawling
                new_links = self.extract_all_links_complete(page_data['content'], current_url)
                for link in new_links:
                    if link not in self.visited_urls and link not in self.failed_urls:
                        self.visited_urls.add(link)
                        self.pages_to_crawl.append(link)
                        print(f"      🔗 Found new page: {self.get_url_display_name(link)}")
                
                # Download ALL assets including CSS from this page
                self.download_all_assets_enhanced(page_data['content'], current_url, downloaded_content)
                
                time.sleep(random.uniform(1, 2))
            else:
                consecutive_failures += 1
                print(f"    ❌ Failed (#{consecutive_failures})")
        
        print(f"✅ Crawl complete: {crawled_pages} pages")
        
        # Final asset discovery pass
        self.final_asset_discovery(downloaded_content)

    def get_url_display_name(self, url):
        """Get a clean display name for URL"""
        parsed = urlparse(url)
        path = parsed.path
        if not path or path == '/':
            return f"{parsed.netloc}/"
        return os.path.basename(path) or path[:80]

    def recover_from_failures(self):
        """Attempt to recover from consecutive failures"""
        print("    🔄 Attempting recovery...")
        time.sleep(5)
        self.update_session_headers()
        return True

    def download_page_enhanced(self, url):
        """Enhanced page download with multiple fallbacks"""
        # Try direct download first
        response = self.download_with_retry_complete(url)
        if response and response.status_code == 200:
            return {
                'url': response.url,
                'content': response.text,
                'content_type': response.headers.get('content-type', 'text/html'),
                'status_code': 200,
                'downloaded_with': 'session'
            }
        
        # Try Selenium as fallback
        if self.driver:
            try:
                print(f"    🔄 Falling back to Selenium for: {url}")
                self.driver.get(url)
                time.sleep(3)
                return {
                    'url': url,
                    'content': self.driver.page_source,
                    'content_type': 'text/html',
                    'status_code': 200,
                    'downloaded_with': 'selenium'
                }
            except Exception as e:
                print(f"    ❌ Selenium fallback failed: {e}")
        
        return None

    def download_asset_complete(self, url):
        """Enhanced asset download with better error handling and content processing"""
        try:
            # Special handling for different file types
            if any(url.endswith(ext) for ext in self.critical_assets):
                # Critical assets - be more persistent
                response = self.download_with_retry_complete(url)
            else:
                response = self.session.get(url, timeout=15, stream=True)
                
            if response and response.status_code == 200:
                return self.process_asset_response(response, url)
            else:
                return None
                
        except Exception as e:
            print(f"      ❌ Error downloading asset {url}: {e}")
            return None

    def process_asset_response(self, response, url):
        """Process asset response with enhanced content handling"""
        content_type = response.headers.get('content-type', '').lower()
        content_encoding = response.headers.get('content-encoding', '').lower()
        
        # Handle content encoding
        content = response.content
        if content_encoding == 'gzip':
            try:
                content = gzip.decompress(content)
            except:
                pass
        elif content_encoding == 'br':
            try:
                content = brotli.decompress(content)
            except:
                pass
        
        # Skip very large files (>10MB)
        if len(content) > 10 * 1024 * 1024:
            print(f"      ⚠️ Skipping large file: {len(content)//1024}KB - {url}")
            return None
        
        # Determine encoding and processing
        is_binary = any(ct in content_type for ct in ['image', 'font', 'binary', 'octet-stream']) or url.endswith(('.css', '.js'))
        
        if is_binary:
            encoded = base64.b64encode(content).decode('utf-8')
            encoding = 'base64'
            
            # Additional processing for images
            if 'image' in content_type:
                try:
                    # Try to optimize image info
                    img = Image.open(io.BytesIO(content))
                    asset_info = {
                        'format': img.format,
                        'size': img.size,
                        'mode': img.mode
                    }
                except:
                    asset_info = {}
            else:
                asset_info = {}
                
            return {
                'url': url,
                'content': encoded,
                'content_type': content_type,
                'encoding': encoding,
                'size': len(encoded),
                'filename': os.path.basename(urlparse(url).path) or 'resource',
                'asset_info': asset_info,
                'is_critical': url.endswith(tuple(self.critical_assets))
            }
        else:
            # Text content
            try:
                encoded = content.decode('utf-8')
                encoding = 'text'
            except UnicodeDecodeError:
                try:
                    encoded = content.decode('latin-1')
                    encoding = 'text'
                except:
                    encoded = base64.b64encode(content).decode('utf-8')
                    encoding = 'base64'
            
            return {
                'url': url,
                'content': encoded,
                'content_type': content_type,
                'encoding': encoding,
                'size': len(encoded),
                'filename': os.path.basename(urlparse(url).path) or 'resource',
                'is_critical': url.endswith(tuple(self.critical_assets))
            }

    def extract_assets_from_html(self, html, base_url):
        """Extract ALL possible assets from HTML with enhanced discovery"""
        soup = BeautifulSoup(html, 'html.parser')
        assets = set()
        
        # Standard tags
        tags_attrs = [
            ('link', 'href'),
            ('script', 'src'),
            ('img', 'src'),
            ('source', 'src'),
            ('source', 'srcset'),
            ('video', 'poster'),
            ('audio', 'src'),
            ('iframe', 'src'),
            ('embed', 'src'),
            ('object', 'data'),
            ('meta', 'content'),  # For og:image etc.
        ]
        
        for tag, attr in tags_attrs:
            for element in soup.find_all(tag, **{attr: True}):
                attr_value = element.get(attr)
                if attr_value:
                    # Handle srcset (multiple images)
                    if attr == 'srcset':
                        for src_entry in attr_value.split(','):
                            src_url = src_entry.strip().split(' ')[0]
                            if src_url:
                                full_url = urljoin(base_url, src_url)
                                assets.add(full_url)
                    else:
                        full_url = urljoin(base_url, attr_value)
                        assets.add(full_url)
        
        # Extract from inline styles and JavaScript
        for style in soup.find_all('style'):
            if style.string:
                assets.update(self.extract_urls_from_css(style.string, base_url))
        
        for script in soup.find_all('script'):
            if script.string:
                assets.update(self.extract_urls_from_js(script.string, base_url))
        
        # Extract from tag attributes that might contain URLs
        for tag in soup.find_all(True):
            for attr in ['style', 'data-src', 'data-background', 'data-url']:
                if tag.get(attr):
                    urls = re.findall(r'url\([\'"]?([^)"\']+)[\'"]?\)', tag.get(attr))
                    for url in urls:
                        full_url = urljoin(base_url, url)
                        assets.add(full_url)
        
        return assets

    def extract_urls_from_css(self, css_text, base_url):
        """Extract URLs from CSS text with enhanced patterns"""
        urls = set()
        
        patterns = [
            r'url\([\'"]?([^)"\']+)[\'"]?\)',
            r'@import\s+[\'"]([^\'"]+)[\'"]',
            r'src:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'@font-face\s*\{[^}]*src:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'background-image:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'content:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'list-style-image:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'cursor:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, css_text, re.IGNORECASE)
            for match in matches:
                url = match.strip()
                if url and not url.startswith(('data:', 'blob:')):
                    full_url = urljoin(base_url, url)
                    urls.add(full_url)
        
        return urls

    def extract_urls_from_js(self, js_text, base_url):
        """Extract URLs from JavaScript text"""
        urls = set()
        
        # Common patterns for URLs in JavaScript
        patterns = [
            r'[\'\"](https?://[^\'\"]+)[\'\"]',
            r'[\'\"](/[^\'\"]+)[\'\"]',
            r'url\([\'"]?([^)"\']+)[\'"]?\)',
            r'=\s*[\'\"]([^\'\"]+\.(css|js|png|jpg|jpeg|svg|ico))[\'\"]',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, js_text)
            for match in matches:
                url = match[0] if isinstance(match, tuple) else match
                if url and not url.startswith(('data:', 'blob:', 'javascript:')):
                    full_url = urljoin(base_url, url)
                    urls.add(full_url)
        
        return urls

    def download_all_assets_enhanced(self, html, base_url, downloaded_content):
        """Enhanced asset download with prioritization"""
        assets = self.extract_assets_from_html(html, base_url)
        
        # Also get assets from Selenium if available
        if self.driver and base_url == self.driver.current_url:
            selenium_assets = self.get_selenium_network_requests()
            assets.update(selenium_assets)
        
        print(f"    📦 Found {len(assets)} total assets")
        
        # Prioritize assets
        critical_assets = [a for a in assets if any(a.endswith(ext) for ext in self.critical_assets)]
        important_assets = [a for a in assets if any(a.endswith(ext) for ext in self.important_assets)]
        other_assets = [a for a in assets if any(a.endswith(ext) for ext in self.other_assets)]
        remaining_assets = assets - set(critical_assets) - set(important_assets) - set(other_assets)
        
        # Download in priority order
        successful = 0
        total_assets = len(assets)
        
        for i, asset_group in enumerate([critical_assets, important_assets, other_assets, remaining_assets]):
            group_name = ['CRITICAL', 'IMPORTANT', 'OTHER', 'REMAINING'][i]
            print(f"    🎯 Downloading {group_name} assets ({len(asset_group)} items)")
            
            for j, asset_url in enumerate(asset_group):
                if asset_url in downloaded_content['assets'] or asset_url in self.failed_urls:
                    continue
                
                filename = os.path.basename(asset_url) or asset_url[:60]
                print(f"      📁 [{successful+1}/{total_assets}] {group_name}: {filename}")
                
                asset_data = self.download_asset_complete(asset_url)
                if asset_data:
                    downloaded_content['assets'][asset_url] = asset_data
                    successful += 1
                    
                    # Process CSS files for nested assets
                    if asset_url.endswith('.css'):
                        self.download_css_assets(asset_data, asset_url, downloaded_content)
                else:
                    print(f"      ❌ Failed: {filename}")
                    self.failed_urls.add(asset_url)
                
                time.sleep(0.1)  # Small delay between downloads
        
        print(f"    ✅ Downloaded: {successful}/{total_assets} assets")

    def get_selenium_network_requests(self):
        """Get all network requests from Selenium performance logs"""
        assets = set()
        try:
            logs = self.driver.get_log('performance')
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    message_type = message.get('message', {}).get('method', '')
                    
                    if message_type == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        url = response.get('url', '')
                        if url and not url.startswith('data:'):
                            assets.add(url)
                except:
                    continue
        except Exception as e:
            print(f"      ⚠️ Selenium network log error: {e}")
        
        return assets

    def download_css_assets(self, css_asset, css_url, downloaded_content):
        """Download assets referenced in CSS files with enhanced processing"""
        try:
            css_content = css_asset['content']
            
            # Decode if base64 encoded
            if css_asset['encoding'] == 'base64':
                css_content = base64.b64decode(css_content)
                
                # Try multiple decoding methods
                css_text = None
                decoding_methods = [
                    ('utf-8', 'UTF-8'),
                    ('latin-1', 'Latin-1'),
                    ('cp1252', 'Windows-1252'),
                ]
                
                for encoding, name in decoding_methods:
                    try:
                        css_text = css_content.decode(encoding)
                        print(f"      🔍 CSS decoded as {name}")
                        break
                    except UnicodeDecodeError:
                        continue
                
                # If text decoding fails, try gzip
                if not css_text:
                    try:
                        if css_content[:2] == b'\x1f\x8b':
                            css_text = gzip.decompress(css_content).decode('utf-8')
                            print("      🔍 Decompressed gzipped CSS")
                    except:
                        pass
                
                # Final fallback - process as binary
                if not css_text:
                    css_text = self.process_binary_css(css_content)
            else:
                css_text = css_content
            
            if not css_text:
                print("      ⚠️ Could not extract text from CSS, skipping asset extraction")
                return
            
            # Extract and download referenced assets
            css_assets = self.extract_urls_from_css(css_text, css_url)
            print(f"      🔍 CSS references {len(css_assets)} assets")
            
            for asset_url in css_assets:
                if asset_url not in downloaded_content['assets'] and asset_url not in self.failed_urls:
                    print(f"      📥 CSS asset: {os.path.basename(asset_url) or asset_url[:50]}")
                    asset_data = self.download_asset_complete(asset_url)
                    if asset_data:
                        downloaded_content['assets'][asset_url] = asset_data
            
        except Exception as e:
            print(f"      ⚠️ CSS asset download error: {e}")

    def process_binary_css(self, css_content):
        """Enhanced binary CSS processing"""
        try:
            # Try to extract URLs directly from binary
            content_str = str(css_content)
            urls = re.findall(r'url\([^)]+\)', content_str)
            if urls:
                print(f"      🔍 Found {len(urls)} URLs in binary CSS")
                return content_str
            return None
        except Exception as e:
            print(f"      ⚠️ Binary CSS processing failed: {e}")
            return None

    def final_asset_discovery(self, downloaded_content):
        """Final pass to discover missing assets"""
        print("🔍 Performing final asset discovery...")
        
        # Check for common missing assets
        common_assets = [
            '/favicon.ico',
            '/apple-touch-icon.png',
            '/robots.txt',
            '/sitemap.xml',
            '/manifest.json'
        ]
        
        for page_url in downloaded_content['pages']:
            base_domain = urlparse(page_url).netloc
            for asset_path in common_assets:
                asset_url = f"https://{base_domain}{asset_path}"
                if asset_url not in downloaded_content['assets'] and asset_url not in self.failed_urls:
                    print(f"    🔎 Checking for common asset: {asset_path}")
                    asset_data = self.download_asset_complete(asset_url)
                    if asset_data:
                        downloaded_content['assets'][asset_url] = asset_data

    def download_website(self, url):
        """Main download method with enhanced error handling"""
        print(f"⬇️ Target: {url}")
        
        # Manual Cloudflare solve
        if not self.manual_cloudflare_solve(url):
            print("❌ Failed to setup Chrome session")
            return None
        
        # Download with complete approach
        result = self.download_with_session_complete(url)
        
        # Cleanup
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        return result

    def download_with_session_complete(self, url):
        """Download using complete approach with enhanced asset capture"""
        print("⬇️ Downloading with ENHANCED COMPLETE asset capture...")
        
        downloaded_content = {
            'main_url': url,
            'pages': {},
            'assets': {},
            'timestamp': time.time(),
            'version': '2.0_enhanced'
        }
        
        # Reset state
        self.visited_urls.clear()
        self.pages_to_crawl.clear()
        self.failed_urls.clear()
        
        # Start enhanced crawling
        self.crawl_website_complete(url, downloaded_content)
        
        # Statistics
        total_pages = len(downloaded_content['pages'])
        total_assets = len(downloaded_content['assets'])
        css_count = sum(1 for asset_url in downloaded_content['assets'] if asset_url.endswith('.css'))
        js_count = sum(1 for asset_url in downloaded_content['assets'] if asset_url.endswith('.js'))
        image_count = sum(1 for asset_url in downloaded_content['assets'] if any(asset_url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']))
        
        print(f"    📊 Final Statistics:")
        print(f"    📄 Total pages: {total_pages}")
        print(f"    📦 Total assets: {total_assets}")
        print(f"    🎨 CSS files: {css_count}")
        print(f"    ⚙️ JavaScript files: {js_count}")
        print(f"    🖼️ Images: {image_count}")
        print(f"    ❌ Failed URLs: {len(self.failed_urls)}")
        
        # Save file
        domain = urlparse(url).netloc.replace(':', '_')
        filename = f"{domain}_ENHANCED_{int(time.time())}.page"
        filepath = os.path.join(self.output_dir, filename)
        
        if self.save_page_file(filepath, downloaded_content):
            print(f"💾 Saved: {filename}")
            return filepath
        else:
            print(f"❌ Failed to save: {filename}")
            return None

    def save_page_file(self, filepath, content):
        """Save as .page file with enhanced metadata"""
        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Enhanced metadata
                metadata = {
                    'main_url': content['main_url'],
                    'timestamp': content['timestamp'],
                    'version': content['version'],
                    'pages': len(content['pages']),
                    'assets': len(content['assets']),
                    'css_files': sum(1 for url in content['assets'] if url.endswith('.css')),
                    'js_files': sum(1 for url in content['assets'] if url.endswith('.js')),
                    'image_files': sum(1 for url in content['assets'] if any(url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'])),
                    'total_size': sum(len(asset['content']) for asset in content['assets'].values()),
                    'failed_urls': list(self.failed_urls)
                }
                zipf.writestr('metadata.json', json.dumps(metadata, indent=2))
                
                # Pages
                for url, data in content['pages'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:12]
                    zipf.writestr(f"pages/{hash_val}.json", json.dumps(data, indent=2))
                
                # Assets
                for url, data in content['assets'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:12]
                    zipf.writestr(f"assets/{hash_val}.json", json.dumps(data, indent=2))
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            print(f"    💾 File size: {file_size:.2f} MB")
            return os.path.exists(filepath)
        except Exception as e:
            print(f"    ❌ Save error: {e}")
            return False

    def download_from_list(self, url_list):
        """Download multiple sites with enhanced reporting"""
        downloaded_files = []
        
        print(f"🎯 Downloading {len(url_list)} sites with ENHANCED COMPLETE assets...")
        print(f"📁 Output: {self.output_dir}")
        
        for i, url in enumerate(url_list, 1):
            url = url.strip()
            if not url:
                continue
                
            print(f"\n{'='*60}")
            print(f"#{i}: {url}")
            print("="*60)
            
            try:
                start_time = time.time()
                filepath = self.download_website(url)
                end_time = time.time()
                
                if filepath:
                    downloaded_files.append(filepath)
                    print(f"✅ Success! ({end_time - start_time:.1f}s) - Downloaded {len(downloaded_files)} sites")
                else:
                    print(f"❌ Failed after {end_time - start_time:.1f}s")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"📊 Complete: {len(downloaded_files)}/{len(url_list)} sites")
        print(f"💾 Location: {self.output_dir}")
        
        return downloaded_files

if __name__ == "__main__":
    print("="*60)
    print("🚀 ENHANCED COMPLETE WEBSITE DOWNLOADER")
    print("📥 Grabs EVERY asset with multiple fallback approaches")
    print("🛡️ Enhanced error recovery and asset discovery")
    print("="*60)
    
    # Install required packages if not present
    try:
        from fake_useragent import UserAgent
        import brotli
        from PIL import Image
    except ImportError:
        print("📦 Installing required packages...")
        import subprocess
        packages = ['fake-useragent', 'brotli', 'pillow']
        for package in packages:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ Installed {package}")
            except:
                print(f"⚠️ Failed to install {package}")
        
        from fake_useragent import UserAgent
        import brotli
        from PIL import Image
    
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
