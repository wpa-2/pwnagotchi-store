import requests
import json
import re
import io
import zipfile
import os

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# --- CATEGORY LOGIC ---
def detect_category(code):
    """Scans code for keywords to guess the category."""
    code_lower = code.lower()
    
    if any(x in code_lower for x in ['ui.set', 'display', 'font', 'screen', 'canvas', 'faces']):
        return "Display"
    if any(x in code_lower for x in ['gps', 'location', 'coordinates', 'fix', 'lat', 'lon']):
        return "GPS"
    if any(x in code_lower for x in ['discord', 'telegram', 'twitter', 'social', 'webhook', 'slack']):
        return "Social"
    if any(x in code_lower for x in ['led', 'gpio', 'light', 'button', 'ups', 'battery']):
        return "Hardware"
    if any(x in code_lower for x in ['handshake', 'deauth', 'assoc', 'crack', 'pwn', 'attack']):
        return "Attack"
    if any(x in code_lower for x in ['log', 'backup', 'ssh', 'ftp', 'system', 'update']):
        return "System"
    
    return "General"

# --- METADATA EXTRACTION ---
def parse_python_content(code, filename, origin_url, internal_path=None):
    try:
        # 1. Find Version and Author
        version = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", code)
        author = re.search(r"__author__\s*=\s*['\"]([^'\"]+)['\"]", code)
        
        # 2. Find Description (Multi-line safe)
        desc_match = re.search(r"__description__\s*=\s*(?:['\"]([^'\"]+)['\"]|\(([^)]+)\))", code, re.DOTALL)
        description = "No description provided."
        if desc_match:
            if desc_match.group(1):
                description = desc_match.group(1)
            elif desc_match.group(2):
                raw_desc = desc_match.group(2)
                description = re.sub(r"['\"\n\r]", "", raw_desc)
                description = re.sub(r"\s+", " ", description).strip()

        # 3. Detect Category
        category = detect_category(code)

        if description != "No description provided." or version:
            return {
                "name": filename.replace(".py", ""),
                "version": version.group(1) if version else "0.0.1",
                "description": description,
                "author": author.group(1) if author else "Unknown",
                "category": category,
                "origin_type": "zip" if internal_path else "single",
                "download_url": origin_url,
                "path_inside_zip": internal_path
            }
    except Exception as e:
        print(f"[!] Error parsing {filename}: {e}")
    return None

def process_zip_url(url):
    found = []
    try:
        print(f"[*] Downloading ZIP: {url}...")
        r = requests.get(url)
        if r.status_code != 200:
            print(f"   [!] Failed to download (Status: {r.status_code})")
            return []
            
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        for filename in z.namelist():
            if filename.endswith(".py") and "__init__" not in filename and "/." not in filename:
                with z.open(filename) as f:
                    code = f.read().decode('utf-8', errors='ignore')
                
                plugin = parse_python_content(code, filename.split("/")[-1], url, filename)
                if plugin:
                    print(f"   [+] Found: {plugin['name']} ({plugin['category']})")
                    found.append(plugin)
    except Exception as e:
        print(f"   [!] ZIP Error: {e}")
    return found

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
            try:
                print(f"[*] Scanning file: {url}")
                code = requests.get(url).text
                plugin = parse_python_content(code, url.split("/")[-1], url, None)
                if plugin:
                    master_list.append(plugin)
            except Exception as e:
                print(f"   [!] Error: {e}")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(master_list, f, indent=2)
    
    print(f"\n[SUCCESS] Generated {OUTPUT_FILE} with {len(master_list)} plugins.")

if __name__ == "__main__":
    main()
