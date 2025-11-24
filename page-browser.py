import os
import zipfile
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
from urllib.parse import urlparse, unquote, urljoin
import base64
import hashlib
import re
from bs4 import BeautifulSoup

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
                # Match by exact path
                parsed_request = urlparse(url)
                parsed_page = urlparse(page_url)
                
                if parsed_request.path and parsed_request.path == parsed_page.path:
                    return page_data
                
                # Match domain and similar path
                if (parsed_request.netloc == parsed_page.netloc and 
                    parsed_request.path in parsed_page.path):
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
        
        # Try by filename
        requested_filename = os.path.basename(urlparse(url).path)
        if requested_filename:
            for site_data in self.loaded_sites.values():
                for asset_url, asset_data in site_data['assets'].items():
                    asset_filename = os.path.basename(urlparse(asset_url).path)
                    if asset_filename == requested_filename:
                        return asset_data
        
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
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>🌐 Offline Website Browser</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    padding: 20px;
                }
                
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                
                .header {
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    padding: 40px;
                    border-radius: 20px;
                    margin-bottom: 30px;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    text-align: center;
                }
                
                .header h1 {
                    font-size: 3em;
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    margin-bottom: 10px;
                }
                
                .header p {
                    color: #666;
                    font-size: 1.2em;
                }
                
                .sites-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                    gap: 25px;
                }
                
                .site-card {
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    padding: 30px;
                    border-radius: 15px;
                    box-shadow: 0 15px 35px rgba(0,0,0,0.1);
                    transition: transform 0.3s ease, box-shadow 0.3s ease;
                }
                
                .site-card:hover {
                    transform: translateY(-5px);
                    box-shadow: 0 25px 50px rgba(0,0,0,0.15);
                }
                
                .site-card h2 {
                    margin-bottom: 15px;
                }
                
                .site-card h2 a {
                    color: #333;
                    text-decoration: none;
                    font-size: 1.4em;
                    transition: color 0.3s ease;
                }
                
                .site-card h2 a:hover {
                    color: #667eea;
                }
                
                .stats {
                    display: flex;
                    gap: 15px;
                    margin-bottom: 20px;
                    flex-wrap: wrap;
                }
                
                .stat {
                    background: linear-gradient(135deg, #667eea, #764ba2);
                    color: white;
                    padding: 8px 15px;
                    border-radius: 20px;
                    font-size: 0.9em;
                    font-weight: 500;
                }
                
                .pages-list {
                    max-height: 200px;
                    overflow-y: auto;
                    margin-top: 15px;
                }
                
                .pages-list ul {
                    list-style: none;
                }
                
                .pages-list li {
                    margin-bottom: 8px;
                    padding: 8px 12px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    transition: background 0.3s ease;
                }
                
                .pages-list li:hover {
                    background: #e9ecef;
                }
                
                .pages-list a {
                    color: #495057;
                    text-decoration: none;
                    display: block;
                }
                
                .pages-list a:hover {
                    color: #667eea;
                }
                
                .empty-state {
                    text-align: center;
                    padding: 60px 20px;
                    color: #666;
                }
                
                .empty-state h2 {
                    margin-bottom: 15px;
                    color: #333;
                }
                
                /* Custom scrollbar */
                .pages-list::-webkit-scrollbar {
                    width: 6px;
                }
                
                .pages-list::-webkit-scrollbar-track {
                    background: #f1f1f1;
                    border-radius: 3px;
                }
                
                .pages-list::-webkit-scrollbar-thumb {
                    background: #667eea;
                    border-radius: 3px;
                }
                
                .pages-list::-webkit-scrollbar-thumb:hover {
                    background: #764ba2;
                }
                
                @media (max-width: 768px) {
                    .sites-grid {
                        grid-template-columns: 1fr;
                    }
                    
                    .header {
                        padding: 30px 20px;
                    }
                    
                    .header h1 {
                        font-size: 2.2em;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🌐 Offline Website Browser</h1>
                    <p>Browse your downloaded websites offline</p>
                </div>
        """
        
        if not self.page_browser.loaded_sites:
            html += """
                <div class="empty-state">
                    <h2>No websites loaded</h2>
                    <p>No .page files found in the downloaded_sites directory.</p>
                    <p>Run the downloader first to download some websites!</p>
                </div>
            """
        else:
            html += '<div class="sites-grid">'
            
            for domain, site_data in self.page_browser.loaded_sites.items():
                metadata = site_data['metadata']
                pages = list(site_data['pages'].keys())
                
                html += f"""
                <div class="site-card">
                    <h2><a href="/page/{domain}">{domain}</a></h2>
                    <div class="stats">
                        <span class="stat">📄 {len(site_data['pages'])} pages</span>
                        <span class="stat">🎨 {len(site_data['assets'])} assets</span>
                        <span class="stat">💾 {metadata.get('total_size', 0) // 1024} KB</span>
                    </div>
                    <div class="pages-list">
                        <strong>Available Pages:</strong>
                        <ul>
                """
                
                # Show main pages
                for page_url in pages[:8]:  # Show first 8 pages
                    page_name = urlparse(page_url).path or '/'
                    if len(page_name) > 40:
                        page_name = page_name[:37] + '...'
                    html += f'<li><a href="/page/{page_url}">{page_name}</a></li>'
                
                if len(pages) > 8:
                    html += f'<li>... and {len(pages) - 8} more pages</li>'
                
                html += """
                        </ul>
                    </div>
                </div>
                """
            
            html += '</div>'
        
        html += """
            </div>
        </body>
        </html>
        """
        
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
            # Try to serve a nice 404 page
            self.serve_404(requested_url)
    
    def serve_404(self, requested_url):
        """Serve a nice 404 page"""
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page Not Found</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    margin: 40px; 
                    background: #f5f5f5;
                    text-align: center;
                }}
                .error-container {{
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{ color: #e74c3c; }}
                a {{ color: #3498db; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>❌ Page Not Found</h1>
                <p>The page <strong>{requested_url}</strong> was not found in your downloaded sites.</p>
                <p><a href="/">← Back to Home</a></p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))
    
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
            self.send_header('Cache-Control', 'public, max-age=3600')  # Cache for 1 hour
            
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
        soup = BeautifulSoup(html, 'html.parser')
        base_domain = urlparse(base_url).netloc
        
        # Rewrite <a> tags
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith(('http://', 'https://')):
                # External link - keep as is or make it open in offline browser
                if base_domain in href:
                    # Convert to our internal routing
                    link['href'] = f"/page/{href}"
                # Otherwise leave external links as-is
            elif href.startswith('/'):
                # Absolute path - convert to full URL then to our routing
                full_url = f"{urlparse(base_url).scheme}://{base_domain}{href}"
                link['href'] = f"/page/{full_url}"
            elif href.startswith('#') or href.startswith('javascript:'):
                # Anchors and JS links - leave as is
                pass
            elif not href.startswith(('mailto:', 'tel:')):
                # Relative path
                full_url = urljoin(base_url, href)
                link['href'] = f"/page/{full_url}"
        
        # Rewrite resource links to use our asset server
        self.rewrite_resource_links(soup, base_url)
        
        return str(soup)
    
    def rewrite_resource_links(self, soup, base_url):
        """Rewrite resource links (CSS, JS, images) to use asset server"""
        # Rewrite <script> tags
        for script in soup.find_all('script', src=True):
            src = script['src']
            if src and not src.startswith(('data:', 'blob:')):
                if src.startswith(('http://', 'https://')):
                    script['src'] = f"/asset/{src}"
                else:
                    full_src = urljoin(base_url, src)
                    script['src'] = f"/asset/{full_src}"
        
        # Rewrite <link> tags (CSS, etc.)
        for link in soup.find_all('link', href=True):
            href = link['href']
            if href and not href.startswith(('data:', 'blob:')):
                if href.startswith(('http://', 'https://')):
                    link['href'] = f"/asset/{href}"
                else:
                    full_href = urljoin(base_url, href)
                    link['href'] = f"/asset/{full_href}"
        
        # Rewrite <img> tags
        for img in soup.find_all('img', src=True):
            src = img['src']
            if src and not src.startswith(('data:', 'blob:')):
                if src.startswith(('http://', 'https://')):
                    img['src'] = f"/asset/{src}"
                else:
                    full_src = urljoin(base_url, src)
                    img['src'] = f"/asset/{full_src}"
        
        # Rewrite CSS url() references in style tags
        for style in soup.find_all('style'):
            if style.string:
                style.string = re.sub(
                    r'url\([\'"]?([^)\'"]+)[\'"]?\)',
                    lambda m: self.rewrite_css_url(m.group(1), base_url),
                    style.string
                )
        
        # Rewrite CSS in style attributes
        for tag in soup.find_all(style=True):
            if tag['style']:
                tag['style'] = re.sub(
                    r'url\([\'"]?([^)\'"]+)[\'"]?\)',
                    lambda m: self.rewrite_css_url(m.group(1), base_url),
                    tag['style']
                )
    
    def rewrite_css_url(self, url, base_url):
        """Rewrite a CSS URL to use asset server"""
        if url.startswith(('data:', 'blob:')):
            return f'url({url})'
        
        if url.startswith(('http://', 'https://')):
            return f'url(/asset/{url})'
        else:
            full_url = urljoin(base_url, url)
            return f'url(/asset/{full_url})'

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
    print("🎨 Beautiful UI with working links!")
    print("📂 Serving from your downloaded sites")
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
