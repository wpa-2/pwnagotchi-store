#!/usr/bin/env python3
'''
PwnStore - The Unofficial Pwnagotchi App Store
Author: WPA2
Donations: https://buymeacoffee.com/wpa2
'''

import requests
import argparse
import os
import sys
import zipfile
import io
import shutil
import re

__version__ = "3.3.5"

# --- CONFIGURATION ---
DEFAULT_REGISTRY = "https://raw.githubusercontent.com/wpa-2/pwnagotchi-store/main/plugins.json"

# Fallback if config.toml has no custom_plugins entry
DEFAULT_CUSTOM_PLUGIN_DIR = "/usr/local/share/pwnagotchi/custom-plugins/"
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
    print(f"  {CYAN}v{__version__}{RESET} - Config-safe updates")
    print(f"  Support the dev: {GREEN}https://buymeacoffee.com/wpa2{RESET}\n")

def check_sudo():
    if os.geteuid() != 0:
        print(f"{RED}[!] Error: You must run this command with sudo.{RESET}")
        sys.exit(1)

def is_safe_name(name):
    """Security: Prevents Path Traversal"""
    return bool(name) and re.match(r'^[a-zA-Z0-9_-]+$', name) is not None

def _require_safe_name(name):
    """Validate plugin name and print clear error if invalid."""
    if not is_safe_name(name):
        print(f"{RED}[!] Invalid plugin name: '{name}'. Only letters, numbers, hyphens and underscores allowed.{RESET}")
        return False
    return True

def _parse_version(v):
    """Split a version string into (release_numbers, prerelease_tag).

    "1.2.3"      -> ([1, 2, 3], "")
    "1.2.3-beta" -> ([1, 2, 3], "beta")
    "2.0.0rc1"   -> ([2, 0, 0], "rc1")

    Returns None if there's no leading numeric component to compare on at all
    (e.g. "unknown"), so callers can refuse to act rather than guess.
    """
    if not isinstance(v, str):
        return None
    v = v.strip().lstrip('vV')
    # Split the numeric release part from any pre-release/build suffix.
    m = re.match(r'^(\d+(?:\.\d+)*)[.\-_+]?([A-Za-z0-9.\-_+]*)$', v)
    if not m:
        return None
    numbers = [int(x) for x in m.group(1).split('.')]
    return numbers, m.group(2) or ""


def compare_versions(v1, v2):
    """Compare semantic versions. Returns 1 if v1>v2, -1 if v1<v2, 0 if equal.

    A pre-release ("1.2.0-beta") sorts BELOW the matching release ("1.2.0"),
    per semver. The old implementation fell back to a lexicographic string
    compare here, which ranked betas as newer than their own stable release
    and treated any unparseable string as newer than everything.

    Returns None when either side can't be parsed, so callers can distinguish
    "older/newer/same" from "no idea" instead of silently getting a wrong answer.
    """
    p1, p2 = _parse_version(v1), _parse_version(v2)
    if p1 is None or p2 is None:
        return None

    n1, tag1 = p1
    n2, tag2 = p2
    while len(n1) < len(n2): n1.append(0)
    while len(n2) < len(n1): n2.append(0)
    for a, b in zip(n1, n2):
        if a > b: return 1
        if a < b: return -1

    # Same release numbers: no tag beats any tag (1.2.0 > 1.2.0-beta).
    if not tag1 and not tag2: return 0
    if not tag1: return 1
    if not tag2: return -1
    return (tag1 > tag2) - (tag1 < tag2)

def get_local_version(file_path):
    """Reads the __version__ string from a local file."""
    try:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read()
            match = re.search(r"__version__\s*=\s*[\"'](.+?)[\"']", content)
            if match: return match.group(1)
    except Exception:
        pass
    return "0.0.0"

def get_installed_plugins():
    plugin_dir = get_custom_plugin_dir()
    if not os.path.exists(plugin_dir): return []
    return [f[:-3] for f in os.listdir(plugin_dir) if f.endswith(".py")]

def get_registry_url():
    """Checks config.toml for a developer override"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                content = f.read()
                match = re.search(r'main\.pwnstore_url\s*=\s*["\'](http.+?)["\']', content)
                if match: return match.group(1)
    except Exception:
        pass
    return DEFAULT_REGISTRY

def get_custom_plugin_dir():
    """Read the custom_plugins path from config.toml so pwnstore always installs
    to wherever pwnagotchi is configured to load plugins from.

    Pwnagotchi's config layout has moved around over the years, so custom_plugins
    is the single source of truth. Commented-out lines are ignored, and the last
    uncommented definition wins (matching how TOML itself resolves duplicates).
    Falls back to DEFAULT_CUSTOM_PLUGIN_DIR if no config entry is found."""
    try:
        if os.path.exists(CONFIG_FILE):
            found = None
            with open(CONFIG_FILE, 'r', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    match = re.match(r"^(?:main\.)?custom_plugins\s*=\s*[\"'](.+?)[\"']", stripped)
                    if match:
                        found = match.group(1).strip()
            if found:
                return found.rstrip('/')
    except Exception:
        pass
    return DEFAULT_CUSTOM_PLUGIN_DIR.rstrip('/')

def fetch_registry():
    url = get_registry_url()
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print(f"{RED}[!] Store error (Status: {r.status_code}){RESET}")
            sys.exit(1)
        return r.json()
    except Exception:
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

def _format_status(plugin_name, remote_version, installed_list):
    """Determine the display status for a plugin in list/search views."""
    if plugin_name not in installed_list:
        return "Available"
    local_ver = get_local_version(os.path.join(get_custom_plugin_dir(), f"{plugin_name}.py"))
    cmp = compare_versions(remote_version, local_ver)
    if cmp is not None and cmp > 0:
        return f"{YELLOW}UPDATE AVAILABLE{RESET}"
    return f"{GREEN}INSTALLED{RESET}"

def list_plugins(args):
    print(f"[*] Fetching plugin list...")
    registry = fetch_registry()
    installed = get_installed_plugins()
    print(f"{'NAME':<25} | {'VERSION':<10} | {'AUTHOR':<20} | {'STATUS'}")
    print("-" * 80)
    for p in registry:
        original_name = p.get('name', '')
        display_name = original_name
        if len(display_name) > 24: display_name = display_name[:21] + "..."
        status = _format_status(original_name, p['version'], installed)
        author = clean_author_name(p.get('author', 'Unknown'))
        if len(author) > 19: author = author[:17] + "..."
        print(f"{display_name:<25} | {p['version']:<10} | {author:<20} | {status}")
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
            try: repo_name = f"github.com/{parts[3]}/{parts[4]}"
            except IndexError: repo_name = url[:40]
        else: repo_name = "Other/Local"
        sources[repo_name] = sources.get(repo_name, 0) + 1
    print(f"\n{'REPOSITORY / SOURCE':<50} | {'PLUGINS'}")
    print("-" * 65)
    for source, count in sorted(sources.items()):
        print(f"{source:<50} | {count}")
    print("-" * 65)
    print(f"Total indexed: {len(registry)}\n")

def search_plugins(args):
    registry = fetch_registry()
    installed = get_installed_plugins()
    query = args.query.lower()
    results = [p for p in registry
               if query in p.get('name', '').lower() or query in p.get('description', '').lower()]
    if not results: return print(f"{YELLOW}[!] No results for '{args.query}'{RESET}")
    print(f"{'NAME':<25} | {'VERSION':<10} | {'AUTHOR':<20} | {'STATUS'}")
    print("-" * 80)
    for p in results:
        original_name = p.get('name', '')
        display_name = original_name
        if len(display_name) > 24: display_name = display_name[:21] + "..."
        status = _format_status(original_name, p['version'], installed)
        author = clean_author_name(p.get('author', 'Unknown'))
        if len(author) > 19: author = author[:17] + "..."
        print(f"{display_name:<25} | {p['version']:<10} | {author:<20} | {status}")
    print("-" * 80)

def show_info(args):
    if not _require_safe_name(args.name): return
    registry = fetch_registry()
    plugin_data = next((p for p in registry if p.get('name') == args.name), None)
    if not plugin_data: return print(f"{RED}[!] Not found.{RESET}")
    print(f"\n{CYAN}--- {plugin_data['name']} ---{RESET}")
    print(f"Author:      {plugin_data['author']}")
    print(f"Version:     {plugin_data['version']}")
    print(f"Category:    {plugin_data.get('category', 'General')}")

    # Show local install status
    installed = get_installed_plugins()
    if plugin_data['name'] in installed:
        local_ver = get_local_version(os.path.join(get_custom_plugin_dir(), f"{plugin_data['name']}.py"))
        cmp = compare_versions(plugin_data['version'], local_ver)
        if cmp is None:
            print(f"Installed:   {YELLOW}v{local_ver} (cannot compare with registry v{plugin_data['version']}){RESET}")
        elif cmp > 0:
            print(f"Installed:   {YELLOW}v{local_ver} (update available -> v{plugin_data['version']}){RESET}")
        elif cmp < 0:
            print(f"Installed:   {GREEN}v{local_ver} (ahead of registry){RESET}")
        else:
            print(f"Installed:   {GREEN}v{local_ver} (up to date){RESET}")
    else:
        print(f"Installed:   No")

    print(f"\n{YELLOW}Description:{RESET}\n{plugin_data['description']}")
    print(f"\n{YELLOW}Download URL:{RESET}\n{plugin_data['download_url']}\n")

def upgrade_tool(args):
    check_sudo()
    print(f"[*] Checking for PwnStore updates...")

    # Build the remote script URL from the registry base
    registry_url = get_registry_url()
    if "plugins.json" in registry_url:
        script_url = registry_url.replace("plugins.json", "pwnstore.py")
    else:
        # Custom registry that doesn't end in plugins.json — can't infer script location
        print(f"{YELLOW}[!] Custom registry URL detected. Cannot auto-upgrade from non-standard registries.{RESET}")
        print(f"{CYAN}Download the latest pwnstore.py manually from: https://github.com/wpa-2/pwnagotchi-store{RESET}")
        return

    try:
        r = requests.get(script_url, timeout=15)
        if r.status_code != 200 or "#!/usr/bin/env python3" not in r.text:
            print(f"{RED}[!] Could not fetch remote version.{RESET}")
            return

        # Extract version from __version__ = "x.y.z" (the canonical source)
        remote_ver_match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', r.text)
        remote_ver = remote_ver_match.group(1) if remote_ver_match else None
        local_ver = __version__

        # Refuse to act on a version we can't read. A truncated or mangled
        # response can still contain the shebang checked above, and overwriting
        # this script in place on the strength of an unreadable version string
        # is how you end up with a bricked CLI and no way to recover it.
        cmp = compare_versions(remote_ver, local_ver) if remote_ver else None
        if cmp is None:
            print(f"{RED}[!] Could not read a valid version from the remote script — refusing to update.{RESET}")
            print(f"{CYAN}Download manually if needed: https://github.com/wpa-2/pwnagotchi-store{RESET}")
            return

        if cmp == 0:
            print(f"{GREEN}[+] PwnStore is already up to date (v{local_ver}).{RESET}")
            return
        elif cmp < 0:
            print(f"{GREEN}[+] Local version (v{local_ver}) is ahead of remote (v{remote_ver}). No update needed.{RESET}")
            return

        # Write via a temp file in the same directory, then atomically replace.
        # Truncating the running script in place means an interrupted write
        # (disk full, power cut, dropped connection mid-body) leaves a
        # half-written pwnstore with no way to run it and fix itself.
        current_file = os.path.realpath(__file__)
        tmp_path = current_file + ".pwnstore.tmp"
        with open(tmp_path, 'w') as f:
            f.write(r.text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp_path, 0o755)
        os.replace(tmp_path, current_file)
        print(f"{GREEN}[+] PwnStore updated v{local_ver} -> v{remote_ver}{RESET}")
        print(f"{CYAN}Restart your session to use the new version.{RESET}")
    except Exception as e:
        print(f"{RED}[!] Update failed: {e}{RESET}")

def _get_bundled_plugin_path(name):
    """Check whether `name` is already shipped as a pwnagotchi core default
    plugin on this specific device. Mirrors pwnagotchi's own
    plugins/__init__.py default_path logic (relative to wherever the
    pwnagotchi package is actually installed) rather than a hardcoded path,
    so this stays correct across image versions and install methods.
    Older images that predate a plugin being bundled simply won't find it
    here, and install proceeds normally."""
    try:
        import importlib.util
        spec = importlib.util.find_spec("pwnagotchi.plugins")
        if spec and spec.origin:
            default_dir = os.path.join(os.path.dirname(spec.origin), "default")
            candidate = os.path.join(default_dir, f"{name}.py")
            if os.path.exists(candidate):
                return candidate
    except Exception:
        pass
    return None

def _install_plugin_by_name(name, registry=None):
    """Core install logic used by both install_plugin() and update_plugins()."""
    if not _require_safe_name(name): return False

    bundled_path = _get_bundled_plugin_path(name)
    if bundled_path:
        print(f"{YELLOW}[!] '{name}' is already built into pwnagotchi core on this device.{RESET}")
        print(f"{YELLOW}    Found at: {bundled_path}{RESET}")
        print(f"{YELLOW}    pwnagotchi loads default plugins then custom plugins with no{RESET}")
        print(f"{YELLOW}    collision check, so a second copy here would run alongside it —{RESET}")
        print(f"{YELLOW}    both instances active at once, which can break either or both.{RESET}")
        try:
            confirm = input(f"{YELLOW}    Install a custom copy anyway? [y/N]: {RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            confirm = 'n'
        if confirm != 'y':
            print(f"{CYAN}[*] Skipped — already available as a core plugin.{RESET}")
            print(f"{CYAN}    Just enable it in config.toml: [main.plugins.{name}]{RESET}")
            return False

    if registry is None:
        registry = fetch_registry()

    plugin_data = next((p for p in registry if p.get('name') == name), None)
    if not plugin_data:
        print(f"{RED}[!] Not found.{RESET}")
        return False

    plugin_dir = get_custom_plugin_dir()
    final_file_path = os.path.join(plugin_dir, f"{name}.py")
    already_installed = os.path.exists(final_file_path)
    print(f"[*] Installing {CYAN}{name}{RESET}...")

    try:
        # Ensure plugin directory exists for both zip and single-file installs
        if not os.path.exists(plugin_dir):
            os.makedirs(plugin_dir)

        if plugin_data.get('origin_type') == 'zip':
            # Validate path_inside_zip for traversal attacks
            zip_path = plugin_data.get('path_inside_zip', '')
            if '..' in zip_path or zip_path.startswith('/'):
                print(f"{RED}[!] Refused: suspicious path in zip archive.{RESET}")
                return False

            r = requests.get(plugin_data['download_url'], timeout=30)
            if r.status_code != 200:
                print(f"{RED}[!] Download failed (HTTP {r.status_code}).{RESET}")
                return False
            z = zipfile.ZipFile(io.BytesIO(r.content))
            with z.open(zip_path) as source, open(final_file_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
        else:
            r = requests.get(plugin_data['download_url'], timeout=30)
            if r.status_code != 200:
                print(f"{RED}[!] Download failed (HTTP {r.status_code}).{RESET}")
                return False
            # Sanity check: make sure we didn't get an HTML error page
            if r.text.strip().startswith('<!') or r.text.strip().startswith('<html'):
                print(f"{RED}[!] Download returned an HTML page instead of Python. Check the URL.{RESET}")
                return False
            with open(final_file_path, "wb") as f: f.write(r.content)

        print(f"{GREEN}[+] Installed to {final_file_path}{RESET}")

        # Only write config for a first-time install. Re-enabling on an update
        # would wipe any keys the user has set for this plugin.
        if not already_installed:
            if plugin_has_config(name):
                print(f"{YELLOW}[!] Existing config found — left untouched.{RESET}")
            else:
                update_config(name, enable=True)
                print(f"{GREEN}[+] Enabled in config.toml{RESET}")

            print(f"\n{YELLOW}[!] Configuration may be required{RESET}")
            repo_url = plugin_data.get('download_url', '')
            if '/archive/' in repo_url:
                repo_url = repo_url.split('/archive/')[0]
            print(f"{CYAN}View setup docs: {repo_url}{RESET}")
            print(f"{CYAN}Edit config: {CONFIG_FILE}{RESET}")
        else:
            print(f"{CYAN}[*] Existing config left untouched.{RESET}")
        return True
    except Exception as e:
        print(f"{RED}[!] Failed: {e}{RESET}")
        return False

def update_plugins(args):
    check_sudo()
    print(f"[*] Checking for updates...")
    registry = fetch_registry()

    plugin_dir = get_custom_plugin_dir()
    if not os.path.exists(plugin_dir):
        print(f"{YELLOW}[!] Plugin directory does not exist: {plugin_dir}{RESET}")
        return

    installed_files = [f for f in os.listdir(plugin_dir) if f.endswith(".py")]
    updates_found = []
    for filename in installed_files:
        plugin_name = filename[:-3]
        remote_data = next((p for p in registry if p.get('name') == plugin_name), None)
        if remote_data:
            local_ver = get_local_version(os.path.join(plugin_dir, filename))
            remote_ver = remote_data.get('version', '')
            cmp = compare_versions(remote_ver, local_ver)
            if cmp is not None and cmp > 0:
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
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}[!] Aborted.{RESET}")
            break

        if choice == 's':
            print(f"\n{YELLOW}[!] Skipping remaining updates.{RESET}")
            break
        elif choice in ('n',):
            print(f"  {YELLOW}Skipped.{RESET}\n")
            skipped.append(u['name'])
            continue
        else:
            if _install_plugin_by_name(u['name'], registry=registry):
                print(f"  {CYAN}Check for config changes: {repo_url}{RESET}\n")
                updated.append(u['name'])
            else:
                skipped.append(u['name'])

    if updated:
        print(f"\n{GREEN}[+] Updated: {len(updated)} plugin(s){RESET}")
    if skipped:
        print(f"{YELLOW}[!] Skipped: {len(skipped)} plugin(s){RESET}")
    if updated:
        print(f"{GREEN}[+] Restart Pwnagotchi to activate changes.{RESET}")

def install_plugin(args):
    check_sudo()
    _install_plugin_by_name(args.name)

def uninstall_plugin(args):
    check_sudo()
    if not _require_safe_name(args.name): return
    file_path = os.path.join(get_custom_plugin_dir(), f"{args.name}.py")
    if not os.path.exists(file_path):
        print(f"{YELLOW}[!] Plugin '{args.name}' is not installed.{RESET}")
        return
    try:
        os.remove(file_path)
        print(f"{GREEN}[+] Removed {args.name}.{RESET}")
        remove_plugin_config(args.name)
    except Exception as e:
        print(f"{RED}[!] Failed to remove: {e}{RESET}")

def _strip_plugin_config(lines, plugin_name):
    """Remove every trace of a plugin's config from config.toml lines.

    Pwnagotchi accepts two equivalent forms and older PwnStore versions wrote the
    dotted one, so both must be stripped. Leaving one behind while writing the
    other produces a duplicate key that TOML refuses to parse, which stops
    pwnagotchi from booting:

        main.plugins.foo.enabled = true      <- dotted
        [main.plugins.foo]                   <- section
        enabled = true
    """
    section_header = f"[main.plugins.{plugin_name}]"
    dotted_prefix = f"main.plugins.{plugin_name}."
    kept = []
    inside_section = False
    for line in lines:
        stripped = line.strip()
        if stripped == section_header:
            inside_section = True
            continue
        # Any new table header ends the section we're skipping.
        if inside_section and stripped.startswith("["):
            inside_section = False
        if inside_section:
            continue
        if stripped.startswith(dotted_prefix):
            continue
        kept.append(line)
    return kept

def plugin_has_config(plugin_name):
    """True if config.toml already has settings for this plugin."""
    try:
        if not os.path.exists(CONFIG_FILE): return False
        with open(CONFIG_FILE, "r", errors='ignore') as f: lines = f.readlines()
        return len(_strip_plugin_config(lines, plugin_name)) != len(lines)
    except Exception:
        return False

def update_config(plugin_name, enable=True):
    """Enable a plugin in config.toml without touching the user's own settings.

    Only ever called for a fresh install or an uninstall, never on update -- an
    update must not clobber keys the user has set (API tokens, VPN keys, display
    positions). Rewrites are done via a temp file so an interrupted write can't
    leave a truncated config behind.
    """
    try:
        if not os.path.exists(CONFIG_FILE): return
        with open(CONFIG_FILE, "r", errors='ignore') as f: lines = f.readlines()

        new_lines = _strip_plugin_config(lines, plugin_name)

        if enable:
            if new_lines and not new_lines[-1].endswith('\n'): new_lines[-1] += '\n'
            new_lines.append(f"\n[main.plugins.{plugin_name}]\nenabled = true\n")

        tmp_path = CONFIG_FILE + ".pwnstore.tmp"
        with open(tmp_path, "w") as f:
            f.writelines(new_lines)
            f.flush()
            os.fsync(f.fileno())
        shutil.copymode(CONFIG_FILE, tmp_path)
        os.replace(tmp_path, CONFIG_FILE)
    except Exception as e:
        print(f"{RED}[!] Config update failed for {plugin_name}: {e}{RESET}")

def remove_plugin_config(plugin_name):
    """Remove the plugin's config from config.toml (both dotted and section form)."""
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
    print(f"{CYAN}PwnStore - Pwnagotchi Plugin Manager v{__version__}{RESET}\n")

    print(f"{YELLOW}BROWSE PLUGINS:{RESET}")
    print(f"  {CYAN}pwnstore list{RESET}                    List all available plugins")
    print(f"  {CYAN}pwnstore search <query>{RESET}          Search for plugins")
    print(f"  {CYAN}pwnstore info <n>{RESET}             Show plugin details")
    print(f"  {CYAN}pwnstore sources{RESET}                 Show repository sources\n")

    print(f"{YELLOW}MANAGE PLUGINS:{RESET}")
    print(f"  {GREEN}sudo pwnstore install <n>{RESET}     Install a plugin")
    print(f"  {RED}sudo pwnstore uninstall <n>{RESET}   Remove a plugin\n")

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
    print(f"  {CYAN}info{RESET} <n>       View detailed plugin information")
    print(f"  {GREEN}install{RESET} <n>    Install a plugin (requires sudo)")
    print(f"  {RED}uninstall{RESET} <n>  Remove a plugin (requires sudo)")
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
