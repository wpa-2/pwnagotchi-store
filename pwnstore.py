#!/usr/bin/env python3
'''
PwnStore - The Unofficial Pwnagotchi App Store
Author: WPA2
Donations: https://buymeacoffee.com/wpa2
v3.3.2 - Dynamic plugin directory from config
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

# Fallback if config.toml has no custom_plugins entry
DEFAULT_CUSTOM_PLUGIN_DIR = "/etc/pwnagotchi/custom-plugins/"
CONFIG_FILE = "/etc/pwnagotchi/config.toml"

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"

def banner():
    print(f"{CYAN}")
    print(r"    ____                 _____ __                 ")
    print(r"   / __ \_      ______  / ___// /_____  ________  ")
    print(r"  / /_/ / | /| / / __ \ \__ \/ __/ __ \/ ___/ _ \ ")
    print(r" / ____/| |/ |/ / / / /___/ / /_/ /_/ / /  /  __/ ")
    print(r"/_/     |__/|__/_/ /_//____/\__/\____/_/    \___/  ")
    print(f"{RESET}")
    print(f"  {CYAN}v3.3.2{RESET} - Dynamic plugin directory from config")
    print(f"  Support the dev: {GREEN}https://buymeacoffee.com/wpa2{RESET}\n")

def check_sudo():
    if os.geteuid() != 0:
        print(f"{RED}[!] Error: You must run this command with sudo.{RESET}")
        sys.exit(1)

def is_safe_name(name):
    """Security: Prevents Path Traversal"""
    return re.match(r'^[a-zA-Z0-9_-]+$', name) is not None

def compare_versions(v1, v2):
    """Compare semantic versions properly"""
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

def get_local_version(file_path):
    """Reads the __version__ string from a local file."""
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
            match = re.search(r"__version__\s*=\s*[\"'](.+?)[\"']", content)
            if match: return match.group(1)
    except: pass
    return "0.0.0"

def get_installed_plugins():
    if not os.path.exists(get_custom_plugin_dir()): return []
    return [f.replace(".py", "") for f in os.listdir(get_custom_plugin_dir()) if f.endswith(".py")]

def get_registry_url():
    """Checks config.toml for a developer override"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                match = re.search(r'main\.pwnstore_url\s*=\s*["\'](http.+?)["\']', content)
                if match: return match.group(1)
    except: pass
    return DEFAULT_REGISTRY

def get_custom_plugin_dir():
    """Read the custom_plugins path from config.toml so pwnstore always installs
    to wherever pwnagotchi is configured to load plugins from.
    Falls back to DEFAULT_CUSTOM_PLUGIN_DIR if no config entry is found."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                # Handles both quoted forms: 'path' and "path"
                match = re.search(r"(?:main\.)?custom_plugins\s*=\s*[\"'](.+?)[\"']", content)
                if match:
                    return match.group(1).rstrip('/')
    except: pass
    return DEFAULT_CUSTOM_PLUGIN_DIR.rstrip('/')

def fetch_registry():
    url = get_registry_url()
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"{RED}[!] Store error (Status: {r.status_code}){RESET}")
            sys.exit(1)
        return r.json()
    except:
        print(f"{RED}[!] Connection failed.{RESET}")
        sys.exit(1)

def clean_author_name(author):
    if not author or author == 'Unknown': return 'Unknown'
    cleaned = re.sub(r'\s*<?[\w\.-]+@[\w\.-]+>?', '', author).strip()
    cleaned = re.sub(r'https?://[^\s]+', '', cleaned).strip()
    cleaned = re.sub(r'^[0-9]+\+\s*', '', cleaned).strip()
    cleaned = re.sub(r'^@', '', cleaned).strip()
    if not cleaned or cleaned.lower() == 'by':
        return author.split(',')[0].strip() or 'Unknown'
    return cleaned.replace(',', '').strip()

def list_plugins(args):
    print(f"[*] Fetching plugin list...")
    registry = fetch_registry()
    installed = get_installed_plugins()
    print(f"{'NAME':<25} | {'VERSION':<10} | {'AUTHOR':<20} | {'STATUS'}")
    print("-" * 80)
    for p in registry:
        name = p['name']
        if len(name) > 24: name = name[:21] + "..."
        status = f"{GREEN}INSTALLED{RESET}" if name in installed else "Available"
        author = clean_author_name(p.get('author', 'Unknown'))
        if len(author) > 19: author = author[:17] + "..."
        print(f"{name:<25} | {p['version']:<10} | {author:<20} | {status}")
    print("-" * 80)

def list_sources(args):
    print(f"[*] Fetching registry...")
    registry = fetch_registry()
    sources = {}
    for p in registry:
        url = p.get('download_url', '')
        repo_key = "other"
        repo_display = "Other/Local"
        if 'github.com' in url or 'githubusercontent.com' in url:
            parts = url.split('/')
            try:
                user, repo = parts[3], parts[4]
                repo_key = f"{user}/{repo}"
                repo_display = f"https://github.com/{user}/{repo}"
            except:
                repo_key = url[:50]
                repo_display = repo_key
        if repo_key not in sources:
            sources[repo_key] = {'display': repo_display, 'count': 0}
        sources[repo_key]['count'] += 1

    sorted_sources = sorted(sources.values(), key=lambda x: x['count'], reverse=True)
    print(f"\n{'REPOSITORY':<55} | {'PLUGINS'}")
    print("-" * 70)
    for s in sorted_sources:
        print(f"{s['display']:<55} | {s['count']}")
    print("-" * 70)
    print(f"Total repos: {len(sources)}  |  Total plugins indexed: {len(registry)}\n")

def search_plugins(args):
    registry = fetch_registry()
    installed = get_installed_plugins()
    query = args.query.lower()
    results = [p for p in registry if query in p['name'].lower() or query in p['description'].lower()]
    if not results: return print(f"{YELLOW}[!] No results for '{args.query}'{RESET}")
    print(f"{'NAME':<25} | {'VERSION':<10} | {'AUTHOR':<20} | {'STATUS'}")
    print("-" * 80)
    for p in results:
        name = p['name']
        if len(name) > 24: name = name[:21] + "..."
        status = f"{GREEN}INSTALLED{RESET}" if name in installed else "Available"
        author = clean_author_name(p.get('author', 'Unknown'))
        if len(author) > 19: author = author[:17] + "..."
        print(f"{name:<25} | {p['version']:<10} | {author:<20} | {status}")
    print("-" * 80)

def show_info(args):
    if not is_safe_name(args.name): return
    registry = fetch_registry()
    plugin_data = next((p for p in registry if p['name'] == args.name), None)
    if not plugin_data: return print(f"{RED}[!] Not found.{RESET}")
    print(f"\n{CYAN}--- {plugin_data['name']} ---{RESET}")
    print(f"Author:      {plugin_data['author']}")
    print(f"Version:     {plugin_data['version']}")
    print(f"Category:    {plugin_data.get('category', 'General')}")
    print(f"\n{YELLOW}Description:{RESET}\n{plugin_data['description']}")
    print(f"\n{YELLOW}Download URL:{RESET}\n{plugin_data['download_url']}\n")

def upgrade_tool(args):
    check_sudo()
    print(f"[*] Checking for PwnStore updates...")
    current_registry = get_registry_url()
    script_url = current_registry.replace("plugins.json", "pwnstore.py")
    try:
        r = requests.get(script_url, timeout=15)
        if r.status_code != 200 or "#!/usr/bin/env python3" not in r.text:
            print(f"{RED}[!] Could not fetch remote version.{RESET}")
            return

        remote_ver_match = re.search(r"(v[\d]+\.[\d]+\.[\d]+)", r.text)
        local_ver_match = re.search(r"(v[\d]+\.[\d]+\.[\d]+)", open(os.path.realpath(__file__)).read())
        remote_ver = remote_ver_match.group(1) if remote_ver_match else "unknown"
        local_ver = local_ver_match.group(1) if local_ver_match else "unknown"

        if remote_ver == local_ver:
            print(f"{GREEN}[+] PwnStore is already up to date ({local_ver}).{RESET}")
            return

        current_file = os.path.realpath(__file__)
        with open(current_file, 'w') as f: f.write(r.text)
        os.chmod(current_file, 0o755)
        print(f"{GREEN}[+] PwnStore updated {local_ver} -> {remote_ver}{RESET}")
        print(f"{CYAN}Restart your session to use the new version.{RESET}")
    except Exception as e: print(f"{RED}[!] Update failed: {e}{RESET}")

def update_plugins(args):
    check_sudo()
    print(f"[*] Checking for updates...")
    registry = fetch_registry()
    installed_files = [f for f in os.listdir(get_custom_plugin_dir()) if f.endswith(".py")]
    updates_found = []
    for filename in installed_files:
        plugin_name = filename.replace(".py", "")
        remote_data = next((p for p in registry if p['name'] == plugin_name), None)
        if remote_data:
            local_ver = get_local_version(os.path.join(get_custom_plugin_dir(), filename))
            remote_ver = remote_data['version']
            if compare_versions(remote_ver, local_ver) > 0:
                updates_found.append({"name": plugin_name, "local": local_ver, "remote": remote_ver, "data": remote_data})
    if not updates_found:
        print(f"{GREEN}[+] Everything current.{RESET}")
        return

    print(f"\n{YELLOW}Found {len(updates_found)} update(s):{RESET}\n")
    updated = []
    skipped = []

    for u in updates_found:
        repo_url = u['data'].get('download_url', '')
        if '/archive/' in repo_url:
            repo_url = repo_url.split('/archive/')[0]

        print(f"  {CYAN}{u['name']}{RESET}: v{u['local']} -> {GREEN}v{u['remote']}{RESET}")
        print(f"  {YELLOW}Changelog: {repo_url}{RESET}")
        print(f"  Upgrade? (Y/n/s to skip all) ", end='', flush=True)

        try:
            choice = input().strip().lower()
        except:
            break

        if choice == 's':
            print(f"\n{YELLOW}[!] Skipping remaining updates.{RESET}")
            break
        elif choice in ('n',):
            print(f"  {YELLOW}Skipped.{RESET}\n")
            skipped.append(u['name'])
            continue
        else:
            class MockArgs: name = u['name']
            install_plugin(MockArgs())
            print(f"  {CYAN}Check for config changes: {repo_url}{RESET}\n")
            updated.append(u['name'])

    print(f"\n{GREEN}[+] Updated: {len(updated)} plugin(s){RESET}" if updated else "")
    print(f"{YELLOW}[!] Skipped: {len(skipped)} plugin(s){RESET}" if skipped else "")
    if updated:
        print(f"{GREEN}[+] Restart Pwnagotchi to activate changes.{RESET}")

def install_plugin(args):
    check_sudo()
    if not is_safe_name(args.name): return
    registry = fetch_registry()
    plugin_data = next((p for p in registry if p['name'] == args.name), None)
    if not plugin_data: return print(f"{RED}[!] Not found.{RESET}")

    final_file_path = os.path.join(get_custom_plugin_dir(), f"{args.name}.py")
    already_installed = os.path.exists(final_file_path)
    print(f"[*] Installing {CYAN}{args.name}{RESET}...")

    try:
        if plugin_data.get('origin_type') == 'zip':
            r = requests.get(plugin_data['download_url'], timeout=30)
            z = zipfile.ZipFile(io.BytesIO(r.content))
            with z.open(plugin_data['path_inside_zip']) as source, open(final_file_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
        else:
            r = requests.get(plugin_data['download_url'], timeout=30)
            if not os.path.exists(get_custom_plugin_dir()): os.makedirs(get_custom_plugin_dir())
            with open(final_file_path, "wb") as f: f.write(r.content)

        print(f"{GREEN}[+] Installed to {final_file_path}{RESET}")
        update_config(args.name, enable=True)
        if not already_installed:
            print(f"\n{YELLOW}[!] Configuration may be required{RESET}")
            repo_url = plugin_data.get('download_url', '')
            if '/archive/' in repo_url:
                repo_url = repo_url.split('/archive/')[0]
            print(f"{CYAN}View setup docs: {repo_url}{RESET}")
            print(f"{CYAN}Edit config: /etc/pwnagotchi/config.toml{RESET}")
    except Exception as e: print(f"{RED}[!] Failed: {e}{RESET}")

def uninstall_plugin(args):
    check_sudo()
    if not is_safe_name(args.name): return
    file_path = os.path.join(get_custom_plugin_dir(), f"{args.name}.py")
    if not os.path.exists(file_path): return
    try:
        os.remove(file_path)
        print(f"{GREEN}[+] File removed.{RESET}")
        remove_plugin_config(args.name)
    except: pass

def update_config(plugin_name, enable=True):
    """Remove the plugin's entire TOML section then re-append if enabling.
    Handles extra user config under the section without orphaning those lines."""
    try:
        if not os.path.exists(CONFIG_FILE): return
        with open(CONFIG_FILE, "r") as f: lines = f.readlines()
        section_header = f"[main.plugins.{plugin_name}]"
        new_lines = []
        inside_section = False
        for line in lines:
            stripped = line.strip()
            if stripped == section_header:
                inside_section = True
                continue
            if stripped.startswith("[") and inside_section:
                inside_section = False
            if not inside_section:
                new_lines.append(line)
        if enable:
            if new_lines and not new_lines[-1].endswith('\n'): new_lines[-1] += '\n'
            new_lines.append(f"\n{section_header}\nenabled = true\n")
        with open(CONFIG_FILE, "w") as f: f.writelines(new_lines)
    except: pass

def remove_plugin_config(plugin_name):
    """Remove the plugin's entire TOML section from config."""
    update_config(plugin_name, enable=False)

def show_detailed_help():
    """Show detailed help when -h is used"""
    print(f"{CYAN}")
    print(r"    ____                 _____ __                 ")
    print(r"   / __ \_      ______  / ___// /_____  ________  ")
    print(r"  / /_/ / | /| / / __ \ \__ \/ __/ __ \/ ___/ _ \ ")
    print(r" / ____/| |/ |/ / / / /___/ / /_/ /_/ / /  /  __/ ")
    print(r"/_/     |__/|__/_/ /_//____/\__/\____/_/    \___/  ")
    print(f"{RESET}\n")
    print(f"{CYAN}PwnStore - Pwnagotchi Plugin Manager v3.3.2{RESET}\n")
    
    print(f"{YELLOW}BROWSE PLUGINS:{RESET}")
    print(f"  {CYAN}pwnstore list{RESET}                    List all available plugins")
    print(f"  {CYAN}pwnstore search <query>{RESET}          Search for plugins")
    print(f"  {CYAN}pwnstore info <name>{RESET}             Show plugin details")
    print(f"  {CYAN}pwnstore sources{RESET}                 Show repository sources\n")
    
    print(f"{YELLOW}MANAGE PLUGINS:{RESET}")
    print(f"  {GREEN}sudo pwnstore install <name>{RESET}     Install a plugin")
    print(f"  {RED}sudo pwnstore uninstall <name>{RESET}   Remove a plugin\n")
    
    print(f"{YELLOW}MAINTENANCE:{RESET}")
    print(f"  {GREEN}sudo pwnstore update{RESET}             Update installed plugins")
    print(f"  {GREEN}sudo pwnstore upgrade{RESET}            Update PwnStore itself\n")
    
    print(f"{YELLOW}EXAMPLES:{RESET}")
    print(f"  {CYAN}pwnstore search discord{RESET}          Find Discord plugins")
    print(f"  {GREEN}sudo pwnstore install discord{RESET}    Install the discord plugin")
    print(f"  {CYAN}pwnstore info discord{RESET}            View discord plugin details\n")
    
    print(f"Need help?")
    print(f"  https://github.com/wpa-2/pwnagotchi-store")
    print(f"  https://t.me/Pwnagotchi_UK_Chat/\n")

def show_minimal_help():
    """Show minimal help when no args are provided"""
    banner()
    print(f"{CYAN}Pwnagotchi Plugin Manager{RESET}\n")
    
    print(f"commands:")
    print(f"  {CYAN}list{RESET}              Browse all available plugins")
    print(f"  {CYAN}sources{RESET}           Show plugin repository sources")
    print(f"  {CYAN}search{RESET} <query>    Search plugins by name or description")
    print(f"  {CYAN}info{RESET} <name>       View detailed plugin information")
    print(f"  {GREEN}install{RESET} <name>    Install a plugin (requires sudo)")
    print(f"  {RED}uninstall{RESET} <name>  Remove a plugin (requires sudo)")
    print(f"  {GREEN}upgrade{RESET}           Update PwnStore itself (requires sudo)")
    print(f"  {GREEN}update{RESET}            Update installed plugins (requires sudo)\n")
    
    print(f"Use '{CYAN}pwnstore -h{RESET}' for detailed help with examples\n")

def main():
    # Check for help flag
    if '-h' in sys.argv or '--help' in sys.argv:
        show_detailed_help()
        sys.exit(0)
    
    # Check for no arguments
    if len(sys.argv) == 1:
        show_minimal_help()
        sys.exit(0)
    
    # Normal argparse operation
    banner()
    parser = argparse.ArgumentParser(description="Pwnagotchi Plugin Manager", add_help=False)
    subparsers = parser.add_subparsers()
    p_list = subparsers.add_parser('list'); p_list.set_defaults(func=list_plugins)
    p_src = subparsers.add_parser('sources'); p_src.set_defaults(func=list_sources)
    p_sch = subparsers.add_parser('search'); p_sch.add_argument('query'); p_sch.set_defaults(func=search_plugins)
    p_inf = subparsers.add_parser('info'); p_inf.add_argument('name'); p_inf.set_defaults(func=show_info)
    p_ins = subparsers.add_parser('install'); p_ins.add_argument('name'); p_ins.set_defaults(func=install_plugin)
    p_uni = subparsers.add_parser('uninstall'); p_uni.add_argument('name'); p_uni.set_defaults(func=uninstall_plugin)
    p_upg = subparsers.add_parser('upgrade'); p_upg.set_defaults(func=upgrade_tool)
    p_upd = subparsers.add_parser('update'); p_upd.set_defaults(func=update_plugins)
    args = parser.parse_args()
    if hasattr(args, 'func'): args.func(args)
    else: show_minimal_help()

if __name__ == "__main__":
    main()
