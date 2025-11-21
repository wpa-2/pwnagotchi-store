import requests
import json
import re
import io
import zipfile
import os

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# --- METADATA EXTRACTION ---
def parse_python_content(code, filename, origin_url, internal_path=None):
    """Scrapes the __version__, __author__, etc. from the text content of a plugin."""
    try:
        # Regex to find metadata
        version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", code)
        description = re.search(r"__description__\s*=\s*['\"]([^'\"]+)['\"]", code)
        author = re.search(r"__author__\s*=\s*['\"]([^'\"]+)['\"]", code)
        
        # Only accept if it looks like a valid Pwnagotchi plugin
        if description or version:
            return {
                "name": filename.replace(".py", ""),
                "version": version.group(1) if version else "0.0.1",
                "description": description.group(1) if description else "No description provided.",
                "author": author.group(1) if author else "Unknown",
                "origin_type": "zip" if internal_path else "single",
                "download_url": origin_url,  # The URL of the ZIP or the Raw file
                "path_inside_zip": internal_path # None if it's a single file
            }
    except Exception as e:
        print(f"[!] Error parsing {filename}: {e}")
    return None

def process_zip_url(url):
    """Downloads a ZIP and finds all plugins inside."""
    found = []
    try:
        print(f"[*] Downloading ZIP: {url}...")
        r = requests.get(url)
        if r.status_code != 200:
            print(f"   [!] Failed to download (Status: {r.status_code})")
            return []
            
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        for filename in z.namelist():
            # Filter: Must be .py, not __init__, not in hidden folders
            if filename.endswith(".py") and "__init__" not in filename and "/." not in filename:
                with z.open(filename) as f:
                    code = f.read().decode('utf-8', errors='ignore')
                
                plugin = parse_python_content(code, filename.split("/")[-1], url, filename)
                if plugin:
                    print(f"   [+] Found: {plugin['name']} (v{plugin['version']})")
                    found.append(plugin)
    except Exception as e:
        print(f"   [!] ZIP Error: {e}")
    return found

# --- MAIN LOOP ---
def main():
    master_list = []
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r") as f:
        urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

    for url in urls:
        if url.endswith(".zip"):
            plugins = process_zip_url(url)
            master_list.extend(plugins)
        else:
            # Logic for single raw files (if you ever add them)
            try:
                print(f"[*] Scanning file: {url}")
                code = requests.get(url).text
                plugin = parse_python_content(code, url.split("/")[-1], url, None)
                if plugin:
                    master_list.append(plugin)
            except Exception as e:
                print(f"   [!] Error: {e}")

    # Save to JSON
    with open(OUTPUT_FILE, "w") as f:
        json.dump(master_list, f, indent=2)
    
    print(f"\n[SUCCESS] Generated {OUTPUT_FILE} with {len(master_list)} plugins.")

if __name__ == "__main__":
    main()