import requests
import json
import re
import io
import zipfile
import os
from collections import defaultdict

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# --- SMART CATEGORY DICTIONARY ---
# Keywords mapped to their category
KEYWORDS = {
    "GPS": ["gps", "geo", "lat", "lon", "location", "map", "coordinates", "nmea", "track"],
    "Social": ["discord", "telegram", "twitter", "social", "chat", "bot", "webhook", "slack", "message", "notify"],
    "Display": ["screen", "display", "ui", "theme", "face", "font", "oled", "ink", "led", "view", "clock", "weather", "status", "mem", "cpu", "info"],
    "Attack": ["pwn", "crack", "handshake", "deauth", "assoc", "brute", "attack", "wardriving", "pmkid", "wpa", "eapol", "sniff"],
    "Hardware": ["ups", "battery", "power", "shutdown", "reboot", "button", "switch", "gpio", "i2c", "spi", "bluetooth", "ble", "hw"],
    "System": ["backup", "ssh", "log", "update", "fix", "clean", "config", "manage", "util", "internet", "wifi", "connection"]
}

def detect_category(name, description, code):
    """Calculates a score for each category based on keywords."""
    scores = defaultdict(int)
    
    # Prepare text blobs
    name_lower = name.lower()
    desc_lower = description.lower() if description else ""
    code_lower = code.lower()

    # --- SCORING LOOP ---
    for category, tags in KEYWORDS.items():
        for tag in tags:
            # 1. Filename Match (Highest Priority: 10 points)
            if tag in name_lower:
                scores[category] += 10
            
            # 2. Description Match (Medium Priority: 3 points)
            # We look for the tag as a whole word to avoid false positives (e.g. "lat" in "platform")
            if re.search(r'\b' + re.escape(tag) + r'\b', desc_lower):
                scores[category] += 3
            
            # 3. Code Match (Low Priority: 1 point)
            # Only checks first 2000 characters of code to avoid false positives deep in logic
            if tag in code_lower[:2000]: 
                scores[category] += 1

    # Specific Fixes/Penalties
    # If it has "ui.set", it's almost certainly Display, give it a boost
    if "ui.set" in code_lower: scores["Display"] += 5
    
    # If it mentions "gpio" explicitly, boost Hardware
    if "gpio" in code_lower: scores["Hardware"] += 2

    # Find the winner
    if not scores:
        return "System" # Default if nothing matches
        
    best_category = max(scores, key=scores.get)
    
    # Debug line (Optional: Uncomment to see how it decided)
    # print(f"{name}: {dict(scores)} -> {best_category}")
    
    return best_category

# --- METADATA EXTRACTION ---
def parse_python_content(code, filename, origin_url, internal_path=None):
    try:
        version_match = re.search(r"__version__\s*=\s*[\"'](.+?)[\"']", code)
        author_match = re.search(r"__author__\s*=\s*[\"'](.+?)[\"']", code)
        
        version = version_match.group(1) if version_match else "0.0.1"
        author = author_match.group(1) if author_match else "Unknown"
        
        desc_match = re.search(r"__description__\s*=\s*(?:['\"]([^'\"]+)['\"]|\(([^)]+)\))", code, re.DOTALL)
        description = "No description provided."
        if desc_match:
            if desc_match.group(1):
                description = desc_match.group(1)
            elif desc_match.group(2):
                raw_desc = desc_match.group(2)
                description = re.sub(r"['\"\n\r]", "", raw_desc)
                description = re.sub(r"\s+", " ", description).strip()

        # PASS ALL DATA TO THE SMART DETECTOR
        category = detect_category(filename.replace(".py", ""), description, code)

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
