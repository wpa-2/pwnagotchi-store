"""
PwnStore UI - Plugin Store for Pwnagotchi
Browse and install plugins directly from the web UI

Author: WPA2
Version: see __version__ on PwnStoreUI below
"""

import logging
import json
import subprocess
import requests
import os
import re
import secrets
import hmac
import _thread
from flask import request, Response

import pwnagotchi.plugins as plugins


def is_safe_name(name):
    """Security: Prevents path traversal and command injection"""
    return bool(name) and re.match(r'^[a-zA-Z0-9_-]+$', name) is not None


class PwnStoreUI(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '1.2.11'
    __license__ = 'GPL3'
    __description__ = 'Plugin store with web interface for browsing and installing plugins'

    def __init__(self):
        self.ready = False
        self.store_url = "https://raw.githubusercontent.com/wpa-2/pwnagotchi-store/main/plugins.json"
        # Random per-process secret, embedded in the page and required back on
        # every state-changing request. Regenerated on every pwnagotchi
        # restart -- that's fine, it only needs to match what _render_store()
        # hands out for the lifetime of this process. This replaces the old
        # flask_wtf-based token, which was generated but never actually
        # checked on the way back in.
        self._csrf_token = secrets.token_hex(32)

    def _csrf_valid(self, request):
        token = request.headers.get('X-CSRFToken', '')
        return hmac.compare_digest(token, self._csrf_token)

    def on_loaded(self):
        logging.info("[pwnstore_ui] Plugin loaded")
        self.ready = True

    def _get_custom_plugin_dir(self):
        """Read custom_plugins path from config.toml, matching pwnstore CLI behaviour."""
        config_file = "/etc/pwnagotchi/config.toml"
        default = "/etc/pwnagotchi/custom-plugins"
        try:
            with open(config_file, 'r') as f:
                cfg = f.read()
            match = re.search(r"(?:main\.)?custom_plugins\s*=\s*[\"'](.+?)[\"']", cfg)
            if match:
                return match.group(1).rstrip('/')
        except Exception:
            pass
        return default

    # NOTE: All webhook endpoints are served behind pwnagotchi's built-in
    # web UI basic auth (configured by default), which is the only access
    # control on the read-only routes. The state-changing routes below also
    # require POST + a matching CSRF token, since Basic Auth alone doesn't
    # stop a third-party page from riding the browser's cached credentials.

    def on_webhook(self, path, request):
        """Handle web requests to /plugins/pwnstore_ui/"""
        if path == "/" or path == "" or not path:
            html = self._render_store()
            return Response(html, mimetype='text/html')
        elif path == "api/plugins":
            return self._get_plugins()
        elif path == "api/installed":
            return self._get_installed()
        elif path in ("api/install", "api/uninstall", "api/configure", "api/restart"):
            # These change state on the device (write files, run pwnstore,
            # restart the service), so they must arrive as a POST carrying
            # the token _render_store() handed out. Without this check, any
            # page loaded in a browser that's already authenticated to the
            # pwnagotchi web UI (basic auth is cached per-origin, not per-tab)
            # could trigger them cross-site -- a plain <img> tag is enough
            # for a GET, and a text/plain form POST is enough to reach
            # get_json(force=True) on the JSON endpoints.
            if request.method != 'POST':
                return Response(json.dumps({'success': False, 'error': 'Method not allowed'}),
                               status=405, mimetype='application/json')
            if not self._csrf_valid(request):
                return Response(json.dumps({'success': False, 'error': 'Invalid or missing CSRF token'}),
                               status=403, mimetype='application/json')
            if path == "api/install":
                return self._install_plugin(request)
            elif path == "api/uninstall":
                return self._uninstall_plugin(request)
            elif path == "api/configure":
                return self._configure_plugin(request)
            elif path == "api/restart":
                return self._restart_pwnagotchi()
        return Response("Not found", status=404)

    def _render_store(self):
        """Render the main store interface"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="csrf-token" content="__CSRF_TOKEN__">
    <title>PwnStore - Plugin Gallery</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Courier New', monospace; background: #000; color: #0f0; padding: 10px; overflow-x: hidden; }
        .header { text-align: center; padding: 15px 10px; border-bottom: 2px solid #0f0; margin-bottom: 20px; }
        .ascii-logo { font-size: 10px; line-height: 1.2; white-space: pre; color: #0f0; margin-bottom: 10px; }
        h1 { font-size: 20px; margin: 10px 0; color: #0f0; }
        .donate-btn { display: inline-block; margin: 10px 0; padding: 8px 16px; background: #0f0; color: #000; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 12px; transition: all 0.3s; }
        .donate-btn:hover { background: #fff; transform: scale(1.05); }
        .search-bar { width: 100%; max-width: 500px; margin: 15px auto; display: block; padding: 10px; background: #111; border: 2px solid #0f0; color: #0f0; font-family: 'Courier New', monospace; font-size: 14px; }
        .filters { text-align: center; margin: 15px 0; display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
        .filter-btn { padding: 8px 15px; background: #111; border: 2px solid #0f0; color: #0f0; cursor: pointer; font-family: 'Courier New', monospace; font-size: 12px; transition: all 0.3s; }
        .filter-btn:hover, .filter-btn.active { background: #0f0; color: #000; }
        .stats { text-align: center; margin: 15px 0; font-size: 12px; color: #0f0; }
        .plugins-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; padding: 10px; }
        @media (max-width: 600px) { .plugins-grid { grid-template-columns: 1fr; } }
        .plugin-card { background: #111; border: 2px solid #0f0; padding: 15px; transition: all 0.3s; position: relative; }
        .plugin-card:hover { border-color: #fff; box-shadow: 0 0 15px #0f0; }
        .plugin-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px; }
        .plugin-name { font-size: 16px; font-weight: bold; color: #0f0; }
        .plugin-category { font-size: 10px; padding: 3px 8px; background: #0f0; color: #000; border-radius: 3px; }
        .plugin-author { font-size: 11px; color: #0a0; margin: 5px 0; }
        .plugin-description { font-size: 12px; color: #0f0; margin: 10px 0; line-height: 1.4; }
        .plugin-actions { display: flex; gap: 8px; margin-top: 10px; }
        .btn { flex: 1; padding: 8px; border: 1px solid #0f0; background: #000; color: #0f0; cursor: pointer; font-family: 'Courier New', monospace; font-size: 11px; transition: all 0.3s; }
        .btn:hover { background: #0f0; color: #000; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-uninstall { border-color: #f00; color: #f00; }
        .btn-uninstall:hover { background: #f00; color: #000; }
        .btn-info { flex: 0 0 auto; padding: 8px 12px; }
        .status-badge { position: absolute; top: 10px; right: 10px; font-size: 10px; padding: 3px 8px; border-radius: 3px; font-weight: bold; }
        .installed { background: #0f0; color: #000; }
        .loading { text-align: center; padding: 40px; font-size: 16px; color: #0f0; }
        .message { position: fixed; top: 20px; right: 20px; padding: 15px 20px; border: 2px solid #0f0; background: #000; color: #0f0; font-size: 12px; z-index: 6000; max-width: 300px; animation: slideIn 0.3s; }
        @keyframes slideIn { from { transform: translateX(400px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
        .footer { text-align: center; padding: 20px; margin-top: 30px; border-top: 2px solid #0f0; font-size: 11px; }

        .modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.9); display: flex; align-items: center; justify-content: center; z-index: 8000; padding: 20px; }
        .modal-content { background: #000; border: 3px solid #0f0; padding: 25px; max-width: 500px; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 0 30px #0f0; }
        .modal-content h2 { font-size: 20px; color: #0f0; margin-bottom: 10px; text-align: center; }
        .modal-content p { font-size: 13px; color: #0a0; text-align: center; margin-bottom: 10px; }
        .modal-content .detail-row { margin: 8px 0; font-size: 12px; }
        .modal-content .detail-label { color: #0a0; }
        .config-field { display: flex; flex-direction: column; gap: 5px; margin-bottom: 15px; }
        .config-field label { color: #0f0; font-size: 13px; font-weight: bold; }
        .config-field input { padding: 10px; background: #111; border: 2px solid #0f0; color: #0f0; font-family: 'Courier New', monospace; }
        .modal-btn { padding: 12px; border: 2px solid #0f0; background: #000; color: #0f0; cursor: pointer; font-family: 'Courier New', monospace; width: 100%; margin-top: 10px; }
        .modal-btn:hover { background: #0f0; color: #000; }
        .modal-btn-secondary { border-color: #555; color: #888; }
    </style>
</head>
<body>
    <div class="header">
        <div class="ascii-logo">(&#x25D5;&#x203F;&#x203F;&#x25D5;)</div>
        <h1>&#x1F6D2; PwnStore</h1>
        <p style="font-size: 12px;">Plugin Gallery &amp; Manager</p>
        <div style="display: flex; justify-content: center; gap: 10px;">
            <a href="https://buymeacoffee.com/wpa2" target="_blank" class="donate-btn">&#x2615; Support Dev</a>
            <button class="donate-btn" id="restartBtn" style="background: #f00;">&#x1F504; Restart Service</button>
        </div>
    </div>

    <input type="text" id="searchBox" class="search-bar" placeholder="&#x1F50D; Search plugins...">

    <div class="filters" id="filtersContainer">
        <button class="filter-btn active" data-category="all">All</button>
    </div>

    <div class="stats"><span id="pluginCount">Loading plugins...</span></div>
    <div id="pluginsContainer" class="plugins-grid"></div>

    <div class="footer">Built by <strong>WPA2</strong> &bull; v__PLUGIN_VERSION__ &bull; <a href="https://github.com/wpa-2/pwnagotchi-store" style="color: #0f0;">GitHub</a></div>

    <script>
        let allPlugins = [];
        let installedPlugins = [];
        let currentCategory = 'all';
        let searchTerm = '';

        // --- Security: HTML escaping for all dynamic content ---
        // Escapes " and ' too, not just & < > -- this string gets interpolated
        // into both element text AND attribute values below (data-name=,
        // data-plugin=), and a plugin name/author/description containing a
        // literal quote could otherwise break out of those attributes.
        function escHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function getCSRFToken() {
            const meta = document.querySelector('meta[name="csrf-token"]');
            return meta ? meta.getAttribute('content') : '';
        }

        async function apiRequest(url, options = {}) {
            const headers = { 'Content-Type': 'application/json', ...options.headers };
            if (options.method === 'POST') {
                const token = getCSRFToken();
                if (token) headers['X-CSRFToken'] = token;
            }
            try {
                const response = await fetch(url, { ...options, headers });
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                return await response.json();
            } catch (e) {
                showMessage('Request failed: ' + e.message, 'error');
                return null;
            }
        }

        async function restartService() {
            if (!confirm('Restart Pwnagotchi service to apply all changes?')) return;
            showMessage('Restarting service... please wait.', 'success');
            await apiRequest('/plugins/pwnstore_ui/api/restart', { method: 'POST' });
            setTimeout(() => { location.reload(); }, 5000);
        }

        function buildFilters() {
            const cats = new Set();
            allPlugins.forEach(p => { if (p.category) cats.add(p.category); });
            const container = document.getElementById('filtersContainer');
            container.innerHTML = '<button class="filter-btn active" data-category="all">All</button>';
            Array.from(cats).sort().forEach(cat => {
                const btn = document.createElement('button');
                btn.className = 'filter-btn';
                btn.dataset.category = cat;
                btn.textContent = cat;
                container.appendChild(btn);
            });
        }

        async function loadData() {
            try {
                const [pluginsData, installedData] = await Promise.all([
                    apiRequest('/plugins/pwnstore_ui/api/plugins'),
                    apiRequest('/plugins/pwnstore_ui/api/installed')
                ]);
                allPlugins = pluginsData || [];
                installedPlugins = installedData || [];
                buildFilters();
                renderPlugins();
            } catch (e) { showMessage('Load failed', 'error'); }
        }

        function renderPlugins() {
            const container = document.getElementById('pluginsContainer');
            let filtered = allPlugins.filter(p => {
                const cat = currentCategory === 'all' || p.category === currentCategory;
                const search = !searchTerm || p.name.toLowerCase().includes(searchTerm) || (p.description || '').toLowerCase().includes(searchTerm);
                return cat && search;
            });
            document.getElementById('pluginCount').textContent = 'Showing ' + filtered.length + ' plugins';
            container.innerHTML = filtered.map(p => {
                const isInst = installedPlugins.includes(p.name);
                const safeName = escHtml(p.name);
                const safeAuthor = escHtml(p.author);
                const safeDesc = escHtml(p.description || '');
                const safeVersion = escHtml(p.version || '');
                return '<div class="plugin-card" data-name="' + safeName + '">'
                    + (isInst ? '<span class="status-badge installed">&#x2713; INSTALLED</span>' : '')
                    + '<div class="plugin-header"><div class="plugin-name">' + safeName + '</div></div>'
                    + '<div class="plugin-author">by ' + safeAuthor + ' &bull; v' + safeVersion + '</div>'
                    + '<div class="plugin-description">' + safeDesc + '</div>'
                    + '<div class="plugin-actions">'
                    + (isInst
                        ? '<button class="btn btn-uninstall" data-action="uninstall" data-plugin="' + safeName + '">Uninstall</button>'
                        : '<button class="btn" data-action="install" data-plugin="' + safeName + '">Install</button>')
                    + '<button class="btn btn-info" data-action="info" data-plugin="' + safeName + '">&#x2139;&#xFE0F;</button>'
                    + '</div></div>';
            }).join('');
        }

        async function installPlugin(name) {
            showMessage('Installing ' + escHtml(name) + '...', 'success');
            const res = await apiRequest('/plugins/pwnstore_ui/api/install', { method: 'POST', body: JSON.stringify({ plugin: name }) });
            if (res && res.success) {
                if (!installedPlugins.includes(name)) installedPlugins.push(name);
                renderPlugins();
                if (res.repo_url) {
                    showConfigModal(name, res.repo_url);
                } else {
                    showMessage(escHtml(name) + ' installed! Restart Pwnagotchi to activate.', 'success');
                }
            } else {
                const detail = (res && res.error) ? ': ' + escHtml(res.error) : '';
                showMessage('Install failed' + detail, 'error');
            }
        }

        async function uninstallPlugin(name) {
            if (!confirm('Remove ' + name + '?')) return;
            const res = await apiRequest('/plugins/pwnstore_ui/api/uninstall', { method: 'POST', body: JSON.stringify({ plugin: name }) });
            if (res && res.success) {
                installedPlugins = installedPlugins.filter(p => p !== name);
                renderPlugins();
                showMessage('Removed', 'success');
            } else {
                const detail = (res && res.error) ? ': ' + escHtml(res.error) : '';
                showMessage('Uninstall failed' + detail, 'error');
            }
        }

        function showConfigModal(name, repoUrl) {
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.id = 'configOverlay';
            const modal = document.createElement('div');
            modal.className = 'modal-content';
            const h2 = document.createElement('h2');
            h2.textContent = '\u2699\uFE0F ' + name + ' installed!';
            modal.appendChild(h2);
            const p = document.createElement('p');
            p.textContent = 'Configuration may be required';
            modal.appendChild(p);
            const info = document.createElement('p');
            info.style.marginBottom = '15px';
            info.innerHTML = 'Edit <code>/etc/pwnagotchi/config.toml</code> to configure this plugin.';
            modal.appendChild(info);
            if (repoUrl) {
                const a = document.createElement('a');
                // Only allow http/https links to prevent javascript: XSS
                if (repoUrl.startsWith('http://') || repoUrl.startsWith('https://')) {
                    a.href = repoUrl;
                } else {
                    a.href = '#';
                }
                a.target = '_blank';
                a.className = 'modal-btn';
                a.style.display = 'inline-block';
                a.style.textDecoration = 'none';
                a.textContent = String.fromCodePoint(0x1F4D6) + ' View Setup Instructions';
                modal.appendChild(a);
            }
            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'modal-btn modal-btn-secondary';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', () => overlay.remove());
            modal.appendChild(closeBtn);
            overlay.appendChild(modal);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
            document.body.appendChild(overlay);
        }

        function showInfo(name) {
            const p = allPlugins.find(x => x.name === name);
            if (!p) return;
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            const modal = document.createElement('div');
            modal.className = 'modal-content';
            const h2 = document.createElement('h2');
            h2.textContent = p.name;
            modal.appendChild(h2);
            const fields = [
                ['Author', p.author],
                ['Version', p.version],
                ['Category', p.category || 'General'],
                ['Description', p.description]
            ];
            fields.forEach(([label, value]) => {
                const row = document.createElement('div');
                row.className = 'detail-row';
                const lbl = document.createElement('span');
                lbl.className = 'detail-label';
                lbl.textContent = label + ': ';
                row.appendChild(lbl);
                row.appendChild(document.createTextNode(value || 'N/A'));
                modal.appendChild(row);
            });
            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'modal-btn modal-btn-secondary';
            closeBtn.textContent = 'Close';
            closeBtn.addEventListener('click', () => overlay.remove());
            modal.appendChild(closeBtn);
            overlay.appendChild(modal);
            overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
            document.body.appendChild(overlay);
        }

        function showMessage(text, type) {
            const m = document.createElement('div');
            m.className = 'message ' + type;
            m.textContent = text;
            document.body.appendChild(m);
            setTimeout(() => m.remove(), 4000);
        }

        // --- Event delegation: single listener for all plugin actions ---
        document.getElementById('pluginsContainer').addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const action = btn.dataset.action;
            const plugin = btn.dataset.plugin;
            if (action === 'install') installPlugin(plugin);
            else if (action === 'uninstall') uninstallPlugin(plugin);
            else if (action === 'info') showInfo(plugin);
        });

        // --- Event delegation for filter buttons ---
        document.getElementById('filtersContainer').addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;
            document.querySelectorAll('.filter-btn').forEach(x => x.classList.remove('active'));
            btn.classList.add('active');
            currentCategory = btn.dataset.category;
            renderPlugins();
        });

        document.getElementById('searchBox').oninput = (e) => { searchTerm = e.target.value.toLowerCase(); renderPlugins(); };
        document.getElementById('restartBtn').addEventListener('click', restartService);
        loadData();
    </script>
</body>
</html>
        """
        html = html.replace('__CSRF_TOKEN__', self._csrf_token)
        html = html.replace('__PLUGIN_VERSION__', self.__version__)
        return html

    def _restart_pwnagotchi(self):
        """Triggers a service restart in a separate thread"""
        def run_restart():
            import time
            time.sleep(1)
            subprocess.run(['systemctl', 'restart', 'pwnagotchi'])

        _thread.start_new_thread(run_restart, ())
        return Response(json.dumps({'success': True}), mimetype='application/json')

    def _configure_plugin(self, request):
        """API-only endpoint — not currently called by the frontend UI.
        Kept for direct API consumers and future use.
        POST JSON: {"plugin": "name", "config": {"key": "value", ...}}
        """
        try:
            data = request.get_json(force=True)
            name, vals = data.get('plugin'), data.get('config') or {}
            if not is_safe_name(name):
                return Response(json.dumps({'success': False, 'error': 'Invalid plugin name'}),
                               status=400, mimetype='application/json')
            config_file = "/etc/pwnagotchi/config.toml"
            section_header = f"[main.plugins.{name}]"
            with open(config_file, 'r') as f:
                lines = f.readlines()
            # Remove existing section and all its keys
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
            # Append new section in correct TOML format
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'
            new_lines.append(f"\n{section_header}\n")
            new_lines.append("enabled = true\n")
            for k, v in vals.items():
                if k == 'enabled': continue
                # Validate config key names
                if not re.match(r'^[a-zA-Z0-9_]+$', k): continue
                v_str = str(v).strip()

                # Boolean
                if v_str.lower() in ('true', 'false'):
                    new_lines.append(f"{k} = {v_str.lower()}\n")
                # Integer (TOML forbids leading zeros, e.g. "007")
                elif v_str.lstrip('-').isdigit() and (v_str.lstrip('-') == '0' or not v_str.lstrip('-').startswith('0')):
                    new_lines.append(f"{k} = {v_str}\n")
                # Float (e.g. 1.5, 0.75) — same no-leading-zero rule on the integer part
                elif re.match(r'^-?(0|[1-9]\d*)\.\d+$', v_str):
                    new_lines.append(f"{k} = {v_str}\n")
                # Array — validate it only contains safe TOML primitives, reject newlines
                elif v_str.startswith('[') and v_str.endswith(']'):
                    depth = 0
                    balanced = True
                    for ch in v_str:
                        if ch == '[':
                            depth += 1
                        elif ch == ']':
                            depth -= 1
                            if depth < 0:
                                balanced = False
                                break
                    if ('\n' in v_str or '\r' in v_str or depth != 0 or not balanced
                            or v_str.count('[') > 1):
                        # Reject arrays containing newlines, nested/multiple brackets,
                        # or unbalanced brackets (TOML injection/corruption)
                        continue
                    new_lines.append(f"{k} = {v_str}\n")
                else:
                    # String — escape any embedded quotes and backslashes
                    safe_v = v_str.replace('\\', '\\\\').replace('"', '\\"')
                    safe_v = safe_v.replace('\n', '').replace('\r', '')
                    new_lines.append(f'{k} = "{safe_v}"\n')

            with open(config_file, 'w') as f:
                f.writelines(new_lines)
            return Response(json.dumps({'success': True}), mimetype='application/json')
        except Exception as e:
            return Response(json.dumps({'success': False, 'error': str(e)}), status=500,
                           mimetype='application/json')

    def _get_plugins(self):
        try:
            r = requests.get(self.store_url, timeout=10)
            if r.status_code != 200:
                logging.warning(f"[pwnstore_ui] Store returned HTTP {r.status_code}")
                return Response("[]", mimetype='application/json')
            return Response(r.text, mimetype='application/json')
        except Exception:
            return Response("[]", mimetype='application/json')

    def _get_installed(self):
        path = self._get_custom_plugin_dir()
        if not os.path.exists(path): return Response("[]", mimetype='application/json')
        files = [f.replace('.py', '') for f in os.listdir(path) if f.endswith('.py')]
        return Response(json.dumps(files), mimetype='application/json')

    def _install_plugin(self, request):
        data = request.get_json(force=True)
        name = data.get('plugin', '')
        if not is_safe_name(name):
            return Response(json.dumps({'success': False, 'error': 'Invalid plugin name'}),
                           status=400, mimetype='application/json')

        # Validate plugin exists in registry first, get repo URL in same fetch
        repo_url = ''
        try:
            r = requests.get(self.store_url, timeout=10)
            plugin_list = r.json()
            plugin_data = next((p for p in plugin_list if p['name'] == name), None)
            if not plugin_data:
                return Response(json.dumps({'success': False, 'error': 'Plugin not found in registry'}),
                               status=404, mimetype='application/json')
            repo_url = plugin_data.get('download_url', '')
            if '/archive/' in repo_url:
                repo_url = repo_url.split('/archive/')[0]
        except Exception:
            pass

        result = subprocess.run(['pwnstore', 'install', name], capture_output=True, text=True)

        error_detail = ''
        if result.returncode != 0:
            error_detail = (result.stderr or result.stdout or '').strip()

        return Response(json.dumps({
            'success': result.returncode == 0,
            'repo_url': repo_url,
            'error': error_detail
        }), mimetype='application/json')

    def _uninstall_plugin(self, request):
        data = request.get_json(force=True)
        name = data.get('plugin', '')
        if not is_safe_name(name):
            return Response(json.dumps({'success': False, 'error': 'Invalid plugin name'}),
                           status=400, mimetype='application/json')
        result = subprocess.run(['pwnstore', 'uninstall', name], capture_output=True, text=True)
        success = result.returncode == 0
        error_detail = ''
        if not success:
            error_detail = (result.stderr or result.stdout or '').strip()
        return Response(json.dumps({'success': success, 'error': error_detail}),
                       mimetype='application/json')
