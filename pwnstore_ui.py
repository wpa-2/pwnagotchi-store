import logging
import json
import subprocess
import requests
import os
from flask import render_template_string, request, jsonify, Response

import pwnagotchi.plugins as plugins

# Try to import csrf_exempt if available
try:
    from flask_wtf.csrf import CSRFProtect
    from flask_wtf import csrf
    CSRF_AVAILABLE = True
except ImportError:
    CSRF_AVAILABLE = False


class PwnStoreUI(plugins.Plugin):
    __author__ = 'WPA2'
    __version__ = '1'
    __license__ = 'GPL3'
    __description__ = 'Plugin store with web interface for browsing and installing plugins'

    def __init__(self):
        self.ready = False
        self.store_url = "https://raw.githubusercontent.com/wpa-2/pwnagotchi-store/main/plugins.json"
        
    def on_loaded(self):
        logging.info("[pwnstore_ui] Plugin loaded")
        self.ready = True

    def on_webhook(self, path, request):
        """Handle web requests to /plugins/pwnstore_ui/"""
        
        # Main store page
        if path == "/" or path == "" or not path:
            html = self._render_store()
            return Response(html, mimetype='text/html')
        
        # API endpoint to fetch plugins
        elif path == "api/plugins":
            return self._get_plugins()
        
        # API endpoint to install plugin
        elif path == "api/install":
            return self._install_plugin(request)
        
        # API endpoint to uninstall plugin
        elif path == "api/uninstall":
            return self._uninstall_plugin(request)
        
        # API endpoint to get installed plugins
        elif path == "api/installed":
            return self._get_installed()
        
        # 404 for unknown paths
        return Response("Not found", status=404)

    def _render_store(self):
        """Render the main store interface"""
        # Try to get CSRF token if available
        csrf_token = ''
        try:
            from flask_wtf.csrf import generate_csrf
            csrf_token = generate_csrf()
        except:
            pass
        
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="csrf-token" content="__CSRF_TOKEN__">
    <title>PwnStore - Plugin Gallery</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Courier New', monospace;
            background: #000;
            color: #0f0;
            padding: 10px;
            overflow-x: hidden;
        }

        .header {
            text-align: center;
            padding: 15px 10px;
            border-bottom: 2px solid #0f0;
            margin-bottom: 20px;
        }

        .ascii-logo {
            font-size: 10px;
            line-height: 1.2;
            white-space: pre;
            color: #0f0;
            margin-bottom: 10px;
        }

        h1 {
            font-size: 20px;
            margin: 10px 0;
            color: #0f0;
        }

        .donate-btn {
            display: inline-block;
            margin: 10px 0;
            padding: 8px 16px;
            background: #0f0;
            color: #000;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            font-size: 12px;
            transition: all 0.3s;
        }

        .donate-btn:hover {
            background: #fff;
            transform: scale(1.05);
        }

        .search-bar {
            width: 100%;
            max-width: 500px;
            margin: 15px auto;
            display: block;
            padding: 10px;
            background: #111;
            border: 2px solid #0f0;
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }

        .filters {
            text-align: center;
            margin: 15px 0;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px;
        }

        .filter-btn {
            padding: 8px 15px;
            background: #111;
            border: 2px solid #0f0;
            color: #0f0;
            cursor: pointer;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            transition: all 0.3s;
        }

        .filter-btn:hover, .filter-btn.active {
            background: #0f0;
            color: #000;
        }

        .stats {
            text-align: center;
            margin: 15px 0;
            font-size: 12px;
            color: #0f0;
        }

        .plugins-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 15px;
            padding: 10px;
        }

        @media (max-width: 600px) {
            .plugins-grid {
                grid-template-columns: 1fr;
            }
        }

        .plugin-card {
            background: #111;
            border: 2px solid #0f0;
            padding: 15px;
            transition: all 0.3s;
            position: relative;
        }

        .plugin-card:hover {
            border-color: #fff;
            box-shadow: 0 0 15px #0f0;
        }

        .plugin-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 10px;
        }

        .plugin-name {
            font-size: 16px;
            font-weight: bold;
            color: #0f0;
        }

        .plugin-category {
            font-size: 10px;
            padding: 3px 8px;
            background: #0f0;
            color: #000;
            border-radius: 3px;
        }

        .plugin-author {
            font-size: 11px;
            color: #0a0;
            margin: 5px 0;
        }

        .plugin-description {
            font-size: 12px;
            color: #0f0;
            margin: 10px 0;
            line-height: 1.4;
        }

        .plugin-actions {
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }

        .btn {
            flex: 1;
            padding: 8px;
            border: 1px solid #0f0;
            background: #000;
            color: #0f0;
            cursor: pointer;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            transition: all 0.3s;
        }

        .btn:hover {
            background: #0f0;
            color: #000;
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-install {
            border-color: #0f0;
        }

        .btn-uninstall {
            border-color: #f00;
            color: #f00;
        }

        .btn-uninstall:hover {
            background: #f00;
            color: #000;
        }

        .btn-info {
            flex: 0 0 auto;
            padding: 8px 12px;
        }

        .status-badge {
            position: absolute;
            top: 10px;
            right: 10px;
            font-size: 10px;
            padding: 3px 8px;
            border-radius: 3px;
            font-weight: bold;
        }

        .installed {
            background: #0f0;
            color: #000;
        }

        .loading {
            text-align: center;
            padding: 40px;
            font-size: 16px;
            color: #0f0;
        }

        .message {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border: 2px solid #0f0;
            background: #000;
            color: #0f0;
            font-size: 12px;
            z-index: 1000;
            max-width: 300px;
            animation: slideIn 0.3s;
        }

        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        .message.success {
            border-color: #0f0;
        }

        .message.error {
            border-color: #f00;
            color: #f00;
        }

        .footer {
            text-align: center;
            padding: 20px;
            margin-top: 30px;
            border-top: 2px solid #0f0;
            font-size: 11px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="ascii-logo">(◕‿‿◕)</div>
        <h1>🛒 PwnStore</h1>
        <p style="font-size: 12px;">Plugin Gallery & Manager</p>
        <a href="https://buymeacoffee.com/wpa2" target="_blank" class="donate-btn">☕ Support Dev</a>
    </div>

    <input type="text" id="searchBox" class="search-bar" placeholder="🔍 Search plugins...">

    <div class="filters">
        <button class="filter-btn active" data-category="all">All</button>
        <button class="filter-btn" data-category="Display">Display</button>
        <button class="filter-btn" data-category="GPS">GPS</button>
        <button class="filter-btn" data-category="Social">Social</button>
        <button class="filter-btn" data-category="Hardware">Hardware</button>
        <button class="filter-btn" data-category="Attack">Attack</button>
        <button class="filter-btn" data-category="System">System</button>
    </div>

    <div class="stats">
        <span id="pluginCount">Loading plugins...</span>
    </div>

    <div id="pluginsContainer" class="plugins-grid">
        <div class="loading">⏳ Loading plugins from store...</div>
    </div>

    <div class="footer">
        Built by <strong>WPA2</strong> • v3.0 • 
        <a href="https://github.com/wpa-2/pwnagotchi-store" style="color: #0f0;">GitHub</a>
    </div>

    <script>
        let allPlugins = [];
        let installedPlugins = [];
        let currentCategory = 'all';
        let searchTerm = '';

        // Get CSRF token from meta tag
        function getCSRFToken() {
            const meta = document.querySelector('meta[name="csrf-token"]');
            return meta ? meta.getAttribute('content') : '';
        }

        // Helper to make API requests with proper headers
        async function apiRequest(url, options = {}) {
            const headers = {
                'Content-Type': 'application/json',
                ...options.headers
            };

            // Add CSRF token for POST requests
            if (options.method === 'POST') {
                const csrfToken = getCSRFToken();
                if (csrfToken) {
                    headers['X-CSRFToken'] = csrfToken;
                }
            }

            const response = await fetch(url, {
                ...options,
                headers
            });

            // Check if response is actually JSON
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                // If we got HTML or something else, throw an error
                const text = await response.text();
                console.error('Non-JSON response:', text);
                throw new Error(`Server returned an error (status ${response.status})`);
            }
        }

        // Load plugins and installed list
        async function loadData() {
            try {
                // Load plugins from store
                allPlugins = await apiRequest('/plugins/pwnstore_ui/api/plugins');

                // Load installed plugins
                installedPlugins = await apiRequest('/plugins/pwnstore_ui/api/installed');

                renderPlugins();
            } catch (error) {
                console.error('Load error:', error);
                showMessage('Failed to load plugins: ' + error.message, 'error');
            }
        }

        function renderPlugins() {
            const container = document.getElementById('pluginsContainer');
            
            // Filter plugins
            let filtered = allPlugins.filter(plugin => {
                const matchesCategory = currentCategory === 'all' || plugin.category === currentCategory;
                const matchesSearch = !searchTerm || 
                    plugin.name.toLowerCase().includes(searchTerm) ||
                    plugin.description.toLowerCase().includes(searchTerm) ||
                    plugin.author.toLowerCase().includes(searchTerm);
                return matchesCategory && matchesSearch;
            });

            // Update stats
            document.getElementById('pluginCount').textContent = 
                `Showing ${filtered.length} of ${allPlugins.length} plugins`;

            // Render cards
            if (filtered.length === 0) {
                container.innerHTML = '<div class="loading">No plugins found 😢</div>';
                return;
            }

            container.innerHTML = filtered.map(plugin => {
                const isInstalled = installedPlugins.includes(plugin.name);
                return `
                    <div class="plugin-card" data-name="${plugin.name}">
                        ${isInstalled ? '<span class="status-badge installed">✓ INSTALLED</span>' : ''}
                        <div class="plugin-header">
                            <div class="plugin-name">${plugin.name}</div>
                            <div class="plugin-category">${plugin.category}</div>
                        </div>
                        <div class="plugin-author">by ${plugin.author}</div>
                        <div class="plugin-description">${plugin.description || 'No description available'}</div>
                        <div class="plugin-actions">
                            ${isInstalled ? 
                                `<button class="btn btn-uninstall" onclick="uninstallPlugin('${plugin.name}')">Uninstall</button>` :
                                `<button class="btn btn-install" onclick="installPlugin('${plugin.name}')">Install</button>`
                            }
                            <button class="btn btn-info" onclick="showInfo('${plugin.name}')">ℹ️</button>
                        </div>
                    </div>
                `;
            }).join('');
        }

        async function installPlugin(name) {
            const card = document.querySelector(`[data-name="${name}"]`);
            const btn = card.querySelector('.btn-install');
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = '⏳ Installing...';

            try {
                const result = await apiRequest('/plugins/pwnstore_ui/api/install', {
                    method: 'POST',
                    body: JSON.stringify({ plugin: name })
                });

                if (result.success) {
                    // Check if it was a reinstall
                    if (result.reinstall) {
                        showMessage(`✓ ${name} reinstalled! Config updated. Restart required.`, 'success');
                    } else {
                        showMessage(`✓ ${name} installed! Restart required.`, 'success');
                    }
                    
                    // Add to installed list if not already there
                    if (!installedPlugins.includes(name)) {
                        installedPlugins.push(name);
                    }
                    renderPlugins();
                } else {
                    showMessage(`✗ Install failed: ${result.error || 'Unknown error'}`, 'error');
                    btn.disabled = false;
                    btn.textContent = originalText;
                }
            } catch (error) {
                console.error('Install error:', error);
                showMessage(`✗ Install error: ${error.message}`, 'error');
                btn.disabled = false;
                btn.textContent = originalText;
            }
        }

        async function uninstallPlugin(name) {
            if (!confirm(`Remove ${name}?`)) return;

            const card = document.querySelector(`[data-name="${name}"]`);
            const btn = card.querySelector('.btn-uninstall');
            btn.disabled = true;
            btn.textContent = '⏳ Removing...';

            try {
                const result = await apiRequest('/plugins/pwnstore_ui/api/uninstall', {
                    method: 'POST',
                    body: JSON.stringify({ plugin: name })
                });

                if (result.success) {
                    showMessage(`✓ ${name} removed!`, 'success');
                    installedPlugins = installedPlugins.filter(p => p !== name);
                    renderPlugins();
                } else {
                    showMessage(`✗ Removal failed: ${result.error || 'Unknown error'}`, 'error');
                    btn.disabled = false;
                    btn.textContent = 'Uninstall';
                }
            } catch (error) {
                console.error('Uninstall error:', error);
                showMessage(`✗ Removal error: ${error.message}`, 'error');
                btn.disabled = false;
                btn.textContent = 'Uninstall';
            }
        }

        function showInfo(name) {
            const plugin = allPlugins.find(p => p.name === name);
            if (!plugin) return;

            const info = `
Plugin: ${plugin.name}
Author: ${plugin.author}
Category: ${plugin.category}
Version: ${plugin.version || 'unknown'}
Source: ${plugin.url}

${plugin.description || 'No description available'}
            `.trim();

            alert(info);
        }

        function showMessage(text, type) {
            const msg = document.createElement('div');
            msg.className = `message ${type}`;
            msg.textContent = text;
            document.body.appendChild(msg);

            setTimeout(() => {
                msg.remove();
            }, 4000);
        }

        // Event listeners
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentCategory = btn.dataset.category;
                renderPlugins();
            });
        });

        document.getElementById('searchBox').addEventListener('input', (e) => {
            searchTerm = e.target.value.toLowerCase();
            renderPlugins();
        });

        // Initial load
        loadData();
    </script>
</body>
</html>
        """
        return html.replace('__CSRF_TOKEN__', csrf_token)

    def _get_plugins(self):
        """Fetch plugins from GitHub registry"""
        try:
            response = requests.get(self.store_url, timeout=10)
            plugins_data = response.json()
            return Response(json.dumps(plugins_data), mimetype='application/json')
        except Exception as e:
            logging.error(f"[pwnstore_ui] Failed to fetch plugins: {e}")
            return Response(json.dumps([]), mimetype='application/json', status=500)

    def _get_installed(self):
        """Get list of installed plugins"""
        try:
            plugin_dir = "/usr/local/share/pwnagotchi/custom-plugins"
            if not os.path.exists(plugin_dir):
                return Response(json.dumps([]), mimetype='application/json')
            
            installed = []
            for file in os.listdir(plugin_dir):
                if file.endswith('.py') and file != '__init__.py':
                    installed.append(file.replace('.py', ''))
            
            return Response(json.dumps(installed), mimetype='application/json')
        except Exception as e:
            logging.error(f"[pwnstore_ui] Failed to get installed plugins: {e}")
            return Response(json.dumps([]), mimetype='application/json', status=500)

    def _install_plugin(self, request):
        """
        Install a plugin
        
        The CLI tool (pwnstore install) handles:
        - Downloading the plugin file
        - Placing it in /usr/local/share/pwnagotchi/custom-plugins/
        - Scanning for self.options and suggesting config entries
        - Automatically adding 'enabled = true' to config.toml
        - Preventing duplicate config entries on reinstall
        """
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.get_json(force=True)
            
            plugin_name = data.get('plugin')
            
            if not plugin_name:
                return Response(
                    json.dumps({'success': False, 'error': 'No plugin name provided'}),
                    mimetype='application/json',
                    status=400
                )
            
            # Check if already installed (optional warning, not blocking)
            plugin_path = f"/usr/local/share/pwnagotchi/custom-plugins/{plugin_name}.py"
            already_installed = os.path.exists(plugin_path)
            
            if already_installed:
                logging.info(f"[pwnstore_ui] Plugin {plugin_name} already exists, reinstalling...")
            else:
                logging.info(f"[pwnstore_ui] Installing {plugin_name}")
            
            # Use CLI tool (it now handles duplicates properly)
            result = subprocess.run(
                ['pwnstore', 'install', plugin_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                action = "reinstalled" if already_installed else "installed"
                logging.info(f"[pwnstore_ui] Successfully {action} {plugin_name}")
                return Response(
                    json.dumps({
                        'success': True, 
                        'message': f'{plugin_name} {action}',
                        'reinstall': already_installed
                    }),
                    mimetype='application/json'
                )
            else:
                error_msg = result.stderr or result.stdout or 'Unknown error'
                logging.error(f"[pwnstore_ui] Install failed: {error_msg}")
                return Response(
                    json.dumps({'success': False, 'error': error_msg}),
                    mimetype='application/json',
                    status=500
                )
                
        except subprocess.TimeoutExpired:
            logging.error(f"[pwnstore_ui] Installation timeout for {plugin_name}")
            return Response(
                json.dumps({'success': False, 'error': 'Installation timeout'}),
                mimetype='application/json',
                status=500
            )
        except json.JSONDecodeError as e:
            logging.error(f"[pwnstore_ui] JSON decode error: {e}")
            return Response(
                json.dumps({'success': False, 'error': 'Invalid request data'}),
                mimetype='application/json',
                status=400
            )
        except Exception as e:
            logging.error(f"[pwnstore_ui] Install error: {e}")
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                mimetype='application/json',
                status=500
            )

    def _uninstall_plugin(self, request):
        """Uninstall a plugin"""
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.get_json(force=True)
            
            plugin_name = data.get('plugin')
            
            if not plugin_name:
                return Response(
                    json.dumps({'success': False, 'error': 'No plugin name provided'}),
                    mimetype='application/json',
                    status=400
                )
            
            logging.info(f"[pwnstore_ui] Uninstalling {plugin_name}")
            
            # Use CLI tool if available
            result = subprocess.run(
                ['pwnstore', 'uninstall', plugin_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logging.info(f"[pwnstore_ui] Successfully uninstalled {plugin_name}")
                return Response(
                    json.dumps({'success': True, 'message': f'{plugin_name} removed'}),
                    mimetype='application/json'
                )
            else:
                error_msg = result.stderr or result.stdout or 'Unknown error'
                logging.error(f"[pwnstore_ui] Uninstall failed: {error_msg}")
                return Response(
                    json.dumps({'success': False, 'error': error_msg}),
                    mimetype='application/json',
                    status=500
                )
                
        except subprocess.TimeoutExpired:
            logging.error(f"[pwnstore_ui] Uninstall timeout for {plugin_name}")
            return Response(
                json.dumps({'success': False, 'error': 'Uninstall timeout'}),
                mimetype='application/json',
                status=500
            )
        except json.JSONDecodeError as e:
            logging.error(f"[pwnstore_ui] JSON decode error: {e}")
            return Response(
                json.dumps({'success': False, 'error': 'Invalid request data'}),
                mimetype='application/json',
                status=400
            )
        except Exception as e:
            logging.error(f"[pwnstore_ui] Uninstall error: {e}")
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                mimetype='application/json',
                status=500
            )
