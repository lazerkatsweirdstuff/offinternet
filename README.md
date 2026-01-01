# OffInternet

**A comprehensive tool to download websites and YouTube videos for offline use.**

OffInternet is a Python-based tool designed to reliably save complex web content—including complete websites with all assets or YouTube videos with related content—to your local machine for offline access.

## Features

- **Complete Website Archival**: Downloads entire websites including HTML, CSS, JavaScript, images, and other assets
- **YouTube Video Downloader**: Downloads YouTube videos and optionally fetches related/suggested videos
- **Offline Access**: Download once, view anytime—perfect for archiving, research, or areas with poor connectivity
- **Cloudflare Bypass**: Built-in support for websites protected by Cloudflare security
- **Smart Crawling**: Intelligent URL filtering with relaxed rules to capture more content
- **Bundle Export**: Saves all downloaded content as `.page` files (zipped archives with metadata)
- **Python-Powered**: Built with 100% Python for transparency and easy customization

## Getting Started

### Prerequisites
- Python 3.10+ installed on your system
- Chrome/Chromium browser (for Cloudflare bypass and JavaScript rendering)
- ChromeDriver (automatically managed by the script)

### Installation & Usage

1. Clone the repository:
   ```bash
   git clone https://github.com/lazerkatsweirdstuff/offinternet.git
   cd offinternet
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the downloader:
   ```bash
   python downloader.py
   ```

4. View downloaded content:
   ```bash
   python page-browser.py
   ```
   The browser will run on [localhost:8000](http://localhost:8000)

## Advanced Usage

### Download YouTube Videos
```bash
python downloader.py -y https://youtube.com/watch?v=VIDEO_ID -m 5
```
This downloads the video and up to 5 suggested videos. The `-m` flag sets the maximum number of videos to download.

### Download from a List of URLs
```bash
python downloader.py -f urls.txt -m 10
```
Downloads websites from a text file (`urls.txt`), with a limit of 10 pages per site.

### Advanced Website Crawling
```bash
python downloader.py https://example.com -m 20 --skip-assets
```
Downloads a website deeply (20 pages) but skips images and stylesheets to save space.

## Command Line Reference

| Argument | Description |
|----------|-------------|
| `URL` | Direct URL to download (website or YouTube) |
| `-y`, `--youtube` | Force YouTube downloader mode |
| `-w`, `--website` | Force website downloader mode |
| `-f FILE`, `--file FILE` | File containing list of URLs |
| `-o DIR`, `--output DIR` | Custom output directory |
| `-m N`, `--max-pages N` | Maximum pages/videos to download (default: 2) |
| `-d N`, `--depth N` | Crawl depth for websites (default: 1) |
| `-q`, `--quiet` | Quiet mode (no interactive prompts) |
| `-v`, `--verbose` | Verbose output |
| `--skip-assets` | Skip downloading CSS/images/assets |
| `--yt-quality QUALITY` | YouTube quality: best, 720p, 480p, 360p, worst (default: 720p) |
| `--yt-format FORMAT` | Custom YouTube download format string |

## Project Structure

```
offinternet/
├── page-downloader.py   # Main downloader
├── page-browser.py      # Local web server for viewing .page files
├── README.md            # This file
├── downloaded_sites/    # Default location for saved websites
|  ├── youtube_videos/      # Default location for saved YouTube videos
└── executables/         # (Work in progress) Pre-built binaries
```

## How It Works

### For Websites:
1. **Intelligent Crawling**: Starts from a URL and follows internal links with configurable depth.
2. **Asset Capture**: Downloads HTML, CSS, JavaScript, images, fonts, and other resources.
3. **Link Rewriting**: Converts web URLs to local file paths for offline navigation.
4. **Bundle Creation**: Packages everything into a `.page` file (a ZIP archive with metadata).

### For YouTube:
1. **Video Download**: Downloads the specified video using yt-dlp.
2. **Metadata Capture**: Saves title, description, thumbnail, and video info.
3. **Related Content**: Optionally downloads suggested videos.
4. **Embedded Player**: Creates an HTML page with the video embedded for offline viewing.

## Technical Details

- **Format**: Saved as `.page` files (ZIP archives containing HTML, assets, and metadata)
- **Viewing**: Open `.page` files with the included `page-browser.py` or any ZIP file utility
- **Compatibility**: Works on Windows, macOS, and Linux
- **Dependencies**: See `requirements.txt` for complete list

## Project Status

The project is under active development. Pre-built executables for easier use might be available in the [`/executables`](https://github.com/lazerkatsweirdstuff/offinternet/tree/main/executables) directory (these are a work in progress, so the Python version is recommended for reliability).

## Contributing

Contributions are welcome! If you encounter a website that doesn't download correctly with OffInternet:

**Submit an Issue**: Open a [GitHub Issue](https://github.com/lazerkatsweirdstuff/offinternet/issues) detailing the page you'd like to add support for

## License

BSD-2-Clause license
