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
        self.max_pages = 200
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

    def extract_all_links_complete(self, html, base_url):
        """Extract ALL links for comprehensive crawling"""
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
            '.pdf', '.zip', '.exe', '.dmg',
            '/api/', '/ajax/', '/graphql', '/websocket'
        ]
        url_lower = url.lower()
        return any(pattern in url_lower for pattern in junk_patterns)

    def clean_url(self, url):
        """Clean URL but keep important parameters"""
        try:
            parsed = urlparse(url)
            # Remove fragment only
            cleaned = parsed._replace(fragment='')
            return cleaned.geturl()
        except Exception:
            return url

    def download_with_retry_complete(self, url, retry_count=0):
        """Download with complete retry logic"""
        if retry_count >= self.max_retries:
            self.failed_urls.add(url)
            return None
        
        try:
            time.sleep(random.uniform(0.5, 1.5))
            
            if random.random() < 0.2:
                self.update_session_headers()
            
            response = self.session.get(url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"    🚫 403 Forbidden: {url}")
                time.sleep(5)
                return self.download_with_retry_complete(url, retry_count + 1)
            elif response.status_code == 429:
                print(f"    🐢 429 Rate Limited - waiting 10s: {url}")
                time.sleep(10)
                return self.download_with_retry_complete(url, retry_count + 1)
            else:
                print(f"    ⚠️ HTTP {response.status_code} for {url}")
                time.sleep(3)
                return self.download_with_retry_complete(url, retry_count + 1)
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            time.sleep(3)
            return self.download_with_retry_complete(url, retry_count + 1)

    def crawl_website_complete(self, start_url, downloaded_content):
        """Complete website crawling with asset capture"""
        print("🕷️ Starting COMPLETE website crawl...")
        
        self.pages_to_crawl.append(start_url)
        self.visited_urls.add(start_url)
        
        crawled_pages = 0
        consecutive_failures = 0
        
        while self.pages_to_crawl and crawled_pages < self.max_pages:
            if consecutive_failures >= 5:
                print("    🚨 Too many failures, stopping crawl")
                break
                
            current_url = self.pages_to_crawl.popleft()
            
            print(f"📄 [{crawled_pages+1}/{self.max_pages}] {os.path.basename(current_url) or current_url[:80]}")
            
            # Download the page
            page_data = self.download_page_complete(current_url)
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
                
                # Download ALL assets including CSS from this page
                self.download_all_assets_complete(page_data['content'], current_url, downloaded_content)
                
                time.sleep(random.uniform(1, 2))
            else:
                consecutive_failures += 1
                print(f"    ❌ Failed (#{consecutive_failures})")
        
        print(f"✅ Crawl complete: {crawled_pages} pages")

    def download_page_complete(self, url):
        """Download a single page"""
        response = self.download_with_retry_complete(url)
        if response and response.status_code == 200:
            return {
                'url': response.url,
                'content': response.text,
                'content_type': response.headers.get('content-type', 'text/html'),
                'status_code': 200,
                'downloaded_with': 'session'
            }
        return None

    def download_asset_complete(self, url):
        """Download asset with complete error handling - IMPROVED for CSS"""
        try:
            # Special handling for CSS files - don't auto-decompress
            if url.endswith('.css'):
                headers = self.session.headers.copy()
                headers['Accept-Encoding'] = 'identity'  # Don't accept gzip for CSS
                response = self.session.get(url, timeout=10, stream=True, headers=headers)
            else:
                response = self.session.get(url, timeout=10, stream=True)
                
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # For CSS files, always treat as binary to preserve content
                if url.endswith('.css'):
                    content = response.content
                    
                    # Skip very large files (>5MB)
                    if len(content) > 5 * 1024 * 1024:
                        print(f"      ⚠️ Skipping large CSS file: {len(content)//1024}KB")
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
                        'is_css': True
                    }
                else:
                    # Handle other content types normally
                    is_gzipped = response.headers.get('content-encoding') == 'gzip'
                    
                    if any(ct in content_type for ct in ['image', 'font', 'binary', 'octet-stream']) or is_gzipped:
                        content = response.content
                        
                        if is_gzipped:
                            try:
                                content = gzip.decompress(content)
                            except:
                                pass  # Keep as-is if decompression fails
                        
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
                            'filename': os.path.basename(urlparse(url).path) or 'resource'
                        }
                    else:
                        # Text content
                        content = response.content
                        try:
                            encoded = content.decode('utf-8')
                            encoding = 'text'
                        except UnicodeDecodeError:
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
            print(f"      ❌ Error downloading asset {url}: {e}")
            return None

    def download_css_assets(self, css_asset, css_url, downloaded_content):
        """Download assets referenced in CSS files - FIXED for gzipped CSS"""
        try:
            css_content = css_asset['content']
            
            # Handle both text and base64 encoded CSS
            if css_asset['encoding'] == 'base64':
                css_content = base64.b64decode(css_content)
                
                # Try multiple methods to decode the CSS content
                css_text = None
                
                # Method 1: Try direct UTF-8 decode
                try:
                    css_text = css_content.decode('utf-8')
                    print("      🔍 CSS decoded as UTF-8 text")
                except UnicodeDecodeError:
                    # Method 2: Try gzip decompression
                    try:
                        # Check if it's gzipped by looking for gzip magic number
                        if css_content[:2] == b'\x1f\x8b':
                            css_text = gzip.decompress(css_content).decode('utf-8')
                            print("      🔍 Decompressed gzipped CSS for asset extraction")
                        else:
                            # Method 3: Try other encodings
                            try:
                                css_text = css_content.decode('latin-1')
                                print("      🔍 CSS decoded as latin-1 text")
                            except:
                                # Method 4: Try to detect if it's minified CSS and process as binary
                                css_text = self.process_binary_css(css_content)
                    except Exception as e:
                        print(f"      ⚠️ CSS decompression failed: {e}")
                        css_text = self.process_binary_css(css_content)
            else:
                # Already text
                css_text = css_content
            
            if not css_text:
                print("      ⚠️ Could not extract text from CSS, skipping asset extraction")
                return
            
            # Find all url() references in CSS
            urls = self.extract_css_urls(css_text)
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
                elif url.startswith(('http://', 'https://')):
                    # Already absolute
                    full_url = url
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

    def process_binary_css(self, css_content):
        """Try to extract URLs from binary CSS content"""
        try:
            # Convert to string using latin-1 which preserves all bytes
            css_text = css_content.decode('latin-1')
            
            # Try to find URLs using multiple patterns
            urls_patterns = [
                r'url\([\'"]?([^)"\']+)[\'"]?\)',
                r'@import\s+[\'"]([^\'"]+)[\'"]',
                r'src:\s*url\([\'"]?([^)"\']+)[\'"]?\)'
            ]
            
            all_urls = []
            for pattern in urls_patterns:
                urls = re.findall(pattern, css_text)
                all_urls.extend(urls)
            
            if all_urls:
                print(f"      🔍 Found {len(all_urls)} URLs in binary CSS")
                return css_text
            else:
                print("      ⚠️ No URLs found in binary CSS")
                return None
                
        except Exception as e:
            print(f"      ⚠️ Binary CSS processing failed: {e}")
            return None

    def extract_css_urls(self, css_text):
        """Extract all URLs from CSS text using multiple patterns"""
        urls = set()
        
        # Pattern 1: url() references
        url_patterns = [
            r'url\([\'"]?([^)"\']+)[\'"]?\)',
            r'@import\s+[\'"]([^\'"]+)[\'"]',
            r'src:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'@font-face\s*\{[^}]*src:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'background-image:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
            r'content:\s*url\([\'"]?([^)"\']+)[\'"]?\)'
        ]
        
        for pattern in url_patterns:
            matches = re.findall(pattern, css_text, re.IGNORECASE)
            for match in matches:
                # Clean up the URL
                url = match.strip()
                if url and not url.startswith(('data:', 'blob:')):
                    urls.add(url)
        
        return list(urls)

    def get_selenium_resources(self):
        """Use Selenium to find additional resources"""
        resources = set()
        try:
            # Get all resource URLs from browser network (approximation)
            scripts = self.driver.find_elements(By.TAG_NAME, "script")
            links = self.driver.find_elements(By.TAG_NAME, "link")
            images = self.driver.find_elements(By.TAG_NAME, "img")
            
            for script in scripts:
                src = script.get_attribute("src")
                if src and src.startswith('http'):
                    resources.add(src)
            
            for link in links:
                href = link.get_attribute("href")
                if href and href.startswith('http'):
                    resources.add(href)
            
            for img in images:
                src = img.get_attribute("src")
                if src and src.startswith('http'):
                    resources.add(src)
                    
        except Exception as e:
            print(f"      ⚠️ Selenium resource error: {e}")
        
        return resources

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

    def download_website(self, url):
        """Main download method"""
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
        """Download using complete approach"""
        print("⬇️ Downloading with COMPLETE asset capture...")
        
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
        
        # Start complete crawling
        self.crawl_website_complete(url, downloaded_content)
        
        print(f"    📊 Total pages: {len(downloaded_content['pages'])}")
        print(f"    📊 Total assets: {len(downloaded_content['assets'])}")
        
        # Count CSS files specifically
        css_count = sum(1 for asset_url in downloaded_content['assets'] if asset_url.endswith('.css'))
        print(f"    🎨 CSS files: {css_count}")
        
        # Save file
        domain = urlparse(url).netloc.replace(':', '_')
        filename = f"{domain}_COMPLETE_{int(time.time())}.page"
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
                    'css_files': sum(1 for url in content['assets'] if url.endswith('.css')),
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

    def download_from_list(self, url_list):
        """Download multiple sites"""
        downloaded_files = []
        
        print(f"🎯 Downloading {len(url_list)} sites with COMPLETE assets...")
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
    print("🚀 COMPLETE WEBSITE DOWNLOADER - FIXED CSS EXTRACTION")
    print("📥 Handles gzipped/binary CSS files properly")
    print("🌐 Extracts assets from all CSS files")
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
