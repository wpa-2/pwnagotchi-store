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
# [IMPORTANT] CHANGE THIS TO YOUR GITHUB RAW URL
REGISTRY_URL = "http://192.168.1.4:3001/wpa2/pwnagotchi-store/raw/branch/main/plugins.json"

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
    print(r" |_|   v1.6 (Upgrade)   \_____/\__\___/|_|  \___| ")
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
            # Look for __version__ = '1.0.0' or "1.0.0"
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

def fetch_registry():
    try:
        r = requests.get(REGISTRY_URL, timeout=15)
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

def list_plugins(args):
    print(f"[*] Fetching plugin list...")
    registry = fetch_registry()
    installed = get_installed_plugins()
    
    print(f"{'NAME':<20} | {'VERSION':<8} | {'STATUS':<10} | {'DESCRIPTION'}")
    print("-" * 85)
    
    for p in registry:
        name = p['name']
        status = f"{GREEN}INSTALLED{RESET}" if name in installed else "Available"
        desc = p['description'][:40] + "..." if len(p['description']) > 40 else p['description']
        print(f"{name:<20} | {p['version']:<8} | {status:<19} | {desc}")
    print("-" * 85)

def show_info(args):
    if not is_safe_name(args.name):
        print(f"{RED}[!] Invalid plugin name.{RESET}")
        return

    target_name = args.name
    registry = fetch_registry()
    plugin_data = next((p for p in registry if p['name'] == target_name), None)
    
    if not plugin_data:
        print(f"{RED}[!] Plugin '{target_name}' not found.{RESET}")
        return

    print(f"\n{CYAN}--- {plugin_data['name']} ---{RESET}")
    print(f"Author:      {plugin_data['author']}")
    print(f"Version:     {plugin_data['version']}")
    print(f"Origin:      {plugin_data['origin_type']}")
    print(f"\n{YELLOW}Description:{RESET}")
    print(plugin_data['description'])
    print(f"\n{YELLOW}Download URL:{RESET}")
    print(plugin_data['download_url'])
    print("")

def scan_for_config_params(file_path):
    params = []
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
            matches = re.findall(r"self\.options(?:\[|\.get\()\s*['\"]([^'\"]+)['\"]", content)
            params = list(set(matches)) 
    except:
        pass
    return params

def update_self(args):
    """Downloads the latest pwnstore.py from the repo and overwrites itself."""
    check_sudo()
    print(f"[*] Checking for tool updates...")
    
    script_url = REGISTRY_URL.replace("plugins.json", "pwnstore.py")
    
    try:
        print(f"[*] Downloading latest version...")
        r = requests.get(script_url, timeout=15)
        if r.status_code != 200:
            print(f"{RED}[!] Update failed: Server returned {r.status_code}{RESET}")
            return
            
        if "#!/usr/bin/env python3" not in r.text:
            print(f"{RED}[!] Security Error: Downloaded file does not look like a valid script.{RESET}")
            return

        current_file = os.path.realpath(__file__)
        with open(current_file, 'w') as f:
            f.write(r.text)
        
        os.chmod(current_file, 0o755)
        print(f"{GREEN}[+] PwnStore updated successfully! Run 'pwnstore list' to verify version.{RESET}")

    except Exception as e:
        print(f"{RED}[!] Update failed: {e}{RESET}")

def upgrade_plugins(args):
    """Checks installed plugins against registry and updates them."""
    check_sudo()
    print(f"[*] Checking for plugin updates...")
    
    registry = fetch_registry()
    installed_files = [f for f in os.listdir(CUSTOM_PLUGIN_DIR) if f.endswith(".py")]
    
    updates_found = []

    for filename in installed_files:
        plugin_name = filename.replace(".py", "")
        
        # Find this plugin in the registry
        remote_data = next((p for p in registry if p['name'] == plugin_name), None)
        
        if remote_data:
            local_ver = get_local_version(os.path.join(CUSTOM_PLUGIN_DIR, filename))
            remote_ver = remote_data['version']
            
            # Basic version check (String comparison works for 1.0.0 vs 1.0.1)
            if remote_ver != local_ver:
                updates_found.append({
                    "name": plugin_name,
                    "local": local_ver,
                    "remote": remote_ver,
                    "author": remote_data['author']
                })

    if not updates_found:
        print(f"{GREEN}[+] All plugins are up to date.{RESET}")
        return

    print(f"\n{YELLOW}Updates available:{RESET}")
    for u in updates_found:
        print(f"  • {CYAN}{u['name']}{RESET}: v{u['local']} -> v{u['remote']}")

    print(f"\n{YELLOW}Do you want to upgrade these {len(updates_found)} plugins? (Y/n){RESET}")
    try:
        choice = input().lower()
    except KeyboardInterrupt:
        print("\n[*] Cancelled.")
        return
    
    if choice == 'y' or choice == '':
        for u in updates_found:
            # Reuse install logic by mocking an args object
            class MockArgs:
                name = u['name']
            
            print(f"\n[*] Upgrading {u['name']}...")
            install_plugin(MockArgs())
        
        print(f"\n{GREEN}[+] Upgrade complete! Please restart Pwnagotchi.{RESET}")
    else:
        print("[*] Upgrade cancelled.")

def install_plugin(args):
    check_sudo()
    if not is_safe_name(args.name):
        print(f"{RED}[!] Security Error: Invalid characters in plugin name.{RESET}")
        return

    target_name = args.name
    registry = fetch_registry()
    
    plugin_data = next((p for p in registry if p['name'] == target_name), None)
    
    if not plugin_data:
        print(f"{RED}[!] Plugin '{target_name}' not found in registry.{RESET}")
        return

    print(f"[*] Installing {CYAN}{target_name}{RESET} by {plugin_data['author']}...")

    final_file_path = os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py")

    try:
        if plugin_data.get('origin_type') == 'zip':
            print(f"[*] Downloading repository archive...")
            r = requests.get(plugin_data['download_url'], timeout=30)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            target_path = plugin_data['path_inside_zip']
            
            if ".." in target_path or target_path.startswith("/"):
                print(f"{RED}[!] Security Error: Malicious zip path detected.{RESET}")
                return

            print(f"[*] Extracting {target_path}...")
            if not os.path.exists(CUSTOM_PLUGIN_DIR):
                os.makedirs(CUSTOM_PLUGIN_DIR)
            
            with z.open(target_path) as source, open(final_file_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
        else:
            print(f"[*] Downloading file...")
            r = requests.get(plugin_data['download_url'], timeout=30)
            if not os.path.exists(CUSTOM_PLUGIN_DIR):
                os.makedirs(CUSTOM_PLUGIN_DIR)
            with open(final_file_path, "wb") as f:
                f.write(r.content)

        print(f"{GREEN}[+] Successfully installed to {final_file_path}{RESET}")
        update_config(target_name, enable=True)

        params = scan_for_config_params(final_file_path)
        if params:
            print(f"\n{YELLOW}[!] CONFIGURATION REQUIRED:{RESET}")
            print(f"This plugin references the following options. You likely need to add them to config.toml:")
            for p in params:
                print(f"  main.plugins.{target_name}.{p} = \"...\"")

    except Exception as e:
        print(f"{RED}[!] Installation failed: {e}{RESET}")

def uninstall_plugin(args):
    check_sudo()
    if not is_safe_name(args.name):
        print(f"{RED}[!] Security Error: Invalid characters in plugin name.{RESET}")
        return

    target_name = args.name
    file_path = os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py")
    
    if not os.path.exists(file_path):
        print(f"{RED}[!] Plugin {target_name} is not installed.{RESET}")
        return

    print(f"[*] Removing {file_path}...")
    try:
        os.remove(file_path)
        print(f"{GREEN}[+] File removed.{RESET}")
        update_config(target_name, enable=False)
    except Exception as e:
        print(f"{RED}[!] Error removing file: {e}{RESET}")

def update_config(plugin_name, enable=True):
    try:
        with open(CONFIG_FILE, "r") as f:
            lines = f.readlines()

        new_lines = []
        found = False
        config_key = f"main.plugins.{plugin_name}.enabled"

        for line in lines:
            if config_key in line:
                found = True
                new_lines.append(f"{config_key} = {'true' if enable else 'false'}\n")
            else:
                new_lines.append(line)
        
        if not found and enable:
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'
            new_lines.append(f"{config_key} = true\n")

        with open(CONFIG_FILE, "w") as f:
            f.writelines(new_lines)
            
        state = "Enabled" if enable else "Disabled"
        print(f"{GREEN}[+] Plugin {state} in config.toml. Restart required.{RESET}")

    except Exception as e:
        print(f"{YELLOW}[!] Config update failed: {e}{RESET}")

def main():
    banner()
    parser = argparse.ArgumentParser(description="Pwnagotchi Plugin Manager")
    subparsers = parser.add_subparsers()

    parser_list = subparsers.add_parser('list', help='List all available plugins')
    parser_list.set_defaults(func=list_plugins)

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

    # NEW UPGRADE COMMAND
    parser_upgrade = subparsers.add_parser('upgrade', help='Check for and install plugin updates')
    parser_upgrade.set_defaults(func=upgrade_plugins)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
