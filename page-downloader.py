import os
import requests
import zipfile
import json
from urllib.parse import urlparse, urljoin, parse_qs
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
import brotli
from PIL import Image
import io
import yt_dlp
import argparse
import textwrap
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class YouTubeSuggestionsExtractor:
    """
    Enhanced YouTube Suggestions Extractor
    Extracts suggested/recommended videos from a YouTube page.
    """
    
    def __init__(self, user_agent: str = None):
        """
        Initialize the extractor.
        
        Args:
            user_agent: Custom user agent string (optional)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Video ID string or None if not found
        """
        # Parse the URL
        parsed = urlparse(url)
        
        # Handle different URL patterns
        if 'youtu.be' in url:
            # Shortened URL: https://youtu.be/VIDEO_ID
            video_id = parsed.path.lstrip('/')
            # Remove any query parameters from short URL
            if '?' in video_id:
                video_id = video_id.split('?')[0]
            return video_id
        elif 'youtube.com' in url:
            # Standard URL: https://www.youtube.com/watch?v=VIDEO_ID
            if 'watch' in parsed.path:
                query_params = parse_qs(parsed.query)
                video_id = query_params.get('v', [None])[0]
                return video_id
            # Embed URL: https://www.youtube.com/embed/VIDEO_ID
            elif 'embed' in parsed.path:
                video_id = parsed.path.split('/')[-1]
                return video_id
            # Shorts URL: https://www.youtube.com/shorts/VIDEO_ID
            elif 'shorts' in parsed.path:
                video_id = parsed.path.split('/')[-1]
                return video_id
        
        return None
    
    def extract_from_html(self, html_content: str) -> List[Dict]:
        """
        Extract suggested videos from YouTube page HTML.
        
        Args:
            html_content: Raw HTML of the YouTube page
            
        Returns:
            List of dictionaries containing video information
        """
        suggestions = []
        
        # Pattern 1: Look for var ytInitialData (most reliable)
        yt_data_pattern = r'var ytInitialData\s*=\s*({.*?});'
        yt_data_match = re.search(yt_data_pattern, html_content, re.DOTALL)
        
        if yt_data_match:
            try:
                yt_data = json.loads(yt_data_match.group(1))
                suggestions.extend(self._extract_from_yt_initial_data(yt_data))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"   ⚠️ Error parsing ytInitialData: {e}")
        
        # Pattern 2: Look for watch-next-renderer elements (common for suggestions)
        watch_next_pattern = r'"watchEndpoint":{"videoId":"([^"]+)"[^}]+"simpleText":"([^"]+)"'
        matches = re.findall(watch_next_pattern, html_content)
        
        for video_id, title in matches[:20]:  # Limit to first 20 matches
            if video_id and title and len(video_id) == 11:
                suggestions.append({
                    'title': title.replace('\\u0026', '&').replace('\\"', '"'),
                    'url': f'https://www.youtube.com/watch?v={video_id}',
                    'id': video_id
                })
        
        # Pattern 3: Look for JSON-LD structured data
        ld_json_pattern = r'<script type="application/ld\+json">(.*?)</script>'
        ld_json_matches = re.findall(ld_json_pattern, html_content, re.DOTALL)
        
        for match in ld_json_matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and 'relatedLink' in data:
                    # Extract related videos from JSON-LD
                    related = data.get('relatedLink', [])
                    for item in related:
                        if 'url' in item:
                            video_id = self.extract_video_id(item.get('url', ''))
                            if video_id:
                                suggestions.append({
                                    'title': item.get('name', 'Untitled'),
                                    'url': item.get('url', ''),
                                    'id': video_id
                                })
            except json.JSONDecodeError:
                continue
        
        # Remove duplicates based on video ID
        unique_suggestions = []
        seen_ids = set()
        for video in suggestions:
            if video['id'] and video['id'] not in seen_ids:
                seen_ids.add(video['id'])
                unique_suggestions.append(video)
        
        return unique_suggestions[:20]  # Return top 20 unique suggestions
    
    def _extract_from_yt_initial_data(self, yt_data: dict) -> List[Dict]:
        """
        Extract suggested videos from YouTube's initial data object.
        
        Args:
            yt_data: YouTube's initial data dictionary
            
        Returns:
            List of suggested video dictionaries
        """
        suggestions = []
        
        try:
            # Try multiple paths to find suggested videos
            # Path 1: Secondary results in watch page
            contents = yt_data.get('contents', {}) \
                .get('twoColumnWatchNextResults', {}) \
                .get('secondaryResults', {}) \
                .get('secondaryResults', {}) \
                .get('results', [])
            
            if contents:
                for item in contents:
                    video_info = self._extract_video_info_from_item(item)
                    if video_info:
                        suggestions.append(video_info)
            
            # Path 2: Player overlays/end screen
            if not suggestions:
                items = yt_data.get('playerOverlays', {}) \
                    .get('playerOverlayRenderer', {}) \
                    .get('endScreen', {}) \
                    .get('watchNextEndScreenRenderer', {}) \
                    .get('results', [])
                
                for item in items:
                    video_info = self._extract_video_info_from_item(item)
                    if video_info:
                        suggestions.append(video_info)
            
            # Path 3: Search for compactVideoRenderer in the entire data structure
            def search_for_videos(obj, depth=0):
                if depth > 10:  # Limit recursion depth
                    return []
                
                found = []
                if isinstance(obj, dict):
                    # Check for video renderers
                    for key, value in obj.items():
                        if 'Renderer' in key and isinstance(value, dict):
                            video_info = self._extract_video_info_from_item({key: value})
                            if video_info:
                                found.append(video_info)
                        else:
                            found.extend(search_for_videos(value, depth + 1))
                elif isinstance(obj, list):
                    for item in obj:
                        found.extend(search_for_videos(item, depth + 1))
                return found
            
            if not suggestions:
                suggestions.extend(search_for_videos(yt_data))
                
        except (KeyError, AttributeError) as e:
            print(f"   ⚠️ Error navigating ytInitialData: {e}")
        
        return suggestions
    
    def _extract_video_info_from_item(self, item: dict) -> Optional[Dict]:
        """
        Extract video information from a YouTube data item.
        
        Args:
            item: YouTube data item dictionary
            
        Returns:
            Video info dictionary or None
        """
        try:
            # Try different renderer types
            renderer_keys = ['compactVideoRenderer', 'videoRenderer', 
                           'endScreenVideoRenderer', 'playlistVideoRenderer',
                           'gridVideoRenderer', 'richItemRenderer']
            
            video_renderer = None
            for key in renderer_keys:
                if key in item:
                    video_renderer = item[key]
                    break
            
            if video_renderer:
                video_id = video_renderer.get('videoId')
                if not video_id:
                    # Sometimes videoId is nested
                    video_id = video_renderer.get('navigationEndpoint', {}) \
                        .get('watchEndpoint', {}) \
                        .get('videoId')
                
                # Extract title
                title = ''
                title_runs = video_renderer.get('title', {}) \
                    .get('runs', [{}])
                if title_runs:
                    title = title_runs[0].get('text', '')
                
                # Alternative title path
                if not title:
                    title = video_renderer.get('title', {}) \
                        .get('simpleText', '')
                
                # Another alternative title path
                if not title:
                    title = video_renderer.get('headline', {}) \
                        .get('simpleText', '')
                
                if video_id and title and len(video_id) == 11:
                    return {
                        'title': title.replace('\\u0026', '&').replace('\\"', '"'),
                        'url': f'https://www.youtube.com/watch?v={video_id}',
                        'id': video_id,
                        'channel': video_renderer.get('shortBylineText', {})
                            .get('runs', [{}])[0]
                            .get('text', 'Unknown Channel')
                    }
                    
        except (KeyError, IndexError, AttributeError) as e:
            pass
        
        return None
    
    def get_suggested_videos(self, youtube_url: str, max_results: int = 20) -> List[Dict]:
        """
        Main method to get suggested videos from a YouTube URL.
        
        Args:
            youtube_url: URL of the YouTube video
            max_results: Maximum number of suggestions to return
            
        Returns:
            List of dictionaries with suggested video information
        """
        video_id = self.extract_video_id(youtube_url)
        
        if not video_id:
            raise ValueError(f"Could not extract video ID from URL: {youtube_url}")
        
        # Construct the actual YouTube watch URL
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        
        try:
            # Fetch the YouTube page
            response = self.session.get(watch_url, timeout=15)
            response.raise_for_status()
            
            # Extract suggestions from HTML
            suggestions = self.extract_from_html(response.text)
            
            # Limit results
            return suggestions[:max_results]
            
        except requests.RequestException as e:
            print(f"   ⚠️ Error fetching YouTube page: {e}")
            return []
    
    def get_suggested_videos_as_array(self, youtube_url: str, max_results: int = 20) -> List[str]:
        """
        Get suggested videos as a simple array of URLs.
        
        Args:
            youtube_url: URL of the YouTube video
            max_results: Maximum number of suggestions to return
            
        Returns:
            List of suggested video URLs
        """
        suggestions = self.get_suggested_videos(youtube_url, max_results)
        return [video['url'] for video in suggestions]


class YouTubeDownloader:
    def __init__(self, output_dir=None, max_pages=10, yt_format=None, yt_quality='720p'):
        # Create temp directory for videos while program runs
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if output_dir is None:
            output_dir = os.path.join(script_dir, "youtube_videos")
        
        # Create temp folder if it doesn't exist
        self.temp_dir = os.path.join(output_dir, "temp")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir, exist_ok=True)
        
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        
        self.max_pages = max_pages
        self.downloaded_videos = set()
        self.suggested_queue = deque()
        
        # Initialize suggestions extractor
        self.suggestions_extractor = YouTubeSuggestionsExtractor()
        
        # Set format based on quality preference
        if yt_format:
            format_str = yt_format
        else:
            format_str = self._get_format_for_quality(yt_quality)
        
        # SIMPLIFIED: Just download the best available format
        self.ydl_opts = {
            'format': format_str,
            'outtmpl': os.path.join(self.temp_dir, '%(id)s.%(ext)s'),  # Use temp dir
            'quiet': True,
            'no_warnings': True,
            'writeinfojson': True,
            'writethumbnail': True,
        }
        
        # Initialize session
        self.session = requests.Session()
        self.ua = UserAgent()
        self.update_headers()
    
    def _get_format_for_quality(self, quality: str) -> str:
        """Get format string based on quality preference"""
        quality_map = {
            'best': 'best[ext=mp4]/best',
            '720p': 'best[ext=mp4]/best[height<=720]/best',
            '480p': 'best[ext=mp4]/best[height<=480]/best',
            '360p': 'best[ext=mp4]/best[height<=360]/best',
            'worst': 'worst[ext=mp4]/worst',
        }
        return quality_map.get(quality, 'best[ext=mp4]/best[height<=720]/best')
    
    def update_headers(self):
        """Update session headers with random user agent"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        self.session.headers.update(headers)
    
    def get_suggested_videos(self, video_id=None, url=None, max_results=20):
        """Get suggested videos from YouTube using enhanced extractor"""
        suggested_videos = []
        
        try:
            # Get URL for extraction
            if url:
                extract_url = url
            elif video_id:
                extract_url = f"https://www.youtube.com/watch?v={video_id}"
            else:
                return []
            
            print(f"   🔍 Fetching suggested videos...")
            
            # Use the enhanced extractor
            suggestions = self.suggestions_extractor.get_suggested_videos(
                extract_url, 
                max_results=max_results
            )
            
            for suggested in suggestions:
                suggested_id = suggested['id']
                if suggested_id != video_id and suggested_id not in self.downloaded_videos:
                    suggested_videos.append({
                        'id': suggested_id,
                        'title': suggested.get('title', f"Video {suggested_id}")[:100],
                        'channel': suggested.get('channel', 'Unknown Channel'),
                        'url': suggested['url']
                    })
                    if len(suggested_videos) >= max_results:
                        break
            
            print(f"   ✅ Found {len(suggested_videos)} suggested videos")
            return suggested_videos[:max_results]
            
        except Exception as e:
            print(f"   ⚠️ Error fetching suggested videos: {e}")
            # Fallback to old method
            return self._get_suggested_videos_fallback(video_id, max_results)
    
    def _get_suggested_videos_fallback(self, video_id, max_results=20):
        """Fallback method to get suggested videos if enhanced extractor fails"""
        suggested_videos = []
        
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for link in soup.find_all('a', href=True):
                    href = link.get('href', '')
                    if '/watch?v=' in href and 'list=' not in href:
                        video_id_match = re.search(r'v=([a-zA-Z0-9_-]{11})', href)
                        if video_id_match:
                            suggested_id = video_id_match.group(1)
                            if suggested_id != video_id and suggested_id not in self.downloaded_videos:
                                video_title = link.get_text(strip=True) or f"Video {suggested_id}"
                                suggested_videos.append({
                                    'id': suggested_id,
                                    'title': video_title[:100],
                                    'url': f"https://www.youtube.com/watch?v={suggested_id}"
                                })
                                if len(suggested_videos) >= max_results:
                                    break
        except Exception:
            pass
            
        return suggested_videos[:max_results]
    
    def download_video_simple(self, url, depth=0):
        """Simplified video download without complex processing"""
        if depth >= self.max_pages:
            return None
            
        video_id = None
        try:
            # Extract video ID
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0]
            
            if not video_id or len(video_id) != 11:
                print(f"❌ Invalid YouTube URL: {url}")
                return None
            
            if video_id in self.downloaded_videos:
                return None
            
            print(f"\n🎬 Downloading YouTube video ({depth+1}/{self.max_pages}):")
            print(f"   🔗 URL: {url}")
            print(f"   🆔 Video ID: {video_id}")
            
            # Get video info
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', f'Video {video_id}')
                channel = info.get('uploader', 'Unknown Channel')
                duration = info.get('duration', 0)
                
                print(f"   📹 Title: {title}")
                print(f"   👤 Channel: {channel}")
                print(f"   ⏱️ Duration: {duration}s")
            
            # Download with progress
            def progress_hook(d):
                if d['status'] == 'downloading':
                    percent = d.get('_percent_str', '0%').strip()
                    speed = d.get('_speed_str', 'N/A')
                    print(f"   📥 Downloading: {percent} at {speed}", end='\r')
                elif d['status'] == 'finished':
                    print(f"   ✅ Download complete!                     ")
            
            download_opts = self.ydl_opts.copy()
            download_opts['progress_hooks'] = [progress_hook]
            
            with yt_dlp.YoutubeDL(download_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                if not info_dict:
                    print(f"   ❌ Failed to download video: {url}")
                    return None
                
                # Find downloaded file in temp directory
                video_file = None
                info_file = None
                thumb_file = None
                
                # Look for files in temp directory
                for file in os.listdir(self.temp_dir):
                    if file.startswith(video_id):
                        file_path = os.path.join(self.temp_dir, file)
                        if file.endswith('.json'):
                            info_file = file_path
                        elif file.endswith(('.webp', '.jpg', '.png', '.jpeg')):
                            thumb_file = file_path
                        elif any(file.endswith(ext) for ext in ['.mp4', '.webm', '.mkv', '.flv', '.avi']):
                            video_file = file_path
                
                if not video_file:
                    print(f"   ❌ No video file found for {video_id}")
                    # Try to find by video filename from info_dict
                    if info_dict.get('requested_downloads'):
                        for download in info_dict['requested_downloads']:
                            if download.get('filepath'):
                                video_file = download['filepath']
                                break
                
                if not video_file:
                    print(f"   ❌ Could not locate video file for {video_id}")
                    return None
                
                # Get file info
                file_size = os.path.getsize(video_file)
                file_ext = os.path.splitext(video_file)[1].lower().lstrip('.')
                
                print(f"   💾 File: {os.path.basename(video_file)} ({file_size/1024/1024:.1f} MB)")
                
                # Move files from temp to output directory
                final_video_file = os.path.join(self.output_dir, f"{video_id}.{file_ext}")
                
                # Copy video file
                import shutil
                shutil.copy2(video_file, final_video_file)
                
                # Copy info file if exists
                final_info_file = None
                if info_file:
                    final_info_file = os.path.join(self.output_dir, f"{video_id}.info.json")
                    shutil.copy2(info_file, final_info_file)
                
                # Copy thumbnail if exists
                final_thumb_file = None
                if thumb_file:
                    thumb_ext = os.path.splitext(thumb_file)[1]
                    final_thumb_file = os.path.join(self.output_dir, f"{video_id}{thumb_ext}")
                    shutil.copy2(thumb_file, final_thumb_file)
                
                # Clean up temp files
                try:
                    for file in os.listdir(self.temp_dir):
                        if file.startswith(video_id):
                            os.remove(os.path.join(self.temp_dir, file))
                except Exception as e:
                    print(f"   ⚠️ Could not clean up temp files: {e}")
                
                # Mark as downloaded
                self.downloaded_videos.add(video_id)
                
                # Get suggested videos using enhanced extractor
                if depth < self.max_pages - 1:
                    print(f"   🔍 Finding related videos for next download...")
                    suggested_videos = self.get_suggested_videos(
                        video_id=video_id, 
                        max_results=min(5, self.max_pages - depth - 1)
                    )
                    
                    for suggested in suggested_videos:
                        if suggested['id'] not in self.downloaded_videos:
                            self.suggested_queue.append({
                                'url': suggested['url'],
                                'depth': depth + 1,
                                'parent_id': video_id,
                                'title': suggested['title'],
                                'channel': suggested.get('channel', 'Unknown Channel')
                            })
                    
                    if suggested_videos:
                        print(f"   📋 Added {len(suggested_videos)} suggestions to queue")
                
                return {
                    'success': True,
                    'video_id': video_id,
                    'title': title,
                    'channel': channel,
                    'duration': duration,
                    'video_file': final_video_file,
                    'video_filename': os.path.basename(final_video_file),
                    'file_size': file_size,
                    'file_ext': file_ext,
                    'original_url': url,
                    'depth': depth,
                    'info_file': final_info_file,
                    'thumb_file': final_thumb_file
                }
                
        except Exception as e:
            print(f"\n❌ YouTube download error: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_embedded_page(self, video_data, page_number=1):
        """Create HTML page with embedded video - using local file reference"""
        video_id = video_data['video_id']
        title = video_data['title']
        channel = video_data['channel']
        duration = video_data['duration']
        video_filename = video_data['video_filename']
        
        # Format duration
        if duration:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            if hours > 0:
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "0:00"
        
        # Format file size
        file_size = video_data.get('file_size', 0)
        if file_size > 1024*1024:
            size_str = f"{file_size/1024/1024:.1f} MB"
        elif file_size > 1024:
            size_str = f"{file_size/1024:.1f} KB"
        else:
            size_str = f"{file_size} bytes"
        
        file_ext = video_data.get('file_ext', 'mp4').upper()
        
        # Use local file reference instead of base64
        html_template = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - YouTube</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: #0f0f0f;
            color: white;
            font-family: Arial, sans-serif;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }}
        .logo {{
            color: red;
            font-size: 24px;
            font-weight: bold;
            margin-right: 20px;
        }}
        .search {{
            flex: 1;
            padding: 8px 15px;
            background: #121212;
            border: 1px solid #303030;
            border-radius: 20px;
            color: white;
        }}
        .video-container {{
            background: #000;
            border-radius: 10px;
            overflow: hidden;
            margin-bottom: 20px;
        }}
        video {{
            width: 100%;
            max-height: 720px;
        }}
        .video-title {{
            font-size: 20px;
            font-weight: bold;
            margin: 15px 0;
        }}
        .video-info {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
            color: #aaa;
            font-size: 14px;
        }}
        .actions {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}
        .btn {{
            padding: 8px 15px;
            background: #272727;
            border: none;
            border-radius: 20px;
            color: white;
            cursor: pointer;
        }}
        .subscribe {{
            background: #cc0000;
        }}
        .download-info {{
            background: #272727;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            font-size: 12px;
            color: #aaa;
        }}
        @media (max-width: 768px) {{
            .video-info {{
                flex-direction: column;
                gap: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">YouTube</div>
            <input type="text" class="search" placeholder="Search" value="{title}">
        </div>
        
        <div class="video-container">
            <video controls autoplay>
                <source src="video.mp4" type="video/mp4">
                Your browser does not support HTML5 video.
            </video>
        </div>
        
        <div class="video-title">{title}</div>
        
        <div class="video-info">
            <div>
                <strong>{channel}</strong> • {duration_str} • {size_str}
            </div>
            <div>
                Format: {file_ext} • Page: {page_number}/{self.max_pages}
            </div>
        </div>
        
        <div class="actions">
            <button class="btn subscribe">SUBSCRIBE</button>
            <button class="btn">LIKE</button>
            <button class="btn">SHARE</button>
            <button class="btn">SAVE</button>
        </div>
        
        <div class="download-info">
            <p>📥 Downloaded using YouTube Downloader • Video ID: {video_id}</p>
            <p>🎬 Original URL: {video_data['original_url']}</p>
            <p>⏰ Downloaded: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <script>
        // Auto-play the video
        document.addEventListener('DOMContentLoaded', function() {{
            const video = document.querySelector('video');
            video.play().catch(e => console.log('Auto-play prevented:', e));
            
            // Save playback position
            video.addEventListener('timeupdate', function() {{
                localStorage.setItem('yt_{video_id}_time', video.currentTime);
            }});
            
            // Restore playback position
            const savedTime = localStorage.getItem('yt_{video_id}_time');
            if (savedTime) {{
                video.currentTime = parseFloat(savedTime);
            }}
        }});
    </script>
</body>
</html>'''
        return html_template
    
    def save_as_page_file(self, video_data, page_number, total_pages):
        """Save the YouTube video as a .page file - FIXED ENCODING"""
        try:
            # Create simple metadata
            metadata = {
                'video_id': video_data['video_id'],
                'title': video_data['title'],
                'channel': video_data['channel'],
                'duration': video_data['duration'],
                'original_url': video_data['original_url'],
                'page_number': page_number,
                'total_pages': total_pages,
                'timestamp': time.time(),
                'type': 'youtube_video',
                'file_size': video_data.get('file_size', 0),
                'file_format': video_data.get('file_ext', 'mp4'),
            }
            
            # Create safe filename
            safe_title = re.sub(r'[^\w\-_\. ]', '_', video_data['title'])[:50]
            filename = f"youtube_{video_data['video_id']}_{page_number}_{safe_title}.page"
            filepath = os.path.join(self.output_dir, filename)
            
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Save metadata with explicit UTF-8 encoding
                metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
                zipf.writestr('metadata.json', metadata_json.encode('utf-8'))
                
                # Save HTML with explicit UTF-8 encoding
                html_content = self.create_embedded_page(video_data, page_number)
                zipf.writestr('index.html', html_content.encode('utf-8'))
                
                # Save video file directly
                video_file = video_data['video_file']
                if os.path.exists(video_file):
                    zipf.write(video_file, 'video.mp4')
                
                # Save video info if exists
                info_file = video_data.get('info_file')
                if info_file and os.path.exists(info_file):
                    with open(info_file, 'r', encoding='utf-8') as f:
                        video_info = json.load(f)
                        video_info_json = json.dumps(video_info, indent=2, ensure_ascii=False)
                        zipf.writestr('video_info.json', video_info_json.encode('utf-8'))
                
                # Save thumbnail if exists
                thumb_file = video_data.get('thumb_file')
                if thumb_file and os.path.exists(thumb_file):
                    with open(thumb_file, 'rb') as f:
                        thumb_data = f.read()
                        zipf.writestr('thumbnail' + os.path.splitext(thumb_file)[1], thumb_data)
            
            print(f"💾 Saved: {filename}")
            return filepath
            
        except Exception as e:
            print(f"❌ Error saving .page file: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def download_youtube_with_suggestions(self, start_url):
        """Main download method with enhanced suggestions"""
        print(f"\n{'='*60}")
        print(f"🎬 YOUTUBE DOWNLOADER")
        print(f"📊 Max videos: {self.max_pages}")
        print(f"📁 Output: {self.output_dir}")
        print(f"📁 Temp: {self.temp_dir}")
        print("="*60)
        
        downloaded_files = []
        
        # Add starting URL
        self.suggested_queue.append({
            'url': start_url,
            'depth': 0,
            'parent_id': None
        })
        
        current_page = 1
        
        while self.suggested_queue and current_page <= self.max_pages:
            next_video = self.suggested_queue.popleft()
            url = next_video['url']
            
            print(f"\n📄 Downloading video {current_page}/{self.max_pages}")
            if 'title' in next_video:
                print(f"   📺 Title: {next_video['title']}")
            
            # Download the video
            video_data = self.download_video_simple(url, next_video['depth'])
            
            if video_data and video_data.get('success'):
                # Save as .page file
                page_file = self.save_as_page_file(video_data, current_page, self.max_pages)
                if page_file:
                    downloaded_files.append({
                        'file': page_file,
                        'title': video_data['title'],
                        'video_id': video_data['video_id']
                    })
                
                current_page += 1
            else:
                print(f"❌ Failed to download: {url}")
            
            # Small delay between downloads
            if current_page <= self.max_pages:
                time.sleep(2)
        
        # Clean up temp directory
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ Could not clean up temp directory: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 DOWNLOAD SUMMARY")
        print(f"📁 Downloaded {len(downloaded_files)} videos")
        print(f"📂 Location: {self.output_dir}")
        
        for item in downloaded_files:
            print(f"   • {item['title']}")
        
        print("="*60)
        
        return downloaded_files


class CompleteWebsiteDownloader:
    def __init__(self, output_dir=None, max_pages=10, skip_assets=False):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if output_dir is None:
            self.output_dir = os.path.join(script_dir, "downloaded_sites")
        else:
            self.output_dir = os.path.abspath(output_dir)
            
        print(f"📁 Save location: {self.output_dir}")
        
        self.max_pages = max_pages
        self.skip_assets = skip_assets
        
        # Initialize YouTube downloader with enhanced suggestions
        youtube_output_dir = os.path.join(self.output_dir, "youtube_videos")
        self.youtube_downloader = YouTubeDownloader(
            output_dir=youtube_output_dir,
            max_pages=self.max_pages
        )
        
        # Initialize session with better headers
        self.session = requests.Session()
        self.ua = UserAgent()
        self.update_session_headers()
        
        self.driver = None
        self.visited_urls = set()
        self.pages_to_crawl = deque()
        self.failed_urls = set()
        self.crawl_delay = random.uniform(1, 2)
        self.max_retries = 3
        
        # Asset type priorities
        self.critical_assets = ['.css', '.js']
        self.important_assets = ['.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2', '.ttf']
        self.other_assets = ['.gif', '.webp', '.mp4', '.webm', '.json', '.xml']
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            print(f"✅ Created directory: {self.output_dir}")

    def is_valid_url(self, url):
        """RELAXED URL validation - only filter obvious junk"""
        if not url or not isinstance(url, str):
            return False
            
        # Skip obviously invalid URLs - MUCH MORE PERMISSIVE
        obvious_junk_patterns = [
            r'^[a-f0-9]{64}$',  # SHA256 hashes
            r'^[a-f0-9]{40}$',  # SHA1 hashes  
            r'^[a-zA-Z0-9+/]{40,}={0,2}$',  # Long base64 strings
            r'^[\w\s-]+\s+[\w\s-]+$',  # Plain text with spaces (like "width=device-width")
            r'^:[\w]+\(.*\)$',  # Rails-style routes like ":solution(.:format)"
            r'^@\w+$',  # Twitter handles
        ]
        
        for pattern in obvious_junk_patterns:
            if re.match(pattern, url.strip()):
                return False
        
        # Must have a valid scheme and netloc for HTTP URLs
        try:
            parsed = urlparse(url)
            
            # Skip data URLs and javascript
            if parsed.scheme in ['data', 'javascript', 'mailto', 'tel']:
                return False
                
            # For HTTP URLs, require netloc
            if parsed.scheme in ['http', 'https']:
                if not parsed.netloc:
                    return False
                    
            return True
            
        except Exception:
            return False

    def is_likely_asset_url(self, url):
        """Check if URL is likely a downloadable asset - MORE PERMISSIVE"""
        # Always allow URLs with common file extensions
        valid_extensions = self.critical_assets + self.important_assets + self.other_assets
        
        # Check file extensions
        if any(url.lower().endswith(ext) for ext in valid_extensions):
            return True
            
        # Check common asset patterns
        asset_patterns = [
            r'\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|ttf|webp)(\?.*)?$',
            r'/static/',
            r'/assets/',
            r'/images/',
            r'/fonts/',
            r'/css/',
            r'/js/',
            r'\.min\.(js|css)',
        ]
        
        # If it passes basic URL validation and looks like a resource, allow it
        if any(re.search(pattern, url, re.IGNORECASE) for pattern in asset_patterns):
            return True
            
        # For CSS Zen Garden specifically, be more permissive
        if 'csszengarden.com' in url:
            return True
            
        return False

    def should_download_url(self, url):
        """Main decision function for whether to download a URL"""
        if not self.is_valid_url(url):
            return False
            
        # Always download pages
        if any(url.endswith(ext) for ext in ['', '.html', '.htm', '.php', '.aspx']):
            return True
            
        # Download assets
        if self.is_likely_asset_url(url):
            return True
            
        # For URLs we're unsure about, check if they look like web resources
        try:
            parsed = urlparse(url)
            if parsed.path and '.' in parsed.path:  # Has a file extension
                return True
            if parsed.query:  # Has query parameters (common in assets)
                return True
        except:
            pass
            
        return False

    def update_session_headers(self):
        """Update session headers with random user agent"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
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
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument(f"--user-agent={self.ua.random}")
            
            # Enable performance logging for network requests
            chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
            
            print("🔄 Starting Chrome for complete asset capture...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.implicitly_wait(15)
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
            print("3. Scroll down to trigger lazy loading")
            print("4. Return here and press Enter")
            print("="*50)
            
            input("⏳ Press Enter when the page is COMPLETELY loaded...")
            
            current_url = self.driver.current_url
            print(f"🔗 Current URL: {current_url}")
            print(f"📄 Page title: {self.driver.title}")
            
            # Scroll to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            
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
                clean_url = self.clean_url(full_url)
                
                if self.is_valid_internal_url(clean_url, base_domain) and self.should_download_url(clean_url):
                    links.add(clean_url)
        
        return links

    def is_valid_internal_url(self, url, base_domain):
        """Check if URL is valid and internal"""
        if not url.startswith(('http://', 'https://')):
            return False
            
        if base_domain not in url:
            return False
            
        return True

    def clean_url(self, url):
        """Clean URL but keep important parameters"""
        try:
            parsed = urlparse(url)
            # Remove fragment only, keep query parameters
            cleaned = parsed._replace(fragment='')
            return cleaned.geturl()
        except Exception:
            return url

    def download_with_retry_complete(self, url, retry_count=0, method='get', data=None):
        """Enhanced download with complete retry logic"""
        if not self.should_download_url(url):
            print(f"    🚫 Skipping URL (filtered): {url}")
            return None
            
        if retry_count >= self.max_retries:
            self.failed_urls.add(url)
            return None
        
        try:
            time.sleep(random.uniform(0.5, 1.5))
            
            if random.random() < 0.3:
                self.update_session_headers()
            
            if method == 'post' and data:
                response = self.session.post(url, data=data, timeout=20, allow_redirects=True)
            else:
                response = self.session.get(url, timeout=20, allow_redirects=True)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"    🚫 403 Forbidden: {url}")
                return self.try_alternative_download(url, retry_count)
            elif response.status_code == 429:
                wait_time = 15 + (retry_count * 10)
                print(f"    🐢 429 Rate Limited - waiting {wait_time}s: {url}")
                time.sleep(wait_time)
                return self.download_with_retry_complete(url, retry_count + 1)
            elif response.status_code in [404, 410]:
                print(f"    ❌ {response.status_code} Not Found: {url}")
                return None
            else:
                print(f"    ⚠️ HTTP {response.status_code} for {url}")
                time.sleep(5)
                return self.download_with_retry_complete(url, retry_count + 1)
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            time.sleep(3)
            return self.download_with_retry_complete(url, retry_count + 1)

    def try_alternative_download(self, url, retry_count):
        """Try alternative download methods"""
        print(f"    🔄 Trying alternative download for: {url}")
        
        # Method 1: Try with Selenium if available
        if self.driver:
            try:
                js_fetch = f"""
                fetch('{url}').then(r => r.text()).then(t => window.fetchedContent = t);
                """
                self.driver.execute_script(js_fetch)
                time.sleep(2)
                content = self.driver.execute_script("return window.fetchedContent || ''")
                if content:
                    class MockResponse:
                        def __init__(self, content):
                            self.content = content.encode('utf-8')
                            self.text = content
                            self.status_code = 200
                            self.headers = {'content-type': 'text/html'}
                    return MockResponse(content)
            except:
                pass
        
        return self.download_with_retry_complete(url, retry_count + 1)

    def crawl_website_complete(self, start_url, downloaded_content):
        """Complete website crawling with enhanced asset capture"""
        print("🕷️ Starting COMPREHENSIVE website crawl...")
        
        self.pages_to_crawl.append(start_url)
        self.visited_urls.add(start_url)
        
        crawled_pages = 0
        consecutive_failures = 0
        
        while self.pages_to_crawl and crawled_pages < self.max_pages:
            if consecutive_failures >= 3:
                print("    🚨 Too many failures, trying recovery...")
                if not self.recover_from_failures():
                    break
                consecutive_failures = 0
                
            current_url = self.pages_to_crawl.popleft()
            
            print(f"📄 [{crawled_pages+1}/{self.max_pages}] {self.get_url_display_name(current_url)}")
            
            # Download the page with multiple approaches
            page_data = self.download_page_enhanced(current_url)
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
                        print(f"      🔗 Found new page: {self.get_url_display_name(link)}")
                
                # Download ALL assets including CSS from this page
                if not self.skip_assets:
                    self.download_all_assets_enhanced(page_data['content'], current_url, downloaded_content)
                
                time.sleep(random.uniform(1, 2))
            else:
                consecutive_failures += 1
                print(f"    ❌ Failed (#{consecutive_failures})")
        
        print(f"✅ Crawl complete: {crawled_pages} pages")
        
        # Final asset discovery pass
        if not self.skip_assets:
            self.final_asset_discovery(downloaded_content)

    def get_url_display_name(self, url):
        """Get a clean display name for URL"""
        parsed = urlparse(url)
        path = parsed.path
        if not path or path == '/':
            return f"{parsed.netloc}/"
        return os.path.basename(path) or path[:80]

    def recover_from_failures(self):
        """Attempt to recover from consecutive failures"""
        print("    🔄 Attempting recovery...")
        time.sleep(5)
        self.update_session_headers()
        return True

    def download_page_enhanced(self, url):
        """Enhanced page download with multiple fallbacks"""
        # Try direct download first
        response = self.download_with_retry_complete(url)
        if response and response.status_code == 200:
            return {
                'url': response.url,
                'content': response.text,
                'content_type': response.headers.get('content-type', 'text/html'),
                'status_code': 200,
                'downloaded_with': 'session'
            }
        
        # Try Selenium as fallback
        if self.driver:
            try:
                print(f"    🔄 Falling back to Selenium for: {url}")
                self.driver.get(url)
                time.sleep(3)
                return {
                    'url': url,
                    'content': self.driver.page_source,
                    'content_type': 'text/html',
                    'status_code': 200,
                    'downloaded_with': 'selenium'
                }
            except Exception as e:
                print(f"    ❌ Selenium fallback failed: {e}")
        
        return None

    def download_asset_complete(self, url):
        """Enhanced asset download with better URL validation"""
        # Skip URLs that shouldn't be downloaded
        if not self.should_download_url(url):
            print(f"      🚫 Skipping filtered URL: {url}")
            return None
            
        try:
            if any(url.endswith(ext) for ext in self.critical_assets):
                # Critical assets - be more persistent
                response = self.download_with_retry_complete(url)
            else:
                response = self.session.get(url, timeout=15, stream=True)
                
            if response and response.status_code == 200:
                return self.process_asset_response(response, url)
            else:
                return None
                
        except Exception as e:
            print(f"      ❌ Error downloading asset {url}: {e}")
            return None

    def process_asset_response(self, response, url):
        """Process asset response with enhanced content handling"""
        content_type = response.headers.get('content-type', '').lower()
        content_encoding = response.headers.get('content-encoding', '').lower()
        
        # Handle content encoding
        content = response.content
        if content_encoding == 'gzip':
            try:
                content = gzip.decompress(content)
            except:
                pass
        elif content_encoding == 'br':
            try:
                content = brotli.decompress(content)
            except:
                pass
        
        # Skip very large files (>10MB)
        if len(content) > 10 * 1024 * 1024:
            print(f"      ⚠️ Skipping large file: {len(content)//1024}KB - {url}")
            return None
        
        # Determine encoding and processing
        is_binary = any(ct in content_type for ct in ['image', 'font', 'binary', 'octet-stream']) or url.endswith(('.css', '.js'))
        
        if is_binary:
            encoded = base64.b64encode(content).decode('utf-8')
            encoding = 'base64'
            
            # Additional processing for images
            if 'image' in content_type:
                try:
                    img = Image.open(io.BytesIO(content))
                    asset_info = {
                        'format': img.format,
                        'size': img.size,
                        'mode': img.mode
                    }
                except:
                    asset_info = {}
            else:
                asset_info = {}
                
            return {
                'url': url,
                'content': encoded,
                'content_type': content_type,
                'encoding': encoding,
                'size': len(encoded),
                'filename': os.path.basename(urlparse(url).path) or 'resource',
                'asset_info': asset_info,
                'is_critical': url.endswith(tuple(self.critical_assets))
            }
        else:
            # Text content
            try:
                encoded = content.decode('utf-8')
                encoding = 'text'
            except UnicodeDecodeError:
                try:
                    encoded = content.decode('latin-1')
                    encoding = 'text'
                except:
                    encoded = base64.b64encode(content).decode('utf-8')
                    encoding = 'base64'
            
            return {
                'url': url,
                'content': encoded,
                'content_type': content_type,
                'encoding': encoding,
                'size': len(encoded),
                'filename': os.path.basename(urlparse(url).path) or 'resource',
                'is_critical': url.endswith(tuple(self.critical_assets))
            }

    def extract_assets_from_html(self, html, base_url):
        """Extract ALL possible assets from HTML - MORE PERMISSIVE"""
        soup = BeautifulSoup(html, 'html.parser')
        assets = set()
        
        # Standard tags
        tags_attrs = [
            ('link', 'href'),
            ('script', 'src'),
            ('img', 'src'),
            ('source', 'src'),
            ('source', 'srcset'),
            ('video', 'poster'),
            ('audio', 'src'),
            ('iframe', 'src'),
            ('embed', 'src'),
            ('object', 'data'),
            ('meta', 'content'),
        ]
        
        for tag, attr in tags_attrs:
            for element in soup.find_all(tag, **{attr: True}):
                attr_value = element.get(attr)
                if attr_value:
                    # Handle srcset (multiple images)
                    if attr == 'srcset':
                        for src_entry in attr_value.split(','):
                            src_url = src_entry.strip().split(' ')[0]
                            if src_url:
                                full_url = urljoin(base_url, src_url)
                                if self.should_download_url(full_url):
                                    assets.add(full_url)
                    else:
                        full_url = urljoin(base_url, attr_value)
                        if self.should_download_url(full_url):
                            assets.add(full_url)
        
        # Extract from inline styles and JavaScript
        for style in soup.find_all('style'):
            if style.string:
                assets.update(self.extract_urls_from_css(style.string, base_url))
        
        for script in soup.find_all('script'):
            if script.string:
                assets.update(self.extract_urls_from_js(script.string, base_url))
        
        # Extract from tag attributes that might contain URLs
        for tag in soup.find_all(True):
            for attr in ['style', 'data-src', 'data-background', 'data-url']:
                if tag.get(attr):
                    urls = re.findall(r'url\([\'"]?([^)"\']+)[\'"]?\)', tag.get(attr))
                    for url in urls:
                        full_url = urljoin(base_url, url)
                        if self.should_download_url(full_url):
                            assets.add(full_url)
        
        return assets

    def extract_urls_from_css(self, css_text, base_url):
        """Extract URLs from CSS text - MORE PERMISSIVE"""
        urls = set()
        
        patterns = [
            r'url\([\'"]?([^)"\']+)[\'"]?\)',
            r'@import\s+[\'"]([^\'"]+)[\'"]',
            r'src:\s*url\([\'"]?([^)"\']+)[\'"]?\)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, css_text, re.IGNORECASE)
            for match in matches:
                url = match.strip()
                if url and not url.startswith(('data:', 'blob:')):
                    full_url = urljoin(base_url, url)
                    if self.should_download_url(full_url):
                        urls.add(full_url)
        
        return urls

    def extract_urls_from_js(self, js_text, base_url):
        """Extract URLs from JavaScript text - MORE PERMISSIVE"""
        urls = set()
        
        patterns = [
            r'[\'\"](https?://[^\'\"]+)[\'\"]',
            r'[\'\"](/[^\'\"]+)[\'\"]',
            r'url\([\'"]?([^)"\']+)[\'"]?\)',
            r'=\s*[\'\"]([^\'\"]+\.(css|js|png|jpg|jpeg|svg|ico))[\'\"]',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, js_text)
            for match in matches:
                url = match[0] if isinstance(match, tuple) else match
                if url and not url.startswith(('data:', 'blob:', 'javascript:')):
                    full_url = urljoin(base_url, url)
                    if self.should_download_url(full_url):
                        urls.add(full_url)
        
        return urls

    def download_all_assets_enhanced(self, html, base_url, downloaded_content):
        """Enhanced asset download with prioritization"""
        assets = self.extract_assets_from_html(html, base_url)
        
        # Also get assets from Selenium if available
        if self.driver and base_url == self.driver.current_url:
            selenium_assets = self.get_selenium_network_requests()
            assets.update(selenium_assets)
        
        print(f"    📦 Found {len(assets)} potential assets")
        
        if not assets:
            print("    ℹ️ No assets found to download")
            return
            
        # Download all assets that pass our filters
        successful = 0
        total_assets = len(assets)
        
        for j, asset_url in enumerate(assets):
            if asset_url in downloaded_content['assets'] or asset_url in self.failed_urls:
                continue
            
            filename = os.path.basename(urlparse(asset_url).path) or asset_url[:60]
            print(f"      📁 [{successful+1}/{total_assets}] {filename}")
            
            asset_data = self.download_asset_complete(asset_url)
            if asset_data:
                downloaded_content['assets'][asset_url] = asset_data
                successful += 1
                
                # Process CSS files for nested assets
                if asset_url.endswith('.css'):
                    self.download_css_assets(asset_data, asset_url, downloaded_content)
            else:
                print(f"      ❌ Failed: {filename}")
                self.failed_urls.add(asset_url)
            
            time.sleep(0.1)
        
        print(f"    ✅ Downloaded: {successful}/{total_assets} assets")

    def get_selenium_network_requests(self):
        """Get all network requests from Selenium performance logs"""
        assets = set()
        try:
            logs = self.driver.get_log('performance')
            for log in logs:
                try:
                    message = json.loads(log['message'])
                    message_type = message.get('message', {}).get('method', '')
                    
                    if message_type == 'Network.responseReceived':
                        response = message['message']['params']['response']
                        url = response.get('url', '')
                        if url and self.should_download_url(url):
                            assets.add(url)
                except:
                    continue
        except Exception as e:
            print(f"      ⚠️ Selenium network log error: {e}")
        
        return assets

    def download_css_assets(self, css_asset, css_url, downloaded_content):
        """Download assets referenced in CSS files"""
        try:
            css_content = css_asset['content']
            
            # Decode if base64 encoded
            if css_asset['encoding'] == 'base64':
                css_content = base64.b64decode(css_content)
                
                # Try multiple decoding methods
                css_text = None
                decoding_methods = [
                    ('utf-8', 'UTF-8'),
                    ('latin-1', 'Latin-1'),
                    ('cp1252', 'Windows-1252'),
                ]
                
                for encoding, name in decoding_methods:
                    try:
                        css_text = css_content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
            else:
                css_text = css_content
            
            if not css_text:
                return
            
            # Extract and download referenced assets
            css_assets = self.extract_urls_from_css(css_text, css_url)
            
            for asset_url in css_assets:
                if asset_url not in downloaded_content['assets'] and asset_url not in self.failed_urls:
                    print(f"      📥 CSS asset: {os.path.basename(asset_url) or asset_url[:50]}")
                    asset_data = self.download_asset_complete(asset_url)
                    if asset_data:
                        downloaded_content['assets'][asset_url] = asset_data
            
        except Exception as e:
            print(f"      ⚠️ CSS asset download error: {e}")

    def final_asset_discovery(self, downloaded_content):
        """Final pass to discover missing assets"""
        print("🔍 Performing final asset discovery...")
        
        # Check for common missing assets
        common_assets = [
            '/favicon.ico',
            '/apple-touch-icon.png',
            '/robots.txt',
            '/sitemap.xml',
            '/manifest.json'
        ]
        
        for page_url in downloaded_content['pages']:
            base_domain = urlparse(page_url).netloc
            for asset_path in common_assets:
                asset_url = f"https://{base_domain}{asset_path}"
                if asset_url not in downloaded_content['assets'] and asset_url not in self.failed_urls:
                    print(f"    🔎 Checking for common asset: {asset_path}")
                    asset_data = self.download_asset_complete(asset_url)
                    if asset_data:
                        downloaded_content['assets'][asset_url] = asset_data

    def download_website(self, url):
        """Main download method - now handles YouTube specially"""
        # Check if URL is YouTube
        if 'youtube.com' in url or 'youtu.be' in url:
            print("🎬 YouTube URL detected - using YouTube downloader")
            return self.youtube_downloader.download_youtube_with_suggestions(url)
        else:
            # Use existing website downloader for other sites
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
        print("⬇️ Downloading with RELAXED URL FILTERING...")
        
        downloaded_content = {
            'main_url': url,
            'pages': {},
            'assets': {},
            'timestamp': time.time(),
            'version': '2.2_relaxed_filters'
        }
        
        # Reset state
        self.visited_urls.clear()
        self.pages_to_crawl.clear()
        self.failed_urls.clear()
        
        # Start enhanced crawling
        self.crawl_website_complete(url, downloaded_content)
        
        # Statistics
        total_pages = len(downloaded_content['pages'])
        total_assets = len(downloaded_content['assets'])
        failed_count = len(self.failed_urls)
        
        print(f"    📊 Final Statistics:")
        print(f"    📄 Total pages: {total_pages}")
        print(f"    📦 Total assets: {total_assets}")
        print(f"    ❌ Failed URLs: {failed_count}")
        
        # Save file
        domain = urlparse(url).netloc.replace(':', '_')
        filename = f"{domain}_RELAXED_{int(time.time())}.page"
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
                # Enhanced metadata
                metadata = {
                    'main_url': content['main_url'],
                    'timestamp': content['timestamp'],
                    'version': content['version'],
                    'pages': len(content['pages']),
                    'assets': len(content['assets']),
                    'failed_urls': list(self.failed_urls)
                }
                metadata_json = json.dumps(metadata, indent=2, ensure_ascii=False)
                zipf.writestr('metadata.json', metadata_json.encode('utf-8'))
                
                # Pages
                for url, data in content['pages'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:12]
                    page_json = json.dumps(data, indent=2, ensure_ascii=False)
                    zipf.writestr(f"pages/{hash_val}.json", page_json.encode('utf-8'))
                
                # Assets
                for url, data in content['assets'].items():
                    hash_val = hashlib.md5(url.encode()).hexdigest()[:12]
                    asset_json = json.dumps(data, indent=2, ensure_ascii=False)
                    zipf.writestr(f"assets/{hash_val}.json", asset_json.encode('utf-8'))
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            print(f"    💾 File size: {file_size:.2f} MB")
            return os.path.exists(filepath)
        except Exception as e:
            print(f"    ❌ Save error: {e}")
            return False

    def download_from_list(self, url_list):
        """Download multiple sites"""
        downloaded_files = []
        
        print(f"🎯 Downloading {len(url_list)} sites with RELAXED FILTERS...")
        print(f"📁 Output: {self.output_dir}")
        
        for i, url in enumerate(url_list, 1):
            url = url.strip()
            if not url:
                continue
                
            print(f"\n{'='*60}")
            print(f"#{i}: {url}")
            print("="*60)
            
            try:
                start_time = time.time()
                result = self.download_website(url)
                end_time = time.time()
                
                if result:
                    if isinstance(result, list):  # YouTube returns list of files
                        downloaded_files.extend(result)
                        print(f"✅ YouTube: Downloaded {len(result)} videos ({end_time - start_time:.1f}s)")
                    else:  # Regular website returns single file path
                        downloaded_files.append(result)
                        print(f"✅ Success! ({end_time - start_time:.1f}s)")
                else:
                    print(f"❌ Failed after {end_time - start_time:.1f}s")
                    
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*60}")
        print(f"📊 Complete: {len(downloaded_files)} items downloaded")
        print(f"💾 Location: {self.output_dir}")
        
        return downloaded_files


def main():
    """Main entry point - preserves original behavior when no flags are used"""
    import sys
    
    # Check if any command line flags are used
    has_flags = False
    flag_prefixes = ['-', '--']
    
    for arg in sys.argv[1:]:
        if any(arg.startswith(prefix) for prefix in flag_prefixes):
            has_flags = True
            break
    
    if has_flags:
        # Run with CLI interface
        run_with_cli()
    else:
        # Run with original interactive behavior
        run_original_behavior()


def run_with_cli():
    """Run with CLI interface when flags are used"""
    parser = argparse.ArgumentParser(
        description="Complete Website Downloader with YouTube Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''
        Examples:
          # Download a single website (interactive mode)
          python downloader.py https://example.com
          
          # Download YouTube video with 5 related videos
          python downloader.py -y https://youtube.com/watch?v=VIDEO_ID -m 5
          
          # Download from file list
          python downloader.py -f urls.txt -m 10
          
          # Custom output directory
          python downloader.py https://example.com -o ./my_downloads
          
          # Quiet mode (no interactive prompts)
          python downloader.py https://example.com -q -m 3
          
          # Show verbose output
          python downloader.py https://example.com -v
        ''')
    )
    
    # Required arguments
    parser.add_argument(
        'urls',
        nargs='*',
        help='URL(s) to download (if not provided, use -f or interactive mode)'
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '-y', '--youtube',
        action='store_true',
        help='Force YouTube mode (auto-detected if not specified)'
    )
    mode_group.add_argument(
        '-w', '--website',
        action='store_true',
        help='Force website mode (auto-detected if not specified)'
    )
    
    # File input/output
    parser.add_argument(
        '-f', '--file',
        type=str,
        help='File containing list of URLs to download (one per line)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output directory (default: ./downloaded_sites or ./youtube_videos)'
    )
    
    # Download settings
    parser.add_argument(
        '-m', '--max-pages',
        type=int,
        default=2,
        help='Maximum number of pages/videos to download (default: 2)'
    )
    parser.add_argument(
        '-d', '--depth',
        type=int,
        default=1,
        help='Crawl depth for websites (YouTube uses suggestions)'
    )
    
    # Behavior options
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Quiet mode - no interactive prompts'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Keep temporary files after download'
    )
    parser.add_argument(
        '--skip-assets',
        action='store_true',
        help='Skip downloading assets (CSS, images, etc.)'
    )
    
    # YouTube specific
    parser.add_argument(
        '--yt-format',
        type=str,
        default='best[ext=mp4]/best[height<=720]/best',
        help='YouTube download format (default: best mp4 up to 720p)'
    )
    parser.add_argument(
        '--yt-quality',
        type=str,
        choices=['best', '720p', '480p', '360p', 'worst'],
        default='720p',
        help='Preferred video quality for YouTube downloads'
    )
    
    args = parser.parse_args()
    
    # Get URLs to download
    urls = []
    
    # Read from file if specified
    if args.file:
        try:
            with open(args.file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        urls.append(line)
            print(f"📖 Read {len(urls)} URLs from {args.file}")
        except Exception as e:
            print(f"❌ Error reading file {args.file}: {e}")
            sys.exit(1)
    
    # Add URLs from command line
    urls.extend(args.urls)
    
    # If still no URLs, prompt interactively
    if not urls and not args.quiet:
        while True:
            url = input("Enter URL to download (or press Enter to finish): ").strip()
            if not url:
                break
            urls.append(url)
    
    if not urls:
        print("❌ No URLs provided.")
        sys.exit(1)
    
    # Check requirements
    try:
        import yt_dlp
    except ImportError:
        print("📦 Installing yt-dlp...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
        import yt_dlp
    
    try:
        import fake_useragent
    except ImportError:
        print("📦 Installing fake-useragent...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "fake-useragent"])
        import fake_useragent
    
    # Print banner
    print("="*60)
    print("🚀 COMPLETE WEBSITE DOWNLOADER WITH YOUTUBE SUPPORT")
    print("="*60)
    
    # Process each URL
    downloaded_files = []
    
    for i, url in enumerate(urls, 1):
        print(f"\n📥 Downloading {i}/{len(urls)}: {url}")
        
        # Determine mode
        if args.youtube:
            mode = 'youtube'
        elif args.website:
            mode = 'website'
        else:
            # Auto-detect
            mode = 'youtube' if ('youtube.com' in url or 'youtu.be' in url) else 'website'
        
        print(f"🎯 Mode: {'YouTube' if mode == 'youtube' else 'Website'}")
        print("-"*40)
        
        try:
            if mode == 'youtube':
                # Use YouTube downloader with enhanced suggestions
                output_dir = args.output or os.path.join(os.getcwd(), "youtube_videos")
                downloader = YouTubeDownloader(
                    output_dir=output_dir,
                    max_pages=args.max_pages,
                    yt_format=args.yt_format,
                    yt_quality=args.yt_quality
                )
                result = downloader.download_youtube_with_suggestions(url)
                if result:
                    downloaded_files.extend(result)
            else:
                # Use website downloader
                output_dir = args.output or os.path.join(os.getcwd(), "downloaded_sites")
                downloader = CompleteWebsiteDownloader(
                    output_dir=output_dir,
                    max_pages=args.max_pages,
                    skip_assets=args.skip_assets
                )
                result = downloader.download_website(url)
                if result:
                    downloaded_files.append(result)
                    
        except Exception as e:
            print(f"❌ Error downloading {url}: {e}")
            import traceback
            traceback.print_exc()
    
    # Print summary
    if downloaded_files:
        print(f"\n✅ Successfully downloaded {len(downloaded_files)} items")
    else:
        print(f"\n❌ No items were downloaded")


def run_original_behavior():
    """Run with original interactive behavior (when no flags are used)"""
    print("="*60)
    print("🚀 COMPLETE WEBSITE DOWNLOADER WITH YOUTUBE SUPPORT")
    print("="*60)
    
    # Get max_pages from user - EXACTLY like original
    try:
        max_pages_input = input(f"Enter max pages/videos to download (default: 2): ").strip()
        max_pages = int(max_pages_input) if max_pages_input else 2
    except:
        max_pages = 2
    
    # Check for required packages - EXACTLY like original
    try:
        import yt_dlp
    except ImportError:
        print("📦 Installing yt-dlp...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
        import yt_dlp
    
    sites = []
    
    if len(sys.argv) > 1:
        # URLs provided as command line arguments
        sites = sys.argv[1:]
    else:
        # Interactive mode - EXACTLY like original
        user_input = input("Enter URL to download (or press Enter to exit): ").strip()
        if user_input:
            sites = [user_input]
        else:
            print("No URL provided. Exiting.")
            sys.exit(0)
    
    # Create downloader and run - EXACTLY like original but with enhanced YouTube suggestions
    downloader = CompleteWebsiteDownloader(max_pages=max_pages)
    files = downloader.download_from_list(sites)
    
    if files:
        print(f"\n🎉 Success! Downloaded {len(files)} items!")
        print("💡 Run browser.py to view your downloaded videos!")
    else:
        print(f"\n❌ No videos downloaded. Check the URL and try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Download cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
