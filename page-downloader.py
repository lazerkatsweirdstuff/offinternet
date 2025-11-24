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

class AdvancedWebsiteDownloader:
    def __init__(self, output_dir=None):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if output_dir is None:
            self.output_dir = os.path.join(script_dir, "downloaded_sites")
        else:
            self.output_dir = os.path.abspath(output_dir)
            
        print(f"📁 Save location: {self.output_dir}")
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ Created directory: {self.output_dir}")

    def get_chrome_user_data_dir(self):
        """Get Chrome user data directory"""
        if os.name == 'nt':  # Windows
            app_data = os.getenv('LOCALAPPDATA')
            return os.path.join(app_data, 'Google', 'Chrome', 'User Data')
        else:  # Linux/Mac
            home = os.path.expanduser('~')
            return os.path.join(home, '.config', 'google-chrome')

    def setup_chrome_normal(self):
        """Setup Chrome with normal profile"""
        try:
            chrome_options = Options()
            
            # Get user data directory
            user_data_dir = self.get_chrome_user_data_dir()
            
            # Use normal Chrome profile
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            chrome_options.add_argument("--profile-directory=Default")
            
            # Important: Use a custom profile to avoid conflicts with running Chrome
            chrome_options.add_argument("--profile-directory=TempSeleniumProfile")
            
            # Standard options
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1400,1000")
            chrome_options.add_argument("--start-maximized")
            
            # Remove automation flags
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Don't use the default profile to avoid conflicts
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--no-default-browser-check")
            
            print("🔄 Starting Chrome with normal profile...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Remove webdriver flag
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.driver.implicitly_wait(10)
            print("✅ Chrome started successfully with normal profile")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome with normal profile: {e}")
            print("🔄 Trying with temporary profile instead...")
            return self.setup_chrome_temp()

    def setup_chrome_temp(self):
        """Setup Chrome with temporary profile (fallback)"""
        try:
            chrome_options = Options()
            
            # Use temporary profile
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1400,1000")
            chrome_options.add_argument("--start-maximized")
            
            # Remove automation flags
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            print("🔄 Starting Chrome with temporary profile...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.driver.implicitly_wait(10)
            print("✅ Chrome started successfully with temporary profile")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            return False

    def manual_cloudflare_solve(self, url):
        """Manual Cloudflare solving"""
        print("🚨 CLOUDFLARE SOLVER - NORMAL CHROME")
        print("="*50)
        print("Using your Chrome profile (not incognito)")
        print("1. Chrome will open")
        print("2. Solve Cloudflare challenge")
        print("3. Press Enter when you see DeepSeek chat")
        print("="*50)
        
        # Try normal profile first, then fallback to temp
        if not self.setup_chrome_normal():
            return False
            
        try:
            print("🌐 Opening DeepSeek...")
            self.driver.get(url)
            
            print("\n" + "="*50)
            print("💡 CHROME IS OPEN!")
            print("Please:")
            print("1. Solve the Cloudflare challenge")
            print("2. Wait for DeepSeek chat to load")
            print("3. Return here and press Enter")
            print("="*50)
            
            input("⏳ Press Enter when you see DeepSeek chat...")
            
            # Get current state
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

    def download_with_session(self, url):
        """Download using captured session"""
        print("⬇️ Downloading with session...")
        
        downloaded_content = {
            'main_url': url,
            'pages': {},
            'assets': {},
            'timestamp': time.time(),
        }
        
        # Download main page
        try:
            print("    📄 Downloading main page...")
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                main_page_data = {
                    'url': response.url,
                    'content': response.text,
                    'content_type': response.headers.get('content-type', 'text/html'),
                    'status_code': 200,
                    'downloaded_with': 'session'
                }
                downloaded_content['pages'][url] = main_page_data
                downloaded_content['pages'][response.url] = main_page_data
                print(f"    ✅ Main page from {response.url}")
                
                # Extract and download ALL resources from main page
                self.download_all_resources(response.text, response.url, downloaded_content)
            else:
                print(f"    ❌ Main page: {response.status_code}")
                return None
        except Exception as e:
            print(f"    ❌ Main page error: {e}")
            return None
        
        # Also try to get additional resources from the page after JavaScript execution
        if self.driver:
            try:
                print("    🔍 Extracting resources from live DOM...")
                page_source = self.driver.page_source
                self.download_all_resources(page_source, self.driver.current_url, downloaded_content)
            except Exception as e:
                print(f"    ⚠️ Could not extract from live DOM: {e}")
        
        print(f"    📊 Total assets downloaded: {len(downloaded_content['assets'])}")
        
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

    def download_all_resources(self, html, base_url, downloaded_content):
        """Extract and download ALL resources from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extended list of resource types to download
        resource_patterns = [
            # CSS files
            ('link[rel="stylesheet"]', 'href'),
            ('link[rel="preload"]', 'href'),
            ('link[as="style"]', 'href'),
            
            # JavaScript files
            ('script[src]', 'src'),
            
            # Images
            ('img', 'src'),
            ('img', 'srcset'),
            ('picture source', 'srcset'),
            ('link[rel="icon"]', 'href'),
            ('link[rel="shortcut icon"]', 'href'),
            ('link[rel="apple-touch-icon"]', 'href'),
            ('meta[property="og:image"]', 'content'),
            ('meta[name="twitter:image"]', 'content'),
            
            # Fonts
            ('link[rel="preload"][as="font"]', 'href'),
            ('link[href*=".woff"]', 'href'),
            ('link[href*=".woff2"]', 'href'),
            ('link[href*=".ttf"]', 'href'),
            ('link[href*=".eot"]', 'href'),
            
            # Media
            ('video', 'src'),
            ('video source', 'src'),
            ('audio', 'src'),
            ('audio source', 'src'),
            
            # Frames and embeds
            ('iframe', 'src'),
            ('embed', 'src'),
            ('object', 'data'),
            
            # Manifest and meta
            ('link[rel="manifest"]', 'href'),
            ('link[rel="canonical"]', 'href'),
        ]
        
        all_resource_urls = set()
        
        # Extract from HTML tags
        for selector, attr in resource_patterns:
            for tag in soup.select(selector):
                urls = []
                if attr in tag.attrs:
                    if attr == 'srcset':
                        # Parse srcset (multiple images with descriptors)
                        srcset = tag[attr]
                        for source in srcset.split(','):
                            url_part = source.strip().split(' ')[0]
                            if url_part:
                                urls.append(url_part)
                    else:
                        urls.append(tag[attr])
                
                for url in urls:
                    if url and not url.startswith(('data:', 'blob:', 'javascript:')):
                        full_url = urljoin(base_url, url)
                        all_resource_urls.add(full_url)
        
        # Extract URLs from inline CSS and JavaScript
        inline_resources = self.extract_from_inline_content(soup, base_url)
        all_resource_urls.update(inline_resources)
        
        # Extract from CSS @import and url() patterns in style tags
        style_resources = self.extract_from_style_tags(soup, base_url)
        all_resource_urls.update(style_resources)
        
        # Download all found resources
        print(f"    📦 Found {len(all_resource_urls)} total resources")
        
        successful = 0
        for i, resource_url in enumerate(all_resource_urls):
            if resource_url in downloaded_content['assets']:
                continue
                
            name = os.path.basename(resource_url) or resource_url[:50]
            print(f"    [{i+1}/{len(all_resource_urls)}] Downloading: {name}")
            
            asset_data = self.download_resource(resource_url)
            if asset_data:
                downloaded_content['assets'][resource_url] = asset_data
                successful += 1
        
        print(f"    ✅ Successfully downloaded: {successful}/{len(all_resource_urls)} assets")

    def extract_from_inline_content(self, soup, base_url):
        """Extract resource URLs from inline content (style attributes, script content)"""
        resources = set()
        
        # Extract from style attributes
        for tag in soup.find_all(style=True):
            style_content = tag['style']
            urls = re.findall(r'url\([\'"]?([^\)\'"]+)[\'"]?\)', style_content)
            for url in urls:
                if not url.startswith(('data:', 'blob:')):
                    full_url = urljoin(base_url, url)
                    resources.add(full_url)
        
        # Extract from script content
        for script in soup.find_all('script'):
            if script.string:
                script_content = script.string
                # Look for various URL patterns in JavaScript
                patterns = [
                    r'["\'](https?://[^"\']*\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot))["\']',
                    r'url\(["\']?([^"\'\)]+)["\']?\)',
                    r'src\s*=\s*["\']([^"\'\)]+)["\']',
                    r'href\s*=\s*["\']([^"\'\)]+)["\']',
                    r'["\'](/[^"\'\)]*\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot))["\']',
                    r'["\'](\.\.[^"\'\)]*\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot))["\']',
                    r'["\'](\./[^"\'\)]*\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2|ttf|eot))["\']',
                ]
                for pattern in patterns:
                    matches = re.findall(pattern, script_content)
                    for match in matches:
                        if isinstance(match, tuple):
                            url = match[0]
                        else:
                            url = match
                        if not url.startswith(('data:', 'blob:', 'javascript:')):
                            full_url = urljoin(base_url, url)
                            resources.add(full_url)
        
        return resources

    def extract_from_style_tags(self, soup, base_url):
        """Extract resources from style tag content"""
        resources = set()
        
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                css_content = style_tag.string
                # Extract @import rules
                imports = re.findall(r'@import\s+["\']([^"\'\)]+)["\']', css_content)
                for import_url in imports:
                    if not import_url.startswith(('data:', 'blob:')):
                        full_url = urljoin(base_url, import_url)
                        resources.add(full_url)
                
                # Extract url() references
                urls = re.findall(r'url\([\'"]?([^\)\'"]+)[\'"]?\)', css_content)
                for url in urls:
                    if not url.startswith(('data:', 'blob:')):
                        full_url = urljoin(base_url, url)
                        resources.add(full_url)
        
        return resources

    def download_resource(self, url):
        """Download a resource with better error handling"""
        try:
            response = self.session.get(url, timeout=15, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
                # Handle different content types appropriately
                if any(ct in content_type for ct in ['image', 'font', 'binary', 'video', 'audio', 'octet-stream']):
                    content = response.content
                    encoded = base64.b64encode(content).decode('utf-8')
                    encoding = 'base64'
                else:
                    # For text files (CSS, JS, HTML)
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
                print(f"      ⚠️ HTTP {response.status_code} for {url}")
        except requests.exceptions.Timeout:
            print(f"      ⏰ Timeout for {url}")
        except requests.exceptions.ConnectionError:
            print(f"      🔌 Connection error for {url}")
        except Exception as e:
            print(f"      ❌ Error downloading {url}: {e}")
        
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
                
                # Assets - organized by type
                css_count = js_count = image_count = font_count = other_count = 0
                
                for url, data in content['assets'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:10]
                    filename = data.get('filename', 'resource')
                    
                    # Categorize assets
                    content_type = data.get('content_type', '')
                    if 'css' in content_type:
                        folder = 'css'
                        css_count += 1
                    elif 'javascript' in content_type or 'application/javascript' in content_type:
                        folder = 'js'
                        js_count += 1
                    elif 'image' in content_type:
                        folder = 'images'
                        image_count += 1
                    elif 'font' in content_type:
                        folder = 'fonts'
                        font_count += 1
                    else:
                        folder = 'other'
                        other_count += 1
                    
                    zipf.writestr(f"assets/{folder}/{hash_val}_{filename}", json.dumps(data, indent=2))
                
                # Add asset summary
                asset_summary = {
                    'css_files': css_count,
                    'js_files': js_count,
                    'images': image_count,
                    'fonts': font_count,
                    'other_assets': other_count
                }
                zipf.writestr('asset_summary.json', json.dumps(asset_summary, indent=2))
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # Size in MB
            print(f"    💾 File size: {file_size:.2f} MB")
            return os.path.exists(filepath)
        except Exception as e:
            print(f"    ❌ Save error: {e}")
            return False

    def download_website(self, url):
        """Main download method"""
        print(f"⬇️ Target: {url}")
        
        # Manual Cloudflare solve
        if not self.manual_cloudflare_solve(url):
            print("❌ Failed to setup Chrome session")
            return None
        
        # Download with session
        result = self.download_with_session(url)
        
        # Cleanup
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        return result

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
                    print(f"✅ Success!")
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
    print("🚀 ENHANCED WEBSITE DOWNLOADER - DOWNLOADS ALL FILES")
    print("📥 Now downloads: CSS, JS, Images, Fonts, Media, and more!")
    print("="*50)
    
    sites = ["https://discord.com"]
    
    downloader = AdvancedWebsiteDownloader()
    files = downloader.download_from_list(sites)
    
    if files:
        print(f"\n🎉 Success! Downloaded {len(files)} sites with ALL assets")
    else:
        print(f"\n❌ No sites downloaded")
