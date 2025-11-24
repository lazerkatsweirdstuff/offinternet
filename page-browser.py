import os
import zipfile
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
from urllib.parse import urlparse, unquote
import tempfile
import base64
import hashlib

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
                pages = list(site_data['pages'].
