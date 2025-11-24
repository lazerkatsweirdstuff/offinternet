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
                
                # Read videos
                videos = {}
                for file_info in zipf.filelist:
                    if file_info.filename.startswith('videos/') and file_info.filename.endswith('.mp4'):
                        video_id = os.path.basename(file_info.filename).replace('.mp4', '')
                        video_content = zipf.read(file_info.filename)
                        
                        # Find corresponding metadata
                        meta_filename = f"videos/{video_id}_meta.json"
                        if meta_filename in zipf.namelist():
                            meta_str = zipf.read(meta_filename).decode('utf-8')
                            video_meta = json.loads(meta_str)
                        else:
                            video_meta = {}
                        
                        videos[video_id] = {
                            'video_file': {
                                'filename': file_info.filename,
                                'content': video_content,
                                'size': len(video_content),
                                'mime_type': 'video/mp4'
                            },
                            'original_url': video_meta.get('original_url', ''),
                            'timestamp': video_meta.get('timestamp', 0),
                            'info': video_meta.get('info', {}),
                            'thumbnail': video_meta.get('thumbnail')
                        }
                
                site_data = {
                    'metadata': metadata,
                    'pages': pages,
                    'videos': videos
                }
                
                domain = metadata['main_url']
                self.loaded_sites[domain] = site_data
                print(f"✅ Loaded site: {domain} with {len(pages)} pages and {len(videos)} videos")
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
        for site_data in self.loaded_sites.values():
            if url in site_data['pages']:
                return site_data['pages'][url]
        
        # Try to find by domain or path
        for site_data in self.loaded_sites.values():
            for page_url, page_data in site_data['pages'].items():
                if url in page_url or page_url.endswith(url):
                    return page_data
        
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
            
            # Handle video serving
            if path.startswith('/video/'):
                self.serve_video(path)
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
                .video-badge { background: #ff4444; color: white; padding: 2px 6px; border-radius: 10px; font-size: 12px; margin-left: 8px; }
                .scratch-badge { background: #4A90E2; color: white; padding: 2px 6px; border-radius: 10px; font-size: 12px; margin-left: 8px; }
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
                is_youtube = metadata.get('is_youtube', False)
                is_scratch = metadata.get('is_scratch', False)
                
                html += f"""
                <div class="site">
                    <h2>
                        <a href="/page/{domain}">{domain}</a>
                        {('<span class="video-badge">🎥 YouTube</span>' if is_youtube else '')}
                        {('<span class="scratch-badge">🎮 Scratch</span>' if is_scratch else '')}
                    </h2>
                    <div class="pages">
                        <strong>Pages ({len(site_data['pages'])}):</strong>
                        <ul>
                """
                
                for page_url in list(site_data['pages'].keys())[:10]:  # Show first 10 pages
                    page_name = page_url.split('/')[-1] or 'index'
                    html += f'<li><a href="/page/{page_url}">{page_name}</a></li>'
                
                if len(site_data['pages']) > 10:
                    html += f'<li>... and {len(site_data["pages"]) - 10} more pages</li>'
                
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
        
        if not page_data:
            # Try with http prefix
            if not requested_url.startswith('http'):
                page_data = self.page_browser.find_page_by_url('http://' + requested_url)
                if not page_data:
                    page_data = self.page_browser.find_page_by_url('https://' + requested_url)
        
        if page_data:
            self.send_response(200)
            self.send_header('Content-type', page_data.get('content_type', 'text/html'))
            self.end_headers()
            self.wfile.write(page_data['content'].encode('utf-8'))
            print(f"✅ Served page: {requested_url}")
        else:
            print(f"❌ Page not found: {requested_url}")
            self.send_error(404, f"Page not found: {requested_url}")
    
    def serve_video(self, path):
        """Serve video files from .page files"""
        try:
            # Extract video ID from path: /video/VIDEO_ID
            video_id = path[7:]  # Remove '/video/' prefix
            
            if not video_id:
                self.send_error(404, "Video ID not specified")
                return
            
            print(f"🔍 Looking for video: {video_id}")
            
            # Find video in loaded sites
            video_data = None
            
            for site_data in self.page_browser.loaded_sites.values():
                videos = site_data.get('videos', {})
                if video_id in videos:
                    video_data = videos[video_id]
                    break
            
            if not video_data or not video_data.get('video_file'):
                print(f"❌ Video not found: {video_id}")
                self.send_error(404, f"Video not found: {video_id}")
                return
            
            video_info = video_data['video_file']
            
            # Send video file with proper headers
            self.send_response(200)
            self.send_header('Content-type', 'video/mp4')
            self.send_header('Content-Length', str(len(video_info['content'])))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            # Send binary video content
            self.wfile.write(video_info['content'])
            print(f"✅ Served video: {video_id} ({len(video_info['content'])} bytes)")
            
        except Exception as e:
            print(f"❌ Error serving video: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Video serving error: {str(e)}")

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
