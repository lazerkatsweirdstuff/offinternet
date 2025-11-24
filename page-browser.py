import os
import zipfile
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
from urllib.parse import urlparse, unquote
import tempfile
import base64

def get_script_directory():
    """Get the directory where the script is located"""
    return os.path.dirname(os.path.abspath(__file__))

class PageFileBrowser:
    def __init__(self, pages_directory=None):
        # Always look in script directory by default
        script_dir = get_script_directory()
        if pages_directory is None:
            self.pages_directory = os.path.join(script_dir, "downloaded_sites")
        else:
            self.pages_directory = os.path.abspath(pages_directory)
            
        print(f"📁 Script location: {script_dir}")
        print(f"📁 Browser looking for .page files in: {self.pages_directory}")
        self.loaded_sites = {}
        
        # Check if directory exists
        if not os.path.exists(self.pages_directory):
            print(f"❌ ERROR: Directory not found: {self.pages_directory}")
            print("Please run the downloader first or specify the correct path.")
            print(f"Expected to find: downloaded_sites folder in {script_dir}")
            return
        
    def load_page_file(self, filepath):
        """Load a .page file into memory"""
        try:
            with zipfile.ZipFile(filepath, 'r') as zipf:
                # Read metadata
                metadata_str = zipf.read('metadata.json').decode('utf-8')
                metadata = json.loads(metadata_str)
                
                # Read all pages
                pages = {}
                for file_info in zipf.filelist:
                    if file_info.filename.startswith('pages/') and file_info.filename.endswith('.json'):
                        page_data_str = zipf.read(file_info.filename).decode('utf-8')
                        page_data = json.loads(page_data_str)
                        pages[page_data['url']] = page_data
                
                # Read assets
                assets = {}
                for file_info in zipf.filelist:
                    if file_info.filename.startswith('assets/') and file_info.filename.endswith('.json'):
                        asset_data_str = zipf.read(file_info.filename).decode('utf-8')
                        asset_data = json.loads(asset_data_str)
                        assets[asset_data['url']] = asset_data
                
                site_data = {
                    'metadata': metadata,
                    'pages': pages,
                    'assets': assets
                }
                
                domain = metadata['main_url']
                self.loaded_sites[domain] = site_data
                print(f"✅ Loaded site: {domain} with {len(pages)} pages and {len(assets)} assets")
                return site_data
                
        except Exception as e:
            print(f"❌ Error loading {filepath}: {e}")
            return None
    
    def load_all_page_files(self):
        """Load all .page files from the directory"""
        if not os.path.exists(self.pages_directory):
            print(f"❌ Directory {self.pages_directory} does not exist")
            return
        
        files = os.listdir(self.pages_directory)
        page_files = [f for f in files if f.endswith('.page')]
        
        print(f"📄 Found {len(page_files)} .page files:")
        for filename in page_files:
            filepath = os.path.join(self.pages_directory, filename)
            print(f"  • Loading: {filename}")
            self.load_page_file(filepath)
        
        print(f"✅ Total sites loaded: {len(self.loaded_sites)}")
    
    def find_page_by_url(self, url):
        """Find a page across all loaded sites by URL"""
        # Exact match
        for site_data in self.loaded_sites.values():
            if url in site_data['pages']:
                return site_data['pages'][url]
        
        # Try without protocol
        if url.startswith('http://'):
            alt_url = url.replace('http://', 'https://', 1)
            for site_data in self.loaded_sites.values():
                if alt_url in site_data['pages']:
                    return site_data['pages'][alt_url]
        elif url.startswith('https://'):
            alt_url = url.replace('https://', 'http://', 1)
            for site_data in self.loaded_sites.values():
                if alt_url in site_data['pages']:
                    return site_data['pages'][alt_url]
        
        # Try to find by path or domain
        for site_data in self.loaded_sites.values():
            for page_url, page_data in site_data['pages'].items():
                # Match by path
                if url in page_url:
                    return page_data
                # Match by filename
                if url.endswith('/'):
                    if page_url.startswith(url):
                        return page_data
                # Match domain only
                if urlparse(url).netloc and urlparse(url).netloc == urlparse(page_url).netloc:
                    return page_data
        
        return None

    def find_asset_by_url(self, url):
        """Find an asset across all loaded sites by URL"""
        # Exact match
        for site_data in self.loaded_sites.values():
            if url in site_data['assets']:
                return site_data['assets'][url]
        
        # Try without protocol
        if url.startswith('http://'):
            alt_url = url.replace('http://', 'https://', 1)
            for site_data in self.loaded_sites.values():
                if alt_url in site_data['assets']:
                    return site_data['assets'][alt_url]
        elif url.startswith('https://'):
            alt_url = url.replace('https://', 'http://', 1)
            for site_data in self.loaded_sites.values():
                if alt_url in site_data['assets']:
                    return site_data['assets'][alt_url]
        
        return None

class PageFileRequestHandler(SimpleHTTPRequestHandler):
    page_browser = None
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            # Parse the requested path
            path = unquote(self.path)
            
            # Remove query parameters
            if '?' in path:
                path = path.split('?')[0]
            
            print(f"🔍 Requested path: {path}")
            
            # Handle root - show index of loaded sites
            if path == '/' or path == '/index.html':
                self.serve_index()
                return
            
            # Handle asset requests
            if path.startswith('/asset/'):
                self.serve_asset(path)
                return
            
            # Handle requests for specific pages
            if path.startswith('/page/'):
                self.serve_saved_page(path)
                return
            
            # Default to trying to find a matching page
            self.serve_saved_page(f'/page{path}')
            
        except Exception as e:
            self.send_error(500, f"Server error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def serve_index(self):
        """Serve an index page listing all loaded sites"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <html>
        <head>
            <title>Offline Website Browser</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
                .header { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                .site { background: white; padding: 20px; margin: 10px 0; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
                .pages { margin-left: 20px; margin-top: 10px; }
                a { color: #0066cc; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .stats { color: #666; font-size: 14px; margin-top: 5px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🌐 Offline Website Browser</h1>
                <p>Loaded websites from your downloaded_sites folder:</p>
            </div>
        """
        
        if not self.page_browser.loaded_sites:
            html += """
            <div class="site">
                <h2>No sites loaded</h2>
                <p>No .page files found in the downloaded_sites directory.</p>
                <p>Run the downloader first to download some websites!</p>
            </div>
            """
        else:
            for domain, site_data in self.page_browser.loaded_sites.items():
                metadata = site_data['metadata']
                
                html += f"""
                <div class="site">
                    <h2><a href="/page/{domain}">{domain}</a></h2>
                    <div class="stats">
                        📄 {len(site_data['pages'])} pages • 
                        🎨 {len(site_data['assets'])} assets •
                        💾 {metadata.get('total_size', 0) // 1024} KB
                    </div>
                    <div class="pages">
                        <strong>Main Pages:</strong>
                        <ul>
                """
                
                # Show main pages (not all pages to avoid clutter)
                main_pages = list(site_data['pages'].keys())[:5]
                for page_url in main_pages:
                    page_name = urlparse(page_url).path or '/'
                    if len(page_name) > 50:
                        page_name = page_name[:47] + '...'
                    html += f'<li><a href="/page/{page_url}">{page_name}</a></li>'
                
                if len(site_data['pages']) > 5:
                    html += f'<li>... and {len(site_data["pages"]) - 5} more pages</li>'
                
                html += """
                        </ul>
                    </div>
                </div>
                """
        
        html += "</body></html>"
        
        self.wfile.write(html.encode('utf-8'))
    
    def serve_saved_page(self, path):
        """Serve a page from the loaded .page files"""
        # Extract the requested URL from the path
        requested_url = path[6:]  # Remove '/page/' prefix
        
        if not requested_url:
            self.send_error(404, "Page not found")
            return
        
        print(f"🔍 Looking for page: {requested_url}")
        
        # Find the page in loaded sites
        page_data = self.page_browser.find_page_by_url(requested_url)
        
        if page_data:
            content = page_data['content']
            
            # Fix links in the content to work with our offline browser
            content = self.rewrite_links(content, page_data['url'])
            
            self.send_response(200)
            self.send_header('Content-type', page_data.get('content_type', 'text/html'))
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            print(f"✅ Served page: {requested_url}")
        else:
            print(f"❌ Page not found: {requested_url}")
            self.send_error(404, f"Page not found: {requested_url}")
    
    def serve_asset(self, path):
        """Serve asset files (CSS, JS, images, etc.)"""
        try:
            # Extract asset URL from path: /asset/ENCODED_URL
            encoded_url = path[7:]  # Remove '/asset/' prefix
            
            if not encoded_url:
                self.send_error(404, "Asset URL not specified")
                return
            
            # URL decode the asset URL
            asset_url = unquote(encoded_url)
            
            print(f"🔍 Looking for asset: {asset_url}")
            
            # Find asset in loaded sites
            asset_data = self.page_browser.find_asset_by_url(asset_url)
            
            if not asset_data:
                print(f"❌ Asset not found: {asset_url}")
                self.send_error(404, f"Asset not found: {asset_url}")
                return
            
            # Determine content type
            content_type = asset_data.get('content_type', 'application/octet-stream')
            encoding = asset_data.get('encoding', 'text')
            content = asset_data['content']
            
            self.send_response(200)
            self.send_header('Content-type', content_type)
            
            if encoding == 'base64':
                # Decode base64 content
                binary_content = base64.b64decode(content)
                self.send_header('Content-Length', str(len(binary_content)))
                self.end_headers()
                self.wfile.write(binary_content)
            else:
                # Text content
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
            
            print(f"✅ Served asset: {asset_url} ({len(content)} bytes)")
            
        except Exception as e:
            print(f"❌ Error serving asset: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Asset serving error: {str(e)}")
    
    def rewrite_links(self, html, base_url):
        """Rewrite links in HTML to work with offline browser"""
        from bs4 import BeautifulSoup
        import re
        
        soup = BeautifulSoup(html, 'html.parser')
        base_domain = urlparse(base_url).netloc
        
        # Rewrite <a> tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith(('http://', 'https://')):
                # External link - keep as is or make it open in offline browser
                if base_domain in href:
                    link['href'] = f"/page/{href}"
                # Otherwise leave external links as-is
            elif href.startswith('/'):
                # Absolute path
                link['href'] = f"/page/{urlparse(base_url).scheme}://{base_domain}{href}"
            elif href.startswith('#') or href.startswith('javascript:'):
                # Anchors and JS links - leave as is
                pass
            else:
                # Relative path
                link['href'] = f"/page/{urljoin(base_url, href)}"
        
        # Rewrite <script> tags
        for script in soup.find_all('script', src=True):
            src = script['src']
            if src and not src.startswith(('data:', 'blob:')):
                script['src'] = f"/asset/{src}"
        
        # Rewrite <link> tags (CSS, etc.)
        for link in soup.find_all('link', href=True):
            href = link['href']
            if href and not href.startswith(('data:', 'blob:')):
                link['href'] = f"/asset/{href}"
        
        # Rewrite <img> tags
        for img in soup.find_all('img', src=True):
            src = img['src']
            if src and not src.startswith(('data:', 'blob:')):
                img['src'] = f"/asset/{src}"
        
        # Rewrite CSS url() references
        style_tags = soup.find_all('style')
        for style in style_tags:
            if style.string:
                style.string = re.sub(
                    r'url\(([^)]+)\)',
                    lambda m: f"url(/asset/{m.group(1)})",
                    style.string
                )
        
        return str(soup)

def start_browser(pages_directory=None, port=8000):
    """Start the web browser server"""
    script_dir = get_script_directory()
    if pages_directory is None:
        pages_directory = os.path.join(script_dir, "downloaded_sites")
    else:
        pages_directory = os.path.abspath(pages_directory)
    
    print(f"🔍 Looking for .page files in: {pages_directory}")
    
    # Create and configure the browser
    browser = PageFileBrowser(pages_directory)
    browser.load_all_page_files()
    
    if not browser.loaded_sites:
        print("❌ No .page files loaded. Cannot start browser.")
        print("💡 Make sure you run downloader.py first to download some websites!")
        print("💡 Check that the downloaded_sites folder exists and contains .page files")
        return
    
    # Set up the request handler
    from http.server import HTTPServer
    PageFileRequestHandler.page_browser = browser
    
    # Change to script directory to avoid serving system files
    os.chdir(script_dir)
    
    # Start the server
    server = HTTPServer(('localhost', port), PageFileRequestHandler)
    
    print(f"🌐 Starting offline browser on http://localhost:{port}")
    print("📂 Serving from your downloaded sites, not system files!")
    print("🛑 Press Ctrl+C to stop the server")
    
    # Open browser automatically
    webbrowser.open(f'http://localhost:{port}')
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
        server.shutdown()

if __name__ == "__main__":
    start_browser()
