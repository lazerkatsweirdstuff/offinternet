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
import tempfile
import shutil
import signal
import sys
import socket
import threading

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
        self.youtube_videos = []
        
        # Create temp directory for extracted videos when browser runs
        self.temp_dir = tempfile.mkdtemp(prefix="youtube_browser_")
        print(f"📁 Temp directory for videos: {self.temp_dir}")
        
        # Check if directory exists
        if not os.path.exists(self.pages_directory):
            print(f"❌ ERROR: Directory not found: {self.pages_directory}")
            print("Please run the downloader first or specify the correct path.")
            return
        
    def __del__(self):
        """Clean up temp directory when browser is destroyed"""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"🧹 Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                print(f"⚠️ Could not clean up temp directory: {e}")
    
    def extract_video_from_page(self, page_path, video_id):
        """Extract video from .page file to temp directory"""
        try:
            # Create video path in temp directory
            video_temp_path = os.path.join(self.temp_dir, f"{video_id}.mp4")
            
            # Check if already extracted
            if os.path.exists(video_temp_path):
                return video_temp_path
            
            # Extract from .page file
            with zipfile.ZipFile(page_path, 'r') as zipf:
                # Look for video file in the archive
                video_found = False
                for file_info in zipf.filelist:
                    if file_info.filename == 'video.mp4' or file_info.filename.endswith('.mp4'):
                        # Extract video to temp directory
                        with zipf.open(file_info.filename) as video_file:
                            with open(video_temp_path, 'wb') as f:
                                f.write(video_file.read())
                        video_found = True
                        print(f"🎬 Extracted video to temp: {video_temp_path}")
                        break
                
                if not video_found:
                    print(f"❌ No video found in .page file: {page_path}")
                    return None
            
            return video_temp_path
            
        except Exception as e:
            print(f"❌ Error extracting video from {page_path}: {e}")
            return None
    
    def load_page_file(self, filepath):
        """Load a .page file into memory and extract videos to temp"""
        try:
            with zipfile.ZipFile(filepath, 'r') as zipf:
                # Read metadata
                if 'metadata.json' in zipf.namelist():
                    metadata_str = zipf.read('metadata.json').decode('utf-8')
                    metadata = json.loads(metadata_str)
                    
                    # Check if it's a YouTube video
                    if metadata.get('type') == 'youtube_video':
                        video_id = metadata.get('video_id', 'unknown')
                        video_title = metadata.get('title', 'Unknown Title')
                        
                        # Extract video to temp directory
                        video_temp_path = self.extract_video_from_page(filepath, video_id)
                        if not video_temp_path:
                            print(f"⚠️ Could not extract video: {video_id}")
                            return None
                        
                        # Read HTML and modify it to use temp video
                        if 'index.html' in zipf.namelist():
                            html_content = zipf.read('index.html').decode('utf-8')
                            
                            # Modify HTML to use relative video path
                            html_content = html_content.replace('src="video.mp4"', f'src="/temp_videos/{video_id}.mp4"')
                            
                            # Create page data structure
                            page_data = {
                                'url': metadata.get('original_url', f"youtube_video_{video_id}"),
                                'content': html_content,
                                'content_type': 'text/html',
                                'status_code': 200,
                                'downloaded_with': 'youtube_downloader',
                                'video_id': video_id,
                                'temp_video_path': video_temp_path,
                                'page_file': filepath
                            }
                            
                            # Create site data structure
                            domain = f"youtube_{video_id}"
                            site_data = {
                                'metadata': metadata,
                                'pages': {domain: page_data},
                                'assets': {},
                                'is_youtube': True,
                                'video_temp_path': video_temp_path
                            }
                            
                            self.loaded_sites[domain] = site_data
                            
                            # Add to YouTube videos list
                            self.youtube_videos.append({
                                'video_id': video_id,
                                'title': video_title,
                                'channel': metadata.get('channel', 'Unknown Channel'),
                                'domain': domain,
                                'filepath': filepath,
                                'temp_video_path': video_temp_path
                            })
                            
                            print(f"✅ Loaded YouTube video: {video_title}")
                            return site_data
                    else:
                        # Regular website - load pages and assets
                        pages = {}
                        assets = {}
                        
                        # Read pages
                        for file_info in zipf.filelist:
                            if file_info.filename.startswith('pages/') and file_info.filename.endswith('.json'):
                                page_data_str = zipf.read(file_info.filename).decode('utf-8')
                                page_data = json.loads(page_data_str)
                                pages[page_data['url']] = page_data
                        
                        # Read assets
                        for file_info in zipf.filelist:
                            if file_info.filename.startswith('assets/') and file_info.filename.endswith('.json'):
                                asset_data_str = zipf.read(file_info.filename).decode('utf-8')
                                asset_data = json.loads(asset_data_str)
                                assets[asset_data['url']] = asset_data
                        
                        site_data = {
                            'metadata': metadata,
                            'pages': pages,
                            'assets': assets,
                            'is_youtube': False
                        }
                        
                        domain = metadata.get('main_url', 'unknown_site')
                        self.loaded_sites[domain] = site_data
                        print(f"✅ Loaded site: {domain} with {len(pages)} pages")
                        return site_data
                
        except Exception as e:
            print(f"❌ Error loading {filepath}: {e}")
            return None
    
    def load_all_page_files(self):
        """Load all .page files from the directory and subdirectories"""
        if not os.path.exists(self.pages_directory):
            print(f"❌ Directory {self.pages_directory} does not exist")
            return
        
        # Look for .page files in main directory and subdirectories
        page_files = []
        for root, dirs, files in os.walk(self.pages_directory):
            for file in files:
                if file.endswith('.page'):
                    page_files.append(os.path.join(root, file))
        
        print(f"📄 Found {len(page_files)} .page files:")
        for filepath in page_files:
            relative_path = os.path.relpath(filepath, self.pages_directory)
            print(f"  • Loading: {relative_path}")
            self.load_page_file(filepath)
        
        # Print summary
        regular_sites = sum(1 for s in self.loaded_sites.values() if not s.get('is_youtube', False))
        youtube_videos = len(self.youtube_videos)
        
        print(f"✅ Total sites loaded: {regular_sites} regular sites")
        print(f"✅ YouTube videos loaded: {youtube_videos}")
    
    def find_page_by_url(self, url):
        """Find a page across all loaded sites by URL"""
        # Check for YouTube video requests
        if url.startswith('youtube_'):
            for domain, site_data in self.loaded_sites.items():
                if domain == url:
                    return next(iter(site_data['pages'].values()))
        
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

                # Match by exact path
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
    
    def find_asset_by_relative_path(self, path):
        """Find an asset by relative path (e.g., /w/assets/latest/font.woff2)"""
        # Remove leading slash if present
        if path.startswith('/'):
            path = path[1:]
        
        # Try to find asset by matching the end of the URL
        for site_data in self.loaded_sites.values():
            for asset_url, asset_data in site_data['assets'].items():
                parsed = urlparse(asset_url)
                asset_path = parsed.path
                if asset_path.startswith('/'):
                    asset_path = asset_path[1:]
                
                # Check if the path ends with our requested path
                if asset_url.endswith(path) or asset_path == path:
                    return asset_data
        
        return None

class RobustPageFileRequestHandler(SimpleHTTPRequestHandler):
    page_browser = None
    
    def handle_one_request(self):
        """Override to catch connection errors"""
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError) as e:
            # Client disconnected, ignore
            print(f"⚠️ Client disconnected: {e}")
        except Exception as e:
            print(f"⚠️ Unexpected error in request handler: {e}")
            import traceback
            traceback.print_exc()
    
    def do_GET(self):
        """Handle GET requests with robust error handling and better routing"""
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
            
            # Handle temp video files
            if path.startswith('/temp_videos/'):
                self.serve_temp_video(path)
                return
            
            # Handle YouTube video requests
            if path.startswith('/youtube/'):
                self.serve_youtube_video(path)
                return
            
            # Handle asset requests - two formats
            if path.startswith('/asset/'):
                self.serve_encoded_asset(path)
                return
            
            # Check if it looks like a direct asset request (e.g., /w/assets/latest/font.woff2)
            if self.looks_like_asset(path):
                self.serve_direct_asset(path)
                return
            
            # Handle requests for specific pages
            if path.startswith('/page/'):
                self.serve_saved_page(path)
                return
            
            # Default to trying to find a matching page
            self.serve_saved_page(f'/page{path}')
            
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError) as e:
            # Client disconnected, ignore
            print(f"⚠️ Client disconnected during request: {e}")
        except Exception as e:
            print(f"❌ Server error in do_GET: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.send_error(500, f"Server error: {str(e)}")
            except:
                pass  # Client may have disconnected
    
    def looks_like_asset(self, path):
        """Check if a path looks like an asset request"""
        # Common asset file extensions
        asset_extensions = [
            '.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
            '.woff', '.woff2', '.ttf', '.eot', '.otf', '.webp', '.mp4', '.webm',
            '.mp3', '.wav', '.ogg', '.json', '.xml', '.pdf', '.zip'
        ]
        
        # Check if path has an asset extension
        if any(path.lower().endswith(ext) for ext in asset_extensions):
            return True
        
        # Check common asset paths
        asset_paths = [
            '/assets/', '/static/', '/css/', '/js/', '/images/', '/img/',
            '/fonts/', '/font/', '/media/', '/uploads/', '/w/assets/'
        ]
        
        if any(path.startswith(ap) for ap in asset_paths):
            return True
        
        return False
    
    def serve_direct_asset(self, path):
        """Serve an asset using its direct path (e.g., /w/assets/latest/font.woff2)"""
        try:
            print(f"🔍 Looking for direct asset: {path}")
            
            # Try to find asset by relative path
            asset_data = self.page_browser.find_asset_by_relative_path(path)
            
            if not asset_data:
                # Try to construct a full URL and look for it
                # Common pattern: if we're on discord.com page, try discord.com + path
                referer = self.headers.get('Referer', '')
                if referer:
                    # Extract domain from referer
                    parsed_referer = urlparse(referer)
                    if parsed_referer.netloc:
                        # Construct full URL
                        full_url = f"{parsed_referer.scheme}://{parsed_referer.netloc}{path}"
                        print(f"🔍 Trying constructed URL: {full_url}")
                        asset_data = self.page_browser.find_asset_by_url(full_url)
            
            if not asset_data:
                print(f"❌ Asset not found: {path}")
                self.send_error(404, f"Asset not found: {path}")
                return
            
            # Determine content type
            content_type = asset_data.get('content_type', 'application/octet-stream')
            encoding = asset_data.get('encoding', 'text')
            content = asset_data['content']
            
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Cache-Control', 'public, max-age=3600')
            
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
            
            print(f"✅ Served direct asset: {path} ({len(content)} bytes)")
            
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving direct asset: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.send_error(500, f"Asset serving error: {str(e)}")
            except:
                pass
    
    def serve_encoded_asset(self, path):
        """Serve an asset using encoded URL (e.g., /asset/https://example.com/style.css)"""
        try:
            # Extract asset URL from path: /asset/ENCODED_URL
            encoded_url = path[7:]  # Remove '/asset/' prefix
            
            if not encoded_url:
                self.send_error(404, "Asset URL not specified")
                return
            
            # URL decode the asset URL
            asset_url = unquote(encoded_url)
            
            print(f"🔍 Looking for encoded asset: {asset_url}")

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
            self.send_header('Cache-Control', 'public, max-age=3600')
            
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
            
            print(f"✅ Served encoded asset: {asset_url} ({len(content)} bytes)")

        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving encoded asset: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.send_error(500, f"Asset serving error: {str(e)}")
            except:
                pass
    
    def serve_temp_video(self, path):
        """Serve video files from temp directory with robust error handling"""
        try:
            # Extract video filename from path
            video_filename = path.replace('/temp_videos/', '')
            if not video_filename:
                self.send_error(404, "Video not specified")
                return
            
            # Find the video file in temp directories
            video_path = None
            for site_data in self.page_browser.loaded_sites.values():
                if site_data.get('is_youtube', False):
                    temp_path = site_data.get('video_temp_path', '')
                    if os.path.basename(temp_path) == video_filename:
                        video_path = temp_path
                        break
            
            if not video_path or not os.path.exists(video_path):
                print(f"❌ Video not found: {video_filename}")
                self.send_error(404, f"Video not found: {video_filename}")
                return
            
            # Get file size
            file_size = os.path.getsize(video_path)
            
            # Check for Range header (for video seeking)
            range_header = self.headers.get('Range', '')
            range_start = 0
            range_end = file_size - 1
            
            if range_header:
                # Parse Range header
                range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    range_start = int(range_match.group(1))
                    if range_match.group(2):
                        range_end = int(range_match.group(2))
                    else:
                        range_end = file_size - 1
                    
                    # Ensure range is valid
                    if range_start >= file_size:
                        self.send_error(416, 'Requested Range Not Satisfiable')
                        return
                    range_end = min(range_end, file_size - 1)
            
            # Open file for reading
            with open(video_path, 'rb') as f:
                # Handle range request
                if range_header:
                    self.send_response(206)  # Partial Content
                    self.send_header('Content-type', 'video/mp4')
                    self.send_header('Content-Range', f'bytes {range_start}-{range_end}/{file_size}')
                    self.send_header('Content-Length', str(range_end - range_start + 1))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    
                    # Seek to start position
                    f.seek(range_start)
                    
                    # Stream the file in chunks
                    remaining = range_end - range_start + 1
                    chunk_size = 8192
                    
                    while remaining > 0:
                        try:
                            chunk = f.read(min(chunk_size, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
                            # Client disconnected, stop streaming
                            print(f"⚠️ Client disconnected while streaming video")
                            break
                else:
                    # Full file request
                    self.send_response(200)
                    self.send_header('Content-type', 'video/mp4')
                    self.send_header('Content-Length', str(file_size))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    
                    # Stream the file in chunks
                    chunk_size = 8192
                    while True:
                        try:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
                            # Client disconnected, stop streaming
                            print(f"⚠️ Client disconnected while streaming video")
                            break
            
            print(f"✅ Served temp video: {video_filename}")
            
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            print(f"⚠️ Client disconnected during video streaming")
        except Exception as e:
            print(f"❌ Error serving temp video: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.send_error(500, f"Server error: {str(e)}")
            except:
                pass  # Client may have disconnected
    
    def serve_index(self):
        """Serve an index page listing all loaded sites"""
        try:
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
                    
                    .tabs {
                        display: flex;
                        gap: 10px;
                        margin-bottom: 20px;
                        justify-content: center;
                    }
                    
                    .tab-btn {
                        padding: 10px 20px;
                        background: rgba(255, 255, 255, 0.8);
                        border: none;
                        border-radius: 20px;
                        cursor: pointer;
                        font-size: 1em;
                        transition: all 0.3s ease;
                    }
                    
                    .tab-btn.active {
                        background: #4CAF50;
                        color: white;
                    }
                    
                    .tab-btn.youtube {
                        background: rgba(255, 0, 0, 0.1);
                    }
                    
                    .tab-btn.youtube.active {
                        background: #ff0000;
                        color: white;
                    }
                    
                    .tab-content {
                        display: none;
                    }
                    
                    .tab-content.active {
                        display: block;
                    }
                    
                    .sites-grid {
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                        gap: 25px;
                    }
                    
                    .site-card, .video-card {
                        background: rgba(255, 255, 255, 0.95);
                        backdrop-filter: blur(10px);
                        padding: 30px;
                        border-radius: 15px;
                        box-shadow: 0 15px 35px rgba(0,0,0,0.1);
                        transition: transform 0.3s ease, box-shadow 0.3s ease;
                    }
                    
                    .site-card:hover, .video-card:hover {
                        transform: translateY(-5px);
                        box-shadow: 0 25px 50px rgba(0,0,0,0.15);
                    }
                    
                    .site-card h2, .video-card h3 {
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
                    
                    .video-stat {
                        background: linear-gradient(135deg, #ff0000, #cc0000);
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
                    
                    .youtube-btn {
                        background: #ff0000;
                        color: white;
                        padding: 8px 15px;
                        border-radius: 20px;
                        text-decoration: none;
                        display: inline-block;
                        margin-top: 10px;
                    }
                    
                    .btn {
                        background: #4CAF50;
                        color: white;
                        padding: 8px 15px;
                        border-radius: 20px;
                        text-decoration: none;
                        display: inline-block;
                        margin-top: 10px;
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
                        <p>Browse your downloaded websites and YouTube videos offline</p>
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
                # Create tabs
                regular_sites = {k: v for k, v in self.page_browser.loaded_sites.items() if not v.get('is_youtube', False)}
                youtube_sites = [v for v in self.page_browser.loaded_sites.values() if v.get('is_youtube', False)]
                
                html += f"""
                    </div>
                    <div class="tabs">
                        <button class="tab-btn active" onclick="showTab('websites')">🌐 Websites ({len(regular_sites)})</button>
                        <button class="tab-btn youtube" onclick="showTab('youtube')">🎬 YouTube ({len(youtube_sites)})</button>
                    </div>
                    
                    <div id="websites" class="tab-content active">
                """
                
                if regular_sites:
                    html += '<div class="sites-grid">'
                    for domain, site_data in regular_sites.items():
                        metadata = site_data['metadata']
                        pages = list(site_data['pages'].keys())
                        
                        html += f"""
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

                        # Show main pages
                        for page_url in pages[:8]:
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
                else:
                    html += """
                        <div class="empty-state">
                            <h3>No regular websites loaded</h3>
                        </div>
                    """
                
                html += '</div>'  # Close websites tab
                
                # YouTube tab
                html += '<div id="youtube" class="tab-content">'
                
                if youtube_sites:
                    html += '<div class="sites-grid">'
                    # Sort YouTube videos by title
                    sorted_videos = sorted(self.page_browser.youtube_videos, key=lambda x: x['title'])
                    
                    for video in sorted_videos:
                        html += f"""
                        <div class="video-card">
                            <h3>{video['title']}</h3>
                            <div class="stats">
                                <span class="stat video-stat">🎬 YouTube</span>
                                <span class="stat video-stat">{video['channel']}</span>
                            </div>
                            <a href="/youtube/{video['domain']}" class="youtube-btn">▶ Watch Video</a>
                        </div>
                        """
                    html += '</div>'
                else:
                    html += """
                        <div class="empty-state">
                            <h3>No YouTube videos loaded</h3>
                        </div>
                    """
                
                html += '</div>'  # Close youtube tab
                
                # Add JavaScript for tabs
                html += """
                    <script>
                        function showTab(tabName) {
                            // Hide all tabs
                            document.querySelectorAll('.tab-content').forEach(tab => {
                                tab.classList.remove('active');
                            });
                            
                            // Show selected tab
                            document.getElementById(tabName).classList.add('active');
                            
                            // Update active button
                            document.querySelectorAll('.tab-btn').forEach(btn => {
                                btn.classList.remove('active');
                            });
                            event.target.classList.add('active');
                        }
                    </script>
                """

            html += """
                </div>
            </body>
            </html>
            """

            self.wfile.write(html.encode('utf-8'))
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving index: {e}")
    
    def serve_youtube_video(self, path):
        """Serve a YouTube video page"""
        try:
            # Extract video domain from path
            video_domain = path[9:]  # Remove '/youtube/' prefix
            
            if not video_domain:
                self.send_error(404, "YouTube video not specified")
                return
            
            print(f"🔍 Looking for YouTube video: {video_domain}")
            
            # Find the YouTube video
            for video in self.page_browser.youtube_videos:
                if video['domain'] == video_domain:
                    # Get the site data
                    site_data = self.page_browser.loaded_sites.get(video_domain)
                    if site_data:
                        # Get the page content
                        page_data = next(iter(site_data['pages'].values()))
                        content = page_data['content']
                        
                        # Set proper headers
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        
                        self.wfile.write(content.encode('utf-8'))
                        print(f"✅ Served YouTube video: {video['title']}")
                        return
            
            self.send_error(404, f"YouTube video not found: {video_domain}")
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving YouTube video: {e}")
    
    def serve_saved_page(self, path):
        """Serve a page from the loaded .page files"""
        try:
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
                
                # Set proper headers
                self.send_response(200)
                content_type = page_data.get('content_type', 'text/html')
                self.send_header('Content-type', content_type)
                self.end_headers()
                
                self.wfile.write(content.encode('utf-8'))
                print(f"✅ Served page: {requested_url}")
            else:
                print(f"❌ Page not found: {requested_url}")
                # Try to serve a nice 404 page
                self.serve_404(requested_url)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving saved page: {e}")
    
    def serve_404(self, requested_url):
        """Serve a nice 404 page"""
        try:
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
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"❌ Error serving 404 page: {e}")
    
    def rewrite_links(self, html, base_url):
        """Rewrite links in HTML to work with offline browser"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            base_domain = urlparse(base_url).netloc

            # Rewrite <a> tags
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                    if href.startswith(('http://', 'https://')):
                        # External link from same domain
                        if base_domain in href:
                            link['href'] = f"/page/{href}"
                    elif href.startswith('/'):
                        # Absolute path - convert to full URL
                        full_url = f"{urlparse(base_url).scheme}://{base_domain}{href}"
                        link['href'] = f"/page/{full_url}"
                    else:
                        # Relative path
                        full_url = urljoin(base_url, href)
                        link['href'] = f"/page/{full_url}"

            # Rewrite resource links to use our asset server
            self.rewrite_resource_links(soup, base_url)

            return str(soup)
        except Exception as e:
            print(f"❌ Error rewriting links: {e}")
            return html  # Return original HTML if rewriting fails

    def rewrite_resource_links(self, soup, base_url):
        """Rewrite resource links (CSS, JS, images) to use asset server"""
        try:
            base_domain = urlparse(base_url).netloc
            
            # Rewrite <script> tags
            for script in soup.find_all('script', src=True):
                src = script['src']
                if src and not src.startswith(('data:', 'blob:', 'javascript:')):
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
                    
        except Exception as e:
            print(f"❌ Error rewriting resource links: {e}")

    def rewrite_css_url(self, url, base_url):
        """Rewrite a CSS URL to use asset server"""
        if url.startswith(('data:', 'blob:')):
            return f'url({url})'

        if url.startswith(('http://', 'https://')):
            return f'url(/asset/{url})'
        else:
            full_url = urljoin(base_url, url)
            return f'url(/asset/{full_url})'
    
    def log_message(self, format, *args):
        """Override to reduce log spam"""
        # Only log important messages
        if any(x in format for x in ['404', '500', 'ERROR']):
            super().log_message(format, *args)

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n👋 Shutting down server...")
    sys.exit(0)

class ThreadingHTTPServer(HTTPServer):
    """Simple threaded HTTP server that handles connections in separate threads"""
    def process_request(self, request, client_address):
        """Start a new thread to process the request"""
        thread = threading.Thread(target=self.__process_request_thread,
                                  args=(request, client_address))
        thread.daemon = True
        thread.start()
    
    def __process_request_thread(self, request, client_address):
        """Process request in a thread"""
        try:
            HTTPServer.process_request(self, request, client_address)
        except Exception as e:
            print(f"⚠️ Error in request thread: {e}")

def start_browser(pages_directory=None, port=8000):
    """Start the web browser server with robust error handling"""
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
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
    RobustPageFileRequestHandler.page_browser = browser
    
    # Change to script directory to avoid serving system files
    os.chdir(script_dir)

    # Start the server with robust error handling
    server = None
    try:
        # Use threaded server for better stability
        server = ThreadingHTTPServer(('localhost', port), RobustPageFileRequestHandler)
        
        # Set socket options for better stability
        server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        print(f"🌐 Starting offline browser on http://localhost:{port}")
        print("✅ Regular websites and YouTube videos should now work!")
        print("✅ CSS, JavaScript, and images should load properly")
        print("✅ Server is now robust against connection errors!")
        print("✅ Using threaded server for better stability!")
        print("🛑 Press Ctrl+C to stop the server")
        
        # Open browser automatically
        try:
            webbrowser.open(f'http://localhost:{port}')
        except:
            print(f"⚠️ Could not open browser automatically. Please visit: http://localhost:{port}")
        
        # Main server loop
        print("🚀 Server is running...")
        server.serve_forever()
        
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use. Try a different port:")
            print(f"   python browser.py --port 8080")
        else:
            print(f"❌ Server error: {e}")
            import traceback
            traceback.print_exc()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
    except Exception as e:
        print(f"❌ Unexpected error starting server: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if server:
            server.server_close()
        # Clean up temp directory
        if hasattr(browser, 'temp_dir') and os.path.exists(browser.temp_dir):
            try:
                shutil.rmtree(browser.temp_dir)
                print(f"🧹 Cleaned up temp directory: {browser.temp_dir}")
            except Exception as e:
                print(f"⚠️ Could not clean up temp directory: {e}")
        print("✅ Server stopped gracefully")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Offline Website Browser')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--directory', help='Directory containing .page files')
    
    args = parser.parse_args()
    
    start_browser(
        pages_directory=args.directory,
        port=args.port
    )
