# test_assets.py - Run this to check if assets are properly saved
import os
import zipfile
import json

def check_page_file(filepath):
    """Check what's inside a .page file"""
    print(f"🔍 Checking: {filepath}")
    
    try:
        with zipfile.ZipFile(filepath, 'r') as zipf:
            # Read metadata
            metadata_str = zipf.read('metadata.json').decode('utf-8')
            metadata = json.loads(metadata_str)
            print(f"📊 Metadata: {metadata}")
            
            # Count pages
            page_files = [f for f in zipf.namelist() if f.startswith('pages/')]
            print(f"📄 Page files: {len(page_files)}")
            
            # Count assets
            asset_files = [f for f in zipf.namelist() if f.startswith('assets/')]
            print(f"📦 Asset files: {len(asset_files)}")
            
            # Show some asset details
            for asset_file in asset_files[:3]:  # Show first 3
                asset_data_str = zipf.read(asset_file).decode('utf-8')
                asset_data = json.loads(asset_data_str)
                print(f"   📄 {asset_file} - URL: {asset_data.get('url', 'N/A')}")
                
    except Exception as e:
        print(f"❌ Error checking file: {e}")

# Check all .page files in downloaded_sites
downloaded_dir = os.path.join(os.path.dirname(__file__), "downloaded_sites")
if os.path.exists(downloaded_dir):
    for file in os.listdir(downloaded_dir):
        if file.endswith('.page'):
            check_page_file(os.path.join(downloaded_dir, file))
else:
    print("❌ downloaded_sites directory not found")
