# hook-fake_useragent.py
from PyInstaller.utils.hooks import collect_data_files

# Collect all data files from fake_useragent package
datas = collect_data_files('fake_useragent')
