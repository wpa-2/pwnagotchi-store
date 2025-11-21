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
# UPDATE THIS WITH YOUR GITEA IP AND PORT
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
    print(r" |_|   v1.2 by WPA2     \_____/\__\___/|_|  \___| ")
    print(f"{RESET}")
    print(f"  Support the dev: {GREEN}https://buymeacoffee.com/wpa2{RESET}\n")

def get_installed_plugins():
    if not os.path.exists(CUSTOM_PLUGIN_DIR):
        return []
    return [f.replace(".py", "") for f in os.listdir(CUSTOM_PLUGIN_DIR) if f.endswith(".py")]

def fetch_registry():
    try:
        r = requests.get(REGISTRY_URL)
        if r.status_code != 200:
            print(f"{RED}[!] Could not connect to store (Status: {r.status_code}){RESET}")
            sys.exit(1)
        return r.json()
    except Exception as e:
        print(f"{RED}[!] Connection failed.{RESET}")
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
    """Scans for self.options['key'] OR self.options["key"] OR self.options.get('key')."""
    params = []
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
            # Regex: finds self.options followed by ['key'] or .get('key')
            matches = re.findall(r"self\.options(?:\[|\.get\()\s*['\"]([^'\"]+)['\"]", content)
            params = list(set(matches)) 
    except:
        pass
    return params

def check_sudo():
    if os.geteuid() != 0:
        print(f"{RED}[!] Error: You must run this command with sudo.{RESET}")
        sys.exit(1)

def install_plugin(args):
    check_sudo()
    target_name = args.name
    registry = fetch_registry()
    
    plugin_data = next((p for p in registry if p['name'] == target_name), None)
    
    if not plugin_data:
        print(f"{RED}[!] Plugin '{target_name}' not found in registry.{RESET}")
        return

    print(f"[*] Installing {CYAN}{target_name}{RESET} by {plugin_data['author']}...")

    final_file_path = os.path.join(CUSTOM_PLUGIN_DIR, f"{target_name}.py")

    try:
        # DOWNLOAD LOGIC
        if plugin_data.get('origin_type') == 'zip':
            print(f"[*] Downloading repository archive...")
            r = requests.get(plugin_data['download_url'])
            z = zipfile.ZipFile(io.BytesIO(r.content))
            target_path = plugin_data['path_inside_zip']
            print(f"[*] Extracting {target_path}...")
            if not os.path.exists(CUSTOM_PLUGIN_DIR):
                os.makedirs(CUSTOM_PLUGIN_DIR)
            with z.open(target_path) as source, open(final_file_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
        else:
            print(f"[*] Downloading file...")
            r = requests.get(plugin_data['download_url'])
            if not os.path.exists(CUSTOM_PLUGIN_DIR):
                os.makedirs(CUSTOM_PLUGIN_DIR)
            with open(final_file_path, "wb") as f:
                f.write(r.content)

        print(f"{GREEN}[+] Successfully installed to {final_file_path}{RESET}")
        
        # AUTO-ENABLE
        update_config(target_name, enable=True)

        # SMART HINTS
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
    """Toggles enabled flag in config.toml"""
    try:
        with open(CONFIG_FILE, "r") as f:
            lines = f.readlines()

        new_lines = []
        found = False
        config_key = f"main.plugins.{plugin_name}.enabled"

        for line in lines:
            if config_key in line:
                found = True
                # Update the existing line
                new_lines.append(f"{config_key} = {'true' if enable else 'false'}\n")
            else:
                new_lines.append(line)
        
        if not found and enable:
            new_lines.append(f"\n{config_key} = true\n")

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

    # LIST
    parser_list = subparsers.add_parser('list', help='List all available plugins')
    parser_list.set_defaults(func=list_plugins)

    # INFO
    parser_info = subparsers.add_parser('info', help='Show details about a plugin')
    parser_info.add_argument('name', type=str, help='Name of the plugin')
    parser_info.set_defaults(func=show_info)

    # INSTALL
    parser_install = subparsers.add_parser('install', help='Install a plugin')
    parser_install.add_argument('name', type=str, help='Name of the plugin')
    parser_install.set_defaults(func=install_plugin)

    # UNINSTALL
    parser_uninstall = subparsers.add_parser('uninstall', help='Uninstall a plugin')
    parser_uninstall.add_argument('name', type=str, help='Name of the plugin')
    parser_uninstall.set_defaults(func=uninstall_plugin)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
