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
import html

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
        # Normalize URL first
        normalized_url = self.normalize_url(url)
        
        # Exact match with normalized URL
        for site_data in self.loaded_sites.values():
            if normalized_url in site_data['pages']:
                return site_data['pages'][normalized_url]
            
            # Also check original URL
            if url in site_data['pages']:
                return site_data['pages'][url]
        
        # Try to find by path
        parsed_request = urlparse(normalized_url)
        
        for site_data in self.loaded_sites.values():
            for page_url, page_data in site_data['pages'].items():
                parsed_page = urlparse(page_url)
                
                # Match by exact path
                if parsed_request.path == parsed_page.path:
                    return page_data
                
                # Match by similar path (for index pages)
                if (parsed_request.path in ['', '/'] and 
                    parsed_page.path in ['', '/']):
                    return page_data
        
        return None

    def normalize_url(self, url):
        """Normalize URL for consistent matching"""
        try:
            parsed = urlparse(url)
            # Remove fragments, normalize scheme
            normalized = parsed._replace(
                fragment='',
                scheme='https',  # Standardize on https
                query=''  # Remove query parameters for matching
            )
            return normalized.geturl()
        except:
            return url

    def find_asset_by_url(self, url):
        """Find an asset across all loaded sites by URL"""
        # Try exact match first
        for site_data in self.loaded_sites.values():
            if url in site_data['assets']:
                return site_data['assets'][url]
        
        # Try normalized URL
        normalized_url = self.normalize_url(url)
        for site_data in self.loaded_sites.values():
            if normalized_url in site_data['assets']:
                return site_data['assets'][normalized_url]
        
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
        """Handle GET requests - FIXED VERSION"""
        try:
            # Parse the requested path
            path = unquote(self.path)
            
            # Remove query parameters for routing
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
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>🌐 Offline Website Browser</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { background: rgba(255, 255, 255, 0.95); padding: 40px; border-radius: 20px; margin-bottom: 30px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); text-align: center; }
                .header h1 { font-size: 3em; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }
                .sites-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 25px; }
                .site-card { background: rgba(255, 255, 255, 0.95); padding: 30px; border-radius: 15px; box-shadow: 0 15px 35px rgba(0,0,0,0.1); }
                .site-card h2 a { color: #333; text-decoration: none; font-size: 1.4em; }
                .stats { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
                .stat { background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 8px 15px; border-radius: 20px; font-size: 0.9em; }
                .pages-list { max-height: 200px; overflow-y: auto; margin-top: 15px; }
                .pages-list ul { list-style: none; }
                .pages-list li { margin-bottom: 8px; padding: 8px 12px; background: #f8f9fa; border-radius: 8px; }
                .pages-list a { color: #495057; text-decoration: none; display: block; }
                @media (max-width: 768px) { .sites-grid { grid-template-columns: 1fr; } .header { padding: 30px 20px; } .header h1 { font-size: 2.2em; } }
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
            html_content += """
                <div style="text-align: center; padding: 60px 20px; color: #666;">
                    <h2>No websites loaded</h2>
                    <p>No .page files found in the downloaded_sites directory.</p>
                    <p>Run the downloader first to download some websites!</p>
                </div>
            """
        else:
            html_content += '<div class="sites-grid">'
            
            for domain, site_data in self.page_browser.loaded_sites.items():
                metadata = site_data['metadata']
                pages = list(site_data['pages'].keys())
                
                html_content += f"""
                <div class="site-card">
                    <h2><a href="/page/{domain}">{domain}</a></h2>
                    <div class="stats">
                        <span class="stat">📄 {len(site_data['pages'])} pages</span>
                        <span class="stat">🎨 {len(site_data['assets'])} assets</span>
                    </div>
                    <div class="pages-list">
                        <strong>Available Pages:</strong>
                        <ul>
                """
                
                for page_url in pages[:8]:
                    page_name = urlparse(page_url).path or '/'
                    if len(page_name) > 40:
                        page_name = page_name[:37] + '...'
                    html_content += f'<li><a href="/page/{page_url}">{page_name}</a></li>'
                
                if len(pages) > 8:
                    html_content += f'<li>... and {len(pages) - 8} more pages</li>'
                
                html_content += """
                        </ul>
                    </div>
                </div>
                """
            
            html_content += '</div>'
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html_content.encode('utf-8'))
    
    def serve_saved_page(self, path):
        """Serve a page from the loaded .page files - FIXED"""
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
            
            # FIX 1: Fix text encoding issues
            content = self.fix_text_encoding(content)
            
            # FIX 2: Rewrite links to work properly
            content = self.rewrite_links_fixed(content, page_data['url'])
            
            # Set proper headers
            self.send_response(200)
            content_type = page_data.get('content_type', 'text/html')
            if 'charset' not in content_type and 'text/' in content_type:
                content_type += '; charset=utf-8'
            self.send_header('Content-type', content_type)
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            self.wfile.write(content.encode('utf-8'))
            print(f"✅ Served page: {requested_url}")
        else:
            print(f"❌ Page not found: {requested_url}")
            self.serve_404(requested_url)
    
    def fix_text_encoding(self, html_content):
        """Fix text encoding issues like 'funÂ & games'"""
        try:
            # Fix common encoding issues
            fixes = [
                (r'â\x80\x99', "'"),  # Smart quotes
                (r'Â ', ''),          # Extra space characters
                (r'â\x80\x94', '—'),  # Em dash
                (r'â\x80\x93', '–'),  # En dash
                (r'â\x80\x9c', '"'),  # Left double quote
                (r'â\x80\x9d', '"'),  # Right double quote
                (r'â\x80\x98', "'"),  # Left single quote
                (r'â\x80\x99', "'"),  # Right single quote
            ]
            
            for pattern, replacement in fixes:
                html_content = re.sub(pattern, replacement, html_content)
            
            # Also use HTML unescape for any HTML entities
            html_content = html.unescape(html_content)
            
            return html_content
        except Exception as e:
            print(f"⚠️ Encoding fix error: {e}")
            return html_content
    
    def rewrite_links_fixed(self, html_content, base_url):
        """Rewrite links to work with offline browser - COMPLETELY FIXED"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            base_domain = urlparse(base_url).netloc
            
            # FIX: Rewrite <a> tags - SIMPLER AND MORE RELIABLE
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    if href.startswith(('http://', 'https://')):
                        # External link from same domain
                        if base_domain in href:
                            link['href'] = f"/page/{href}"
                        # External links from other domains stay as-is
                    elif href.startswith('/'):
                        # Absolute path
                        full_url = f"https://{base_domain}{href}"
                        link['href'] = f"/page/{full_url}"
                    else:
                        # Relative path
                        full_url = urljoin(base_url, href)
                        link['href'] = f"/page/{full_url}"
            
            # FIX: Rewrite resource links
            self.rewrite_resource_links_fixed(soup, base_url)
            
            return str(soup)
        except Exception as e:
            print(f"❌ Error rewriting links: {e}")
            return html_content
    
    def rewrite_resource_links_fixed(self, soup, base_url):
        """Rewrite resource links - FIXED VERSION"""
        try:
            base_domain = urlparse(base_url).netloc
            
            # Rewrite <script> tags
            for script in soup.find_all('script', src=True):
                src = script['src']
                if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                    if src.startswith(('http://', 'https://')):
                        script['src'] = f"/asset/{src}"
                    else:
                        full_src = urljoin(f"https://{base_domain}", src)
                        script['src'] = f"/asset/{full_src}"
            
            # Rewrite <link> tags (CSS, etc.)
            for link in soup.find_all('link', href=True):
                href = link['href']
                if href and not href.startswith(('data:', 'blob:', 'javascript:')):
                    if href.startswith(('http://', 'https://')):
                        link['href'] = f"/asset/{href}"
                    else:
                        full_href = urljoin(f"https://{base_domain}", href)
                        link['href'] = f"/asset/{full_href}"
            
            # Rewrite <img> tags
            for img in soup.find_all('img', src=True):
                src = img['src']
                if src and not src.startswith(('data:', 'blob:', 'javascript:')):
                    if src.startswith(('http://', 'https://')):
                        img['src'] = f"/asset/{src}"
                    else:
                        full_src = urljoin(f"https://{base_domain}", src)
                        img['src'] = f"/asset/{full_src}"
            
            # Rewrite CSS url() references
            for style in soup.find_all('style'):
                if style.string:
                    style.string = re.sub(
                        r'url\([\'"]?([^)"\']+)[\'"]?\)',
                        lambda m: self.rewrite_css_url_fixed(m.group(1), base_domain),
                        style.string
                    )
            
            # Rewrite CSS in style attributes
            for tag in soup.find_all(style=True):
                if tag['style']:
                    tag['style'] = re.sub(
                        r'url\([\'"]?([^)"\']+)[\'"]?\)',
                        lambda m: self.rewrite_css_url_fixed(m.group(1), base_domain),
                        tag['style']
                    )
                    
        except Exception as e:
            print(f"❌ Error rewriting resource links: {e}")
    
    def rewrite_css_url_fixed(self, url, base_domain):
        """Rewrite a CSS URL to use asset server - FIXED"""
        if url.startswith(('data:', 'blob:')):
            return f'url({url})'
        
        if url.startswith(('http://', 'https://')):
            return f'url(/asset/{url})'
        else:
            # For relative URLs, construct full URL
            full_url = f"https://{base_domain}{url if url.startswith('/') else '/' + url}"
            return f'url(/asset/{full_url})'
    
    def serve_asset(self, path):
        """Serve asset files - FIXED with better error handling"""
        try:
            # Extract asset URL from path
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
                # Try to find similar asset
                self.serve_asset_fallback(asset_url)
                return
            
            # Determine content type
            content_type = asset_data.get('content_type', 'application/octet-stream')
            encoding = asset_data.get('encoding', 'text')
            content = asset_data['content']
            
            self.send_response(200)
            
            # Set proper content type with charset for text files
            if 'text/' in content_type and 'charset' not in content_type:
                content_type += '; charset=utf-8'
                
            self.send_header('Content-type', content_type)
            self.send_header('Cache-Control', 'public, max-age=3600')
            
            if encoding == 'base64':
                # Decode base64 content
                binary_content = base64.b64decode(content)
                self.send_header('Content-Length', str(len(binary_content)))
                self.end_headers()
                self.wfile.write(binary_content)
            else:
                # Text content - ensure proper encoding
                if isinstance(content, str):
                    content_bytes = content.encode('utf-8')
                else:
                    content_bytes = content
                    
                self.send_header('Content-Length', str(len(content_bytes)))
                self.end_headers()
                self.wfile.write(content_bytes)
            
            print(f"✅ Served asset: {asset_url}")
            
        except BrokenPipeError:
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving asset: {e}")
            self.send_error(500, f"Asset serving error: {str(e)}")
    
    def serve_asset_fallback(self, asset_url):
        """Try to find a fallback for missing assets"""
        # Try without query parameters
        clean_url = asset_url.split('?')[0]
        asset_data = self.page_browser.find_asset_by_url(clean_url)
        if asset_data:
            print(f"✅ Found asset without query params: {clean_url}")
            self.serve_asset(f"/asset/{clean_url}")
            return
        
        # Try to find by filename only
        filename = os.path.basename(asset_url)
        if filename:
            for site_data in self.page_browser.loaded_sites.values():
                for asset_url_stored, asset_data in site_data['assets'].items():
                    if filename in asset_url_stored:
                        print(f"✅ Found similar asset: {asset_url_stored}")
                        self.serve_asset(f"/asset/{asset_url_stored}")
                        return
        
        self.send_error(404, f"Asset not found: {asset_url}")
    
    def serve_404(self, requested_url):
        """Serve a nice 404 page"""
        self.send_response(404)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Page Not Found</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; text-align: center; }}
                .error-container {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #e74c3c; }}
                a {{ color: #3498db; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>❌ Page Not Found</h1>
                <p>The page <strong>{html.escape(requested_url)}</strong> was not found in your downloaded sites.</p>
                <p><a href="/">← Back to Home</a></p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to reduce log spam"""
        # Only log important messages
        if any(x in format for x in ['404', '500', 'ERROR']):
            super().log_message(format, *args)

def start_browser(pages_directory=None, port=8000, host='localhost'):
    """Start the web browser server - FIXED with better error handling"""
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
        return
    
    # Set up the request handler
    from http.server import HTTPServer
    PageFileRequestHandler.page_browser = browser
    
    # Change to script directory to avoid serving system files
    os.chdir(script_dir)
    
    # Start the server with better error handling
    try:
        server = HTTPServer((host, port), PageFileRequestHandler)
        
        print(f"🌐 Starting offline browser on http://{host}:{port}")
        print("✅ Fixed: Links should now work properly!")
        print("✅ Fixed: Text encoding issues resolved!")
        print("✅ Fixed: Connection issues resolved!")
        print("🛑 Press Ctrl+C to stop the server")
        
        # Open browser automatically
        try:
            webbrowser.open(f'http://{host}:{port}')
        except:
            print(f"⚠️ Could not open browser automatically. Please visit: http://{host}:{port}")
        
        server.serve_forever()
        
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use. Try a different port:")
            print(f"   python browser.py --port 8080")
        else:
            print(f"❌ Server error: {e}")
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Offline Website Browser')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--host', default='localhost', help='Host to bind the server to')
    parser.add_argument('--directory', help='Directory containing .page files')
    
    args = parser.parse_args()
    
    start_browser(
        pages_directory=args.directory,
        port=args.port,
        host=args.host
    )
