import os
import zipfile
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser
from urllib.parse import urlparse, unquote, urljoin
import tempfile
import base64
import hashlib
import re  # Added missing import
from bs4 import BeautifulSoup  # Added missing import

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
            
            print(f"🔍 Requested path:
