#!/usr/bin/env python3
import requests
import json
import re
import io
import zipfile
import os
import logging
from collections import defaultdict
from datetime import date

# --- CONFIGURATION ---
INPUT_FILE = "repos.txt"
OUTPUT_FILE = "plugins.json"

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- SMART CATEGORY DICTIONARY ---
KEYWORDS = {
    'GPS': ['gps', 'geo', 'lat', 'lon', 'location', 'map', 'coordinates', 'nmea', 'track', 'wigle', 'wardrive'],
    'Social': ['discord', 'telegram', 'twitter', 'social', 'chat', 'bot', 'webhook', 'slack', 'message', 'notify'],
    'Display': ['screen', 'display', 'ui', 'theme', 'face', 'font', 'oled', 'ink', 'led', 'view', 'clock', 'weather', 'status', 'mem', 'cpu', 'info'],
    'Attack': ['pwn', 'crack', 'handshake', 'deauth', 'assoc', 'brute', 'attack', 'wardriving', 'pmkid', 'wpa', 'eapol', 'sniff'],
    'Hardware': ['ups', 'battery', 'power', 'shutdown', 'reboot', 'button', 'switch', 'gpio', 'i2c', 'spi', 'bluetooth', 'ble', 'hw'],
    'System': ['backup', 'ssh', 'log', 'update', 'fix', 'clean', 'config', 'manage', 'util', 'internet', 'wifi', 'connection']
}

def compare_versions(v1, v2):
    """Compare semantic versions properly. Returns 1 if v1>v2, -1 if v1<v2, 0 if equal."""
    try:
        v1_parts = [int(x) for x in v1.lstrip('v').split('.')]
        v2_parts = [int(x) for x in v2.lstrip('v').split('.')]
        while len(v1_parts) < len(v2_parts): v1_parts.append(0)
        while len(v2_parts) < len(v1_parts): v2_parts.append(0)
        for a, b in zip(v1_parts, v2_parts):
            if a > b: return 1
            elif a < b: return -1
        return 0
    except:
        if v1 > v2: return 1
        elif v1 < v2: return -1
        return 0

def detect_category(name, description, code):
    scores = defaultdict(int)
    name_lower = name.lower()
    desc_lower = description.lower() if description else ""
    code_lower = code.lower()

    for category, tags in KEYWORDS.items():
        for tag in tags:
            if tag in name_lower: scores[category] += 10
            if re.search(r'\b' + re.escape(tag) + r'\b', desc_lower): scores[category] += 3
            if tag in code_lower[:2000]: scores[category] += 1

    if "ui.set" in code_lower: scores["Display"] += 5
    if "gpio" in code_lower: scores["Hardware"] += 2

    if not scores: return "System"
    return max(scores, key=scores.get)

def resolve_variable(code, var_name):
    """Resolve a variable name to its string literal value in the source code."""
    val_match = re.search(rf'{re.escape(var_name)}\s*=\s*[\'"](.+?)[\'"]', code)
    return val_match.group(1) if val_match else None

def resolve_paren_string(code, attr_name):
    """Resolve __attr__ = ("str1 " "str2 " "str3") to a joined string."""
    paren_match = re.search(rf'{attr_name}\s*=\s*\(([\s\S]*?)\)', code)
    if not paren_match:
        return None
    inner = paren_match.group(1)
    # Match double-quoted strings first (handles apostrophes), fall back to single
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', inner)
    if not parts:
        parts = re.findall(r"'((?:[^'\\]|\\.)*)'", inner)
    return "".join(parts).strip() if parts else None

def parse_python_content(code, filename, origin_url, internal_path=None):
    data = {}
    
    try:
        # --- Version: try string literal first, then variable reference ---
        version_match = re.search(r"__version__\s*=\s*['\"](.+?)['\"]", code)
        if version_match:
            data['version'] = version_match.group(1)
        else:
            # Handle __version__ = SOME_VARIABLE
            var_match = re.search(r"__version__\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", code)
            resolved = resolve_variable(code, var_match.group(1)) if var_match else None
            data['version'] = resolved if resolved else "0.0.1"

        # --- Author: string literal or variable reference ---
        author_match = re.search(r"__author__\s*=\s*['\"](.+?)['\"]", code)
        if author_match:
            data['author'] = author_match.group(1)
        else:
            var_match = re.search(r"__author__\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", code)
            resolved = resolve_variable(code, var_match.group(1)) if var_match else None
            data['author'] = resolved if resolved else "Unknown"

        # --- Description: string literal, then parenthesized multi-line, then variable ---
        desc_match = re.search(r"__description__\s*=\s*([\"'])((?:(?!\1).)*)\1", code, re.DOTALL)
        if desc_match:
            data['description'] = desc_match.group(2).strip()
        else:
            # Handle __description__ = ("str1 " "str2 " "str3")
            paren_desc = resolve_paren_string(code, '__description__')
            if paren_desc:
                data['description'] = paren_desc
            else:
                # Handle __description__ = SOME_VARIABLE
                var_match = re.search(r"__description__\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", code)
                resolved = resolve_variable(code, var_match.group(1)) if var_match else None
                data['description'] = resolved if resolved else ""

        # Skip plugins with no description — they pollute the registry
        if not data['description']:
            logging.debug(f"    [-] {filename.split('/')[-1]} skipped — no __description__")
            return None
        
        # Determine category
        data['category'] = detect_category(filename.replace(".py", ""), data['description'], code)

        return {
            "name": filename.replace(".py", ""),
            "version": data['version'],
            "description": data['description'],
            "author": data['author'],
            "category": data['category'],
            "origin_type": "zip" if internal_path else "single",
            "download_url": origin_url,
            "path_inside_zip": internal_path
        }
        
    except Exception as e:
        # Silently fail here (pass) to prevent the build process from crashing 
        # due to one broken file, while still logging the main process.
        pass 
        
    return None

def process_zip_url(url):
    found = []
    try:
        logging.info(f"[*] Downloading ZIP: {url}...")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        
        z = zipfile.ZipFile(io.BytesIO(r.content))
        
        for filename in z.namelist():
            if filename.endswith(".py") and "__init__" not in filename and "/." not in filename:
                with z.open(filename) as f:
                    code = f.read().decode('utf-8', errors='ignore')
                
                # Assume any .py file that passes the filename filter is a plugin (lowering the strictness barrier)
                plugin = parse_python_content(code, filename.split("/")[-1], url, filename)
                if plugin:
                    logging.info(f"    [+] {plugin['name']:<25} -> {plugin['category']}")
                    found.append(plugin)
                
    except Exception as e:
        logging.error(f"    [!] ZIP Error for {url}: {e}")
    return found

def main():
    print("--- PwnStore Builder v1.3 Starting ---")
    master_list = []

    # Load existing date_added values so we don't overwrite them on re-runs
    existing_dates = {}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE) as f:
                for p in json.load(f):
                    if p.get('date_added'):
                        existing_dates[p['name'].lower()] = p['date_added']
        except Exception:
            pass
    today = date.today().isoformat()
    
    if not os.path.exists(INPUT_FILE):
        logging.error(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r") as f:
        urls = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

    for url in urls:
        if url.endswith(".zip"):
            plugins = process_zip_url(url)
            master_list.extend(plugins)
        else:
            try:
                # Handle single raw file URL
                code = requests.get(url, timeout=15).text
                plugin = parse_python_content(code, url.split("/")[-1], url, None)
                if plugin:
                    logging.info(f"    [+] {plugin['name']:<25} -> {plugin['category']}")
                    master_list.append(plugin)
            except Exception as e: 
                logging.error(f"    [!] Raw File Error for {url}: {e}")

    # --- DEDUPLICATION AND SORT ---
    final_plugins = {}
    for plugin in master_list:
        name_key = plugin['name'].lower()
        # Keep the plugin if it's new, or if the current one is a higher version
        if name_key not in final_plugins or compare_versions(plugin['version'], final_plugins[name_key]['version']) > 0:
            final_plugins[name_key] = plugin
            
    # Sort the final list alphabetically by name
    sorted_plugins = sorted(final_plugins.values(), key=lambda p: p['name'].lower())

    # Stamp date_added: preserve existing dates, assign today for new entries
    for p in sorted_plugins:
        p['date_added'] = existing_dates.get(p['name'].lower(), today)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(sorted_plugins, f, indent=2)
    
    print(f"\n[SUCCESS] Generated sorted registry with {len(sorted_plugins)} unique plugins.")

if __name__ == "__main__":
    main()
