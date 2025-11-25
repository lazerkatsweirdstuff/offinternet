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
import threading

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
        
        self.driver = None
        self.visited_urls = set()
        self.pages_to_crawl = deque()
        self.max_pages = 10000
        self.crawl_delay = 1  # seconds between requests
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"✅ Created directory: {self.output_dir}")

    def setup_chrome_incognito(self):
        """Setup Chrome with incognito mode"""
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
            
            print("🔄 Starting Chrome in incognito mode...")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(10)
            print("✅ Chrome started successfully in incognito mode")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Chrome: {e}")
            return False

    def manual_cloudflare_solve(self, url):
        """Manual Cloudflare solving"""
        print("🚨 CLOUDFLARE SOLVER - INCOGNITO MODE")
        print("="*50)
        print("Using Chrome incognito mode")
        print("1. Chrome will open in incognito")
        print("2. Solve any security challenges")
        print("3. Press Enter when the page fully loads")
        print("="*50)
        
        if not self.setup_chrome_incognito():
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

    def extract_all_links(self, html, base_url):
        """Extract all links from HTML for crawling"""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        
        # Get all anchor tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                full_url = urljoin(base_url, href)
                # Only add links from the same domain
                if self.is_same_domain(full_url, base_url):
                    links.add(full_url)
        
        return links

    def is_same_domain(self, url, base_url):
        """Check if URL is from the same domain"""
        try:
            parsed_url = urlparse(url)
            parsed_base = urlparse(base_url)
            return parsed_url.netloc == parsed_base.netloc
        except:
            return False

    def crawl_website(self, start_url, downloaded_content):
        """Crawl the website and download all pages"""
        print("🕷️ Starting website crawl...")
        
        self.pages_to_crawl.append(start_url)
        self.visited_urls.add(start_url)
        
        crawled_pages = 0
        
        while self.pages_to_crawl and crawled_pages < self.max_pages:
            current_url = self.pages_to_crawl.popleft()
            
            print(f"📄 Crawling [{crawled_pages+1}/{self.max_pages}]: {current_url}")
            
            # Download the page
            page_data = self.download_page(current_url)
            if page_data:
                downloaded_content['pages'][current_url] = page_data
                crawled_pages += 1
                
                # Extract links from this page for further crawling
                new_links = self.extract_all_links(page_data['content'], current_url)
                for link in new_links:
                    if link not in self.visited_urls:
                        self.visited_urls.add(link)
                        self.pages_to_crawl.append(link)
                        print(f"    🔗 Found new page: {link}")
                
                # Download resources for this page
                self.download_all_resources_aggressive(page_data['content'], current_url, downloaded_content)
                
                # Respect crawl delay
                time.sleep(self.crawl_delay)
            else:
                print(f"    ❌ Failed to download: {current_url}")
        
        print(f"✅ Crawl complete: {crawled_pages} pages downloaded")

    def download_page(self, url):
        """Download a single page"""
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                return {
                    'url': response.url,
                    'content': response.text,
                    'content_type': response.headers.get('content-type', 'text/html'),
                    'status_code': 200,
                    'downloaded_with': 'session'
                }
            else:
                print(f"    ⚠️ HTTP {response.status_code} for {url}")
                return None
        except Exception as e:
            print(f"    ❌ Error downloading {url}: {e}")
            return None

    def download_all_resources_aggressive(self, html, base_url, downloaded_content):
        """Aggressively download ALL resources including from CDNs"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find ALL possible resource URLs
        all_resource_urls = set()
        
        # CSS files
        for link in soup.find_all('link', href=True):
            href = link.get('href')
            if href and not href.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, href)
                all_resource_urls.add(full_url)
        
        # JavaScript files
        for script in soup.find_all('script', src=True):
            src = script.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                all_resource_urls.add(full_url)
        
        # Images
        for img in soup.find_all('img', src=True):
            src = img.get('src')
            if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, src)
                all_resource_urls.add(full_url)
        
        # Also look for URLs in inline scripts and styles
        for script in soup.find_all('script'):
            if script.string:
                # Find URLs in JavaScript
                urls = re.findall(r'["\'](https?://[^"\']+\.(css|js|png|jpg|jpeg|gif|svg|woff|woff2))["\']', script.string)
                for url, ext in urls:
                    all_resource_urls.add(url)
        
        for style in soup.find_all('style'):
            if style.string:
                # Find URLs in CSS
                urls = re.findall(r'url\(["\']?(https?://[^"\'\)]+)["\']?\)', style.string)
                for url in urls:
                    all_resource_urls.add(url)
        
        print(f"    📦 Found {len(all_resource_urls)} resources in page")
        
        # Download ALL resources (no skipping!)
        successful = 0
        for i, resource_url in enumerate(all_resource_urls):
            if resource_url in downloaded_content['assets']:
                continue
                
            name = os.path.basename(resource_url) or resource_url[:50]
            print(f"    [{i+1}/{len(all_resource_urls)}] Downloading: {name}")
            
            asset_data = self.download_resource_aggressive(resource_url)
            if asset_data:
                downloaded_content['assets'][resource_url] = asset_data
                successful += 1
            else:
                print(f"      ❌ Failed to download: {name}")
        
        print(f"    ✅ Successfully downloaded: {successful}/{len(all_resource_urls)} assets")

    def download_resource_aggressive(self, url):
        """Download resource with aggressive retry and no skipping"""
        try:
            response = self.session.get(url, timeout=10, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '').lower()
                
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
                print(f"      ⚠️ HTTP {response.status_code} for {url}")
                return None
                
        except Exception as e:
            print(f"      ❌ Error downloading {url}: {e}")
            return None

    def download_with_session(self, url):
        """Download using captured session - NOW WITH CRAWLING"""
        print("⬇️ Downloading with session and crawling...")
        
        downloaded_content = {
            'main_url': url,
            'pages': {},
            'assets': {},
            'timestamp': time.time(),
        }
        
        # Reset crawling state
        self.visited_urls.clear()
        self.pages_to_crawl.clear()
        
        # Start crawling from the main URL
        self.crawl_website(url, downloaded_content)
        
        print(f"    📊 Total pages downloaded: {len(downloaded_content['pages'])}")
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

    def save_page_file(self, filepath, content):
        """Save as .page file - FIXED to properly save assets"""
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
                
                # Assets - FIXED: Save as individual JSON files in assets folder
                for url, data in content['assets'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:10]
                    # Save each asset as a separate JSON file
                    zipf.writestr(f"assets/{hash_val}.json", json.dumps(data, indent=2))
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)
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
        
        # Download with session AND CRAWLING
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
    print("🚀 ADVANCED WEBSITE DOWNLOADER - WITH CRAWLING")
    print("📥 Downloads ALL pages, CSS, JS, Images!")
    print("🌐 Works with complex sites and follows links")
    print("="*50)
    
    sites = [
        "https://discord.com",
    ]
    
    # Or get sites from user input
    if len(sys.argv) > 1:
        sites = sys.argv[1:]
    else:
        user_input = input("Enter websites to download (comma-separated, or press Enter for default): ").strip()
        if user_input:
            sites = [site.strip() for site in user_input.split(',')]
    
    downloader = AdvancedWebsiteDownloader()
    files = downloader.download_from_list(sites)
    
    if files:
        print(f"\n🎉 Success! Downloaded sites with ALL pages and assets")
        print("💡 Now run the browser.py to view your downloaded sites!")
    else:
        print(f"\n❌ No sites downloaded")
