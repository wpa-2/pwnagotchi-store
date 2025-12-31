#!/usr/bin/env python3
'''
PwnStore - The Unofficial Pwnagotchi App Store
Author: WPA2
Donations: https://buymeacoffee.com/wpa2
'''

import requests
import json
import argparse
import os
import sys
import zipfile
import io
import shutil
import re

# --- CONFIGURATION ---
DEFAULT_REGISTRY = "https://raw.githubusercontent.com/wpa-2/pwnagotchi-store/main/plugins.json"

CUSTOM_PLUGIN_DIR = "/usr/local/share/pwnagotchi/custom-plugins/"
CONFIG_FILE = "/etc/pwnagotchi/config.toml"

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

def banner():
    print(f"{CYAN}")
    print(r"  ____                _____ _                  ")
    print(r" |  _ \ _      ___ __/ ____| |                 ")
    print(r" | |_) \ \ /\ / / '_ \ (___| |_ ___  _ __ ___  ")
    print(r" |  __/ \ V  V /| | | \___ \ __/ _ \| '__/ _ \ ")
    print(r" | |     \_/\_/ |_| |_|____/ || (_) | | |  __/ ")
    print(r" |_|   v2.5 (Clean Auth) \_____/\__\___/|_|  \___| ")
    print(f"{RESET}")
    print(f"  Support the dev: {GREEN}https://buymeacoffee.com/wpa2{RESET}\n")

def check_sudo():
    if os.geteuid() != 0:
        print(f"{RED}[!] Error: You must run this command with sudo.{RESET}")
        sys.exit(1)

def is_safe_name(name):
    """Security: Prevents Path Traversal (e.g. ../../etc/passwd)"""
    return re.match(r'^[a-zA-Z0-9_-]+$', name) is not None

def get_local_version(file_path):
    """Reads the __version__ string from a local file."""
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
            match = re.search(r"__version__\s*=\s*[\"'](.+?)[\"']", content)
            if match:
                return match.group(1)
    except:
        pass
    return "0.0.0"

def get_installed_plugins():
    if not os.path.exists(CUSTOM_PLUGIN_DIR):
        return []
    return [f.replace(".py", "") for f in os.listdir(CUSTOM_PLUGIN_DIR) if f.endswith(".py")]

def get_registry_url():
    """Checks config.toml for a developer override, otherwise uses public GitHub."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                match = re.search(r'main\.pwnstore_url\s*=\s*["\'](http.+?)["\']', content)
                if match:
                    dev_url = match.group(1)
                    return dev_url
    except:
        pass
    return DEFAULT_REGISTRY

def fetch_registry():
    url = get_registry_url()
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"{RED}[!] Could not connect to store (Status: {r.status_code}){RESET}")
            sys.exit(1)
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"{RED}[!] No Internet Connection Detected.{RESET}")
        print(f"    Please connect your Pwnagotchi to the internet.")
        print(f"    {YELLOW}Guide: https://github.com/jayofelony/pwnagotchi/wiki/Step-2-Connecting{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}[!] Connection failed: {e}{RESET}")
        sys.exit(1)

def clean_author_name(author):
    """Removes emails, URLs, and numeric IDs for clean display."""
    if not author or author == 'Unknown':
        return 'Unknown'
    
    # 1. Remove email addresses (e.g., xxx@gmail.com or <xxx@gmail.com>)
    cleaned = re.sub(r'\s*<?[\w\.-]+@[\w\.-]+>?', '', author).strip()
    
    # 2. Remove URL artifacts (e.g., https://github.com/...)
    cleaned = re.sub(r'https?://[^\s]+', '', cleaned).strip()
    
    # 3. Remove GitHub numeric/plus IDs (e.g., 129890632+)
    cleaned = re.sub(r'^[0-9]+\+\s*', '', cleaned).strip()
    
    # 4. Remove leading symbols/handles that are part of the author name
    cleaned = re.sub(r'^@', '', cleaned).strip()
    
    # If cleanup leaves nothing, revert to a clean version of the original.
    if not cleaned or cleaned.lower() == 'by':
        return author.split(',')[0].strip() or 'Unknown'

    # Clean up commas/extra spaces leftover from deletions
    return cleaned.replace(',', '').strip()

def list_plugins(args):
    print(f"[*] Fetching plugin list...")
    registry = fetch_registry()
    installed = get_installed_plugins()
    
    # NEW WIDER TABLE HEADERS
    print(f"{'NAME':<25} | {'VERSION':<10} | {'AUTHOR':<20} | {'STATUS'}")
    print("-" * 80)
    
    for p in registry:
        name = p['name']
        if len(name) > 24: name = name[:21] + "..."
            
        status = f"{GREEN}INSTALLED{RESET}" if name in installed else "Available"
        
        # APPLY CLEANUP LOGIC
        author = clean_author_name(p.get('author', 'Unknown'))
        if len(author) > 19: author = author[:17] + "..."
        
        print(f"{name:<25} | {p['version']:<10} | {author:<20} | {status}")
    print("-" * 80)

def list_sources(args):
    print(f"[*] Analyzing repository sources...")
    registry = fetch_registry()
    sources = {} 

    for p in registry:
        url = p.get('download_url', '')
        repo_name = "Unknown Source"
        if 'github.com' in url or 'githubusercontent.com' in url:
            parts = url.split('/')
            try:
                repo_name = f"github.com/{parts[3]}/{parts[4]}"
            except:
                repo_name = url[:40]
        else:
            repo_name = "Other/Local"
        sources[repo_name] = sources.get(repo_name, 0) + 1

    print(f"\n{'REPOSITORY / SOURCE':<50} | {'PLUGINS'}")
    print("-" * 65)
    for source, count in sorted(sources.items()):
        print(f"{source:<50} | {count}")
    print("-" * 65)
    print(f"Total Plugins Indexed: {len(registry)}\n")

def search_plugins(args):
    print(f"[*] Searching for '{args.query}'...")
    registry = fetch_registry()
    installed = get_installed_plugins()
    
    query = args.query.lower()
    results = [p for p in registry if query in p['name'].lower() or query in p['description'].lower()]
    
    if not results:
        print(f"{YELLOW}[!] No plugins found matching '{args.query}'{RESET}")
        return

    # NEW WIDER TABLE HEADERS
    print(f"{'NAME':<25} | {'VERSION':<10} | {'AUTHOR':<20} | {'STATUS'}")
    print("-" * 80)
    
    for p in results:
        name = p['name']
        if len(name) > 24: name = name[:21] + "..."
            
        status = f"{GREEN}INSTALLED{RESET}" if name in installed else "Available"
        
        # APPLY CLEANUP LOGIC
        author = clean_author_name(p.get('author', 'Unknown'))
        if len(author) > 19: author = author[:17] + "..."
        
        print(f"{name:<25} | {p['version']:<10} | {author:<20} | {status}")
    print("-" * 80)

def show_info(args):
    if not is_safe_name(args.name): return
    target_name = args.name
    registry = fetch_registry()
    plugin_data = next((p for p in registry if p['name'] == target_name), None)
    
    if not plugin_data:
        print(f"{RED}[!] Plugin '{target_name}' not found.{RESET}")
        return

    print(f"\n{CYAN}--- {plugin_data['name']} ---{RESET}")
    print(f"Author:      {plugin_data['author']}")
    print(f"Version:     {plugin_data['version']}")
    print(f"Category:    {plugin_data.get('category', 'General')}")
    print(f"\n{YELLOW}Description:{RESET}")
    print(plugin_data['description'])
    print(f"\n{YELLOW}Download URL:{RESET}")
    print(plugin_data['download_url'])
    print("")

def scan_for_config_params(file_path, plugin_name):
    """Smartly scans for config usage while ignoring API/Data calls."""
    params = []
    ignore = ['main', 'plugins', 'enabled', 'name', 'whitelist', 'screen', 'display', 'none', 'false', 'true', plugin_name]
    
    try:
        with open(file_path, 'r', errors='ignore') as f:
            for line in f:
                if any(bad in line for bad in ['requests.get', 'result.get', 'data.get', 'resp.get', 'json.get']):
                    continue
                
                matches = re.findall(r"self\.options\s*\[\s*['\"]([^'\"]+)['\"]\s*\]", line)
                
                if 'config' in line or 'options' in line or 'kwargs' in line:
                    matches += re.findall(r"\.get\(\s*['\"]([^'\"]+)['\"]", line)
                
                for m in matches:
                    if 'http' in m or '/' in m: continue
                    
                    if m not in ignore and len(m) > 2:
                        params.append(m)
    except:
        pass
    return sorted(list(set(params)))

def update_self(args):
    check_sudo()
    print(f"[*] Checking for tool updates...")
    current_registry = get_registry_url()
    script_url = current_registry.replace("plugins.json", "pwnstore.py")
    
    try:
        print(f"[*] Downloading latest version...")
        r = requests.get(script_url, timeout=15)
        if r.status_code != 200:
            print(f"{RED}[!] Update failed: Server returned {r.status_code}{RESET}")
            return
        if "#!/usr/bin/env python3" not in r.text: return

        current_file = os.path.realpath(__file__)
        with open(current_file, 'w') as f:
            f.write(r.text)
        os.chmod(current_file, 0o755)
        print(f"{GREEN}[+] PwnStore updated successfully! Run 'pwnstore list' to verify version.{RESET}")
    except Exception as e: print(f"{RED}[!] Update failed: {e}{RESET}")

def upgrade_plugins(args):
    check_sudo()
    print(f"[*] Checking for plugin updates...")
    registry = fetch_registry()
    installed_files = [f for f in os.listdir(CUSTOM_PLUGIN_DIR) if f.endswith(".py")]
    updates_found = []

    for filename in installed_files:
        plugin_name = filename.replace(".py", "")
        remote_data = next((p for p in registry if p['name'] == plugin_name), None)
        
        if remote_data:
            local_ver = get_local_version(os.path.join(CUSTOM_PLUGIN_DIR, filename))
            remote_ver = remote_data['version']
            if remote_ver != local_ver:
                updates_found.append({"name": plugin_name, "local": local_ver, "remote": remote_ver})

    if not updates_found:
        print(f"{GREEN}[+] All plugins are up to date.{RESET}")
        return

    print(f"\n{YELLOW}Updates available:{RESET}")
    for u in updates_found:
        print(f"  • {CYAN}{u['name']}{RESET}: v{u['local']} -> v{u['remote']}")

    print(f"\n{YELLOW}Do you want to upgrade these {len(updates_found)} plugins? (Y/n){RESET}")
    try: choice = input().lower()
    except KeyboardInterrupt: return
    
    if choice == 'y' or choice == '':
        for u in updates_found:
            class MockArgs: name = u['name']
            print(f"\n[*] Upgrading {u['name']}...")
            install_plugin(MockArgs())
        print(f"\n{GREEN}[+] Upgrade complete! Please restart Pwnagotchi.{RESET}")
    else: print("[*] Cancelled.")

def install_plugin(args):
    check_sudo()
    if not is_safe_name(args.name): return
    target_name = args.name
    registry = fetch_registry()
    plugin_data = next((p for p in registry if p['name'] == target_name), None)
    
    if not plugin_data:
        print(f"{RED}[!] Plugin '{target_name}' not found in registry.{RESET}")
        return

    # Check if already installed
    final_file_path = os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py")
    already_installed = os.path.exists(final_file_path)
    
    if already_installed:
        print(f"{YELLOW}[!] Plugin '{target_name}' is already installed.{RESET}")
        print(f"{YELLOW}[*] Reinstalling (will update config if needed)...{RESET}")

    print(f"[*] Installing {CYAN}{target_name}{RESET} by {plugin_data['author']}...")

    try:
        if plugin_data.get('origin_type') == 'zip':
            print(f"[*] Downloading repository archive...")
            r = requests.get(plugin_data['download_url'], timeout=30)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            target_path = plugin_data['path_inside_zip']
            if ".." in target_path or target_path.startswith("/"): return
            print(f"[*] Extracting {target_path}...")
            if not os.path.exists(CUSTOM_PLUGIN_DIR): os.makedirs(CUSTOM_PLUGIN_DIR)
            with z.open(target_path) as source, open(final_file_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
        else:
            print(f"[*] Downloading file...")
            r = requests.get(plugin_data['download_url'], timeout=30)
            if not os.path.exists(CUSTOM_PLUGIN_DIR): os.makedirs(CUSTOM_PLUGIN_DIR)
            with open(final_file_path, "wb") as f: f.write(r.content)

        print(f"{GREEN}[+] Successfully installed to {final_file_path}{RESET}")
        update_config(target_name, enable=True)
        
        # Smart Config Scan (only show on first install, not reinstall)
        if not already_installed:
            params = scan_for_config_params(final_file_path, target_name)
            if params:
                print(f"\n{YELLOW}[!] CONFIGURATION REQUIRED:{RESET}")
                print(f"This plugin references the following options. Add them to config.toml:")
                for p in params: print(f"  main.plugins.{target_name}.{p} = \"...\"")
            
    except Exception as e: print(f"{RED}[!] Installation failed: {e}{RESET}")

def uninstall_plugin(args):
    check_sudo()
    if not is_safe_name(args.name): return
    target_name = args.name
    file_path = os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py")
    if not os.path.exists(file_path):
        print(f"{RED}[!] Plugin {target_name} is not installed.{RESET}")
        return
    print(f"[*] Removing {file_path}...")
    try:
        os.remove(file_path)
        print(f"{GREEN}[+] File removed.{RESET}")
        remove_plugin_config(target_name)
    except Exception as e: print(f"{RED}[!] Error: {e}{RESET}")

def update_config(plugin_name, enable=True):
    """Updates config.toml, preventing duplicates with exact key matching."""
    try:
        with open(CONFIG_FILE, "r") as f: 
            lines = f.readlines()
        
        new_lines = []
        found = False
        config_key = f"main.plugins.{plugin_name}.enabled"
        
        # Use regex for EXACT matching (not substring)
        # This pattern matches: main.plugins.PLUGINNAME.enabled = true/false
        # It won't match comments or other lines containing the key
        pattern = re.compile(rf"^\s*{re.escape(config_key)}\s*=\s*(true|false)\s*$")
        
        for line in lines:
            if pattern.match(line.strip()):
                # Found existing config line
                if not found:  # Only update the FIRST occurrence
                    found = True
                    new_lines.append(f"{config_key} = {'true' if enable else 'false'}\n")
                # If we find duplicates, skip them (this cleans up existing dupes)
            else:
                new_lines.append(line)
        
        # Only add new entry if not found AND we're enabling
        if not found and enable:
            # Ensure file ends with newline before adding
            if new_lines and not new_lines[-1].endswith('\n'): 
                new_lines[-1] += '\n'
            new_lines.append(f"\n{config_key} = true\n")

        # Write back to file
        with open(CONFIG_FILE, "w") as f: 
            f.writelines(new_lines)
        
        state = "Enabled" if enable else "Disabled"
        if found:
            print(f"{GREEN}[+] Plugin {state} in config.toml (already existed, updated). Restart required.{RESET}")
        else:
            print(f"{GREEN}[+] Plugin {state} in config.toml (new entry). Restart required.{RESET}")
            
    except Exception as e: 
        print(f"{YELLOW}[!] Config update failed: {e}{RESET}")

def remove_plugin_config(plugin_name):
    """Completely remove ALL config entries for a plugin"""
    try:
        with open(CONFIG_FILE, "r") as f:
            lines = f.readlines()
        
        new_lines = []
        plugin_prefix = f"main.plugins.{plugin_name}."
        removed_count = 0
        
        for line in lines:
            # Skip any line that starts with main.plugins.PLUGINNAME.
            if line.strip().startswith(plugin_prefix):
                removed_count += 1
                continue
            new_lines.append(line)
        
        with open(CONFIG_FILE, "w") as f:
            f.writelines(new_lines)
        
        if removed_count > 0:
            print(f"{GREEN}[+] Removed {removed_count} config entries for {plugin_name}{RESET}")
        else:
            print(f"{YELLOW}[!] No config entries found for {plugin_name}{RESET}")
            
    except Exception as e:
        print(f"{YELLOW}[!] Config cleanup failed: {e}{RESET}")

def main():
    banner()
    parser = argparse.ArgumentParser(description="Pwnagotchi Plugin Manager")
    subparsers = parser.add_subparsers()
    parser_list = subparsers.add_parser('list', help='List all available plugins')
    parser_list.set_defaults(func=list_plugins)
    parser_sources = subparsers.add_parser('sources', help='List repository sources')
    parser_sources.set_defaults(func=list_sources)
    parser_search = subparsers.add_parser('search', help='Search for a plugin')
    parser_search.add_argument('query', type=str, help='Search term')
    parser_search.set_defaults(func=search_plugins)
    parser_info = subparsers.add_parser('info', help='Show details about a plugin')
    parser_info.add_argument('name', type=str, help='Name of the plugin')
    parser_info.set_defaults(func=show_info)
    parser_install = subparsers.add_parser('install', help='Install a plugin')
    parser_install.add_argument('name', type=str, help='Name of the plugin')
    parser_install.set_defaults(func=install_plugin)
    parser_uninstall = subparsers.add_parser('uninstall', help='Uninstall a plugin')
    parser_uninstall.add_argument('name', type=str, help='Name of the plugin')
    parser_uninstall.set_defaults(func=uninstall_plugin)
    parser_update = subparsers.add_parser('update', help='Update PwnStore tool to latest version')
    parser_update.set_defaults(func=update_self)
    parser_upgrade = subparsers.add_parser('upgrade', help='Check for and install plugin updates')
    parser_upgrade.set_defaults(func=upgrade_plugins)
    args = parser.parse_args()
    if hasattr(args, 'func'): args.func(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()
