import requests
import json
import re
import io
import zipfile
import os

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# --- CATEGORY LOGIC (v3 - Smart Priority) ---
def detect_category(code, name):
    """Scans code AND filename with stricter rules and better priority."""
    text = (code + " " + name).lower()
    name = name.lower()
    
    # 1. SOCIAL
    if any(x in text for x in ['discord', 'telegram', 'twitter', 'mastodon', 'webhook', 'slack', 'pushover', 'ntfy']):
        return "Social"

    # 2. GPS 
    if any(x in name for x in ['gps', 'geo', 'loc', 'map']):
        return "GPS"
    if any(x in text for x in ['gpsd', 'nmea', 'coordinates', 'latitude', 'longitude', 'geofence']):
        return "GPS"

    # 3. ATTACK / WIFI
    if any(x in text for x in ['handshake', 'deauth', 'assoc', 'crack', 'brute', 'pmkid', 'pcap', 'wardriving', 'eapol']):
        return "Attack"

    # 4. HARDWARE
    if any(x in name for x in ['ups', 'battery', 'screen', 'display', 'ink', 'oled', 'bt', 'ble', 'led', 'light']):
        return "Hardware"
    if any(x in text for x in ['gpio', 'i2c', 'spi', 'papirus', 'waveshare', 'inky', 'bluetooth', 'pisugar']):
        return "Hardware"

    # 5. SYSTEM / UTILS
    if any(x in name for x in ['backup', 'log', 'ssh', 'update', 'clean', 'clock', 'uptime']):
        return "System"
    if any(x in text for x in ['cpu_load', 'mem_usage', 'temperature', 'shutdown', 'reboot', 'internet', 'hotspot', 'wlan0']):
        return "System"

    # 6. DISPLAY / UI
    if any(x in text for x in ['ui.set', 'ui.add', 'canvas', 'font', 'faces', 'render', 'layout', 'view']):
        return "Display"
    
    return "General"

# --- METADATA EXTRACTION ---
def parse_python_content(code, filename, origin_url, internal_path=None):
    try:
        # 1. Find Version and Author (Improved Regex to handle ' vs " and spacing)
        version_match = re.search(r"__version__\s*=\s*[\"'](.+?)[\"']", code)
        author_match = re.search(r"__author__\s*=\s*[\"'](.+?)[\"']", code)
        
        version = version_match.group(1) if version_match else "0.0.1"
        author = author_match.group(1) if author_match else "Unknown"
        
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

        category = detect_category(code, filename)

        if description != "No description provided." or version != "0.0.1":
            return {
                "name": filename.replace(".py", ""),
                "version": version,
                "description": description,
                "author": author,
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
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        for filename in z.namelist():
            if filename.endswith(".py") and "__init__" not in filename and "/." not in filename:
                with z.open(filename) as f:
                    code = f.read().decode('utf-8', errors='ignore')
                
                plugin = parse_python_content(code, filename.split("/")[-1], url, filename)
                if plugin:
                    print(f"   [+] {plugin['name']:<25} -> {plugin['category']}")
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
                code = requests.get(url).text
                plugin = parse_python_content(code, url.split("/")[-1], url, None)
                if plugin:
                    print(f"   [+] {plugin['name']:<25} -> {plugin['category']}")
                    master_list.append(plugin)
            except Exception as e: pass

    with open(OUTPUT_FILE, "w") as f:
        json.dump(master_list, f, indent=2)
    print(f"\n[SUCCESS] Updated {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
