"""
PwnStore - Plugin Store for Pwnagotchi
Browse and install plugins directly from the web UI

Author: WPA2
Version: 3.0
"""

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
    __version__ = '1.0'
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
        
        # API endpoint to configure plugin
        elif path == "api/configure":
            return self._configure_plugin(request)
        
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

        /* Config Modal Styles */
        .config-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            padding: 20px;
        }

        .config-modal {
            background: #000;
            border: 3px solid #0f0;
            padding: 25px;
            max-width: 500px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 0 30px #0f0;
        }

        .config-header {
            text-align: center;
            margin-bottom: 20px;
        }

        .config-header h2 {
            font-size: 20px;
            color: #0f0;
            margin-bottom: 10px;
        }

        .config-header p {
            font-size: 13px;
            color: #0a0;
        }

        .config-buttons {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .config-btn {
            padding: 12px 20px;
            border: 2px solid #0f0;
            background: #000;
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
        }

        .config-btn:hover {
            background: #0f0;
            color: #000;
            transform: scale(1.02);
        }

        .config-btn-primary {
            border-width: 3px;
            font-weight: bold;
        }

        .config-btn-secondary {
            border-color: #0a0;
            color: #0a0;
        }

        .config-btn-secondary:hover {
            background: #0a0;
            color: #000;
        }

        .config-btn-tertiary {
            border-color: #070;
            color: #070;
            font-size: 12px;
        }

        .config-btn-tertiary:hover {
            background: #070;
            color: #000;
        }

        .config-form {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .config-field {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .config-field label {
            color: #0f0;
            font-size: 13px;
            font-weight: bold;
        }

        .config-field input,
        .config-field select {
            padding: 10px;
            background: #111;
            border: 2px solid #0f0;
            color: #0f0;
            font-family: 'Courier New', monospace;
            font-size: 13px;
        }

        .config-field input:focus,
        .config-field select:focus {
            outline: none;
            border-color: #fff;
            box-shadow: 0 0 10px #0f0;
        }

        .config-field small {
            color: #0a0;
            font-size: 11px;
        }

        .config-form-actions {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }

        .config-form-actions button {
            flex: 1;
        }

        .ssh-instructions {
            text-align: left;
            padding: 15px;
            background: #111;
            border: 1px solid #0f0;
            margin: 15px 0;
        }

        .ssh-instructions ol {
            margin-left: 20px;
            color: #0f0;
            line-height: 1.8;
        }

        .ssh-instructions code {
            background: #000;
            padding: 3px 8px;
            border: 1px solid #0f0;
            color: #0f0;
            font-size: 12px;
        }

        .code-block {
            background: #000;
            padding: 10px;
            border: 1px solid #0f0;
            margin: 10px 0;
            font-size: 12px;
            color: #0f0;
            overflow-x: auto;
        }

        @media (max-width: 600px) {
            .config-modal {
                padding: 20px;
                max-height: 85vh;
            }

            .config-btn {
                padding: 14px 20px;
                font-size: 15px;
            }

            .config-field input,
            .config-field select {
                padding: 12px;
                font-size: 14px;
            }
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

                    // Check if configuration is required
                    if (result.config_required && result.config_hints && result.config_hints.length > 0) {
                        setTimeout(() => showConfigModal(name, result.config_hints), 1000);
                    }
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

        function showConfigModal(pluginName, configHints) {
            // Create overlay
            const overlay = document.createElement('div');
            overlay.className = 'config-overlay';
            overlay.id = 'configOverlay';

            // Create modal
            const modal = document.createElement('div');
            modal.className = 'config-modal';
            modal.innerHTML = `
                <div class="config-header">
                    <h2>⚙️ Configure ${pluginName}</h2>
                    <p>This plugin needs configuration before it will work properly.</p>
                </div>
                <div class="config-buttons">
                    <button class="config-btn config-btn-primary" onclick="showConfigForm('${pluginName}', ${JSON.stringify(configHints).replace(/"/g, '&quot;')})">
                        📱 Configure Now
                    </button>
                    <button class="config-btn config-btn-secondary" onclick="showSSHInstructions('${pluginName}', ${JSON.stringify(configHints).replace(/"/g, '&quot;')})">
                        💻 Show SSH Instructions
                    </button>
                    <button class="config-btn config-btn-tertiary" onclick="closeConfigModal()">
                        ⏭️ Skip for Now
                    </button>
                </div>
            `;

            overlay.appendChild(modal);
            document.body.appendChild(overlay);
        }

        function showConfigForm(pluginName, configHints) {
            const overlay = document.getElementById('configOverlay');
            const modal = overlay.querySelector('.config-modal');

            let formHTML = `
                <div class="config-header">
                    <h2>⚙️ Configure ${pluginName}</h2>
                    <p>Fill in the settings below to configure this plugin</p>
                </div>
                <form class="config-form" id="configForm" onsubmit="submitConfig(event, '${pluginName}')">
            `;

            configHints.forEach(hint => {
                const label = hint.description || hint.key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                const required = hint.required ? ' *' : '';
                const helpText = hint.help || ('Enter value for ' + hint.key);
                const placeholder = hint.placeholder || hint.default || '';
                
                formHTML += `
                    <div class="config-field">
                        <label>${label}${required}</label>
                `;

                // Render appropriate input type
                if (hint.type === 'select' && hint.options) {
                    // Dropdown select
                    formHTML += `<select name="${hint.key}" ${hint.required ? 'required' : ''}>`;
                    hint.options.forEach(opt => {
                        const selected = opt === hint.default ? 'selected' : '';
                        formHTML += `<option value="${opt}" ${selected}>${opt}</option>`;
                    });
                    formHTML += `</select>`;
                } else if (hint.type === 'multiselect' && hint.options) {
                    // Multi-select as comma-separated text input with available options
                    const defaultVal = hint.default || hint.options.join(',');
                    formHTML += `<input 
                        type="text" 
                        name="${hint.key}" 
                        value="${defaultVal}"
                        placeholder="${hint.options.join(', ')}"
                        ${hint.required ? 'required' : ''}
                    />`;
                } else if (hint.type === 'password') {
                    // Password field
                    formHTML += `<input 
                        type="password" 
                        name="${hint.key}" 
                        placeholder="${placeholder}"
                        ${hint.required ? 'required' : ''}
                    />`;
                } else if (hint.type === 'number') {
                    // Number field
                    formHTML += `<input 
                        type="number" 
                        name="${hint.key}" 
                        placeholder="${placeholder}"
                        value="${hint.default || ''}"
                        ${hint.required ? 'required' : ''}
                    />`;
                } else if (hint.type === 'url') {
                    // URL field
                    formHTML += `<input 
                        type="text" 
                        name="${hint.key}" 
                        placeholder="${placeholder}"
                        ${hint.required ? 'required' : ''}
                    />`;
                } else if (hint.type === 'email') {
                    // Email field
                    formHTML += `<input 
                        type="email" 
                        name="${hint.key}" 
                        placeholder="${placeholder}"
                        ${hint.required ? 'required' : ''}
                    />`;
                } else {
                    // Default text field
                    formHTML += `<input 
                        type="text" 
                        name="${hint.key}" 
                        placeholder="${placeholder}"
                        value="${hint.default || ''}"
                        ${hint.required ? 'required' : ''}
                    />`;
                }

                formHTML += `
                        <small>💡 ${helpText}</small>
                    </div>
                `;
            });

            formHTML += `
                    <div class="config-form-actions">
                        <button type="submit" class="config-btn config-btn-primary">✓ Save Configuration</button>
                        <button type="button" class="config-btn config-btn-secondary" onclick="closeConfigModal()">✗ Cancel</button>
                    </div>
                </form>
            `;

            modal.innerHTML = formHTML;
        }

        async function submitConfig(event, pluginName) {
            event.preventDefault();
            const form = event.target;
            const formData = new FormData(form);
            const config = {};

            for (let [key, value] of formData.entries()) {
                config[key] = value;
            }

            // Show loading
            const submitBtn = form.querySelector('[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Saving...';

            try {
                const result = await apiRequest('/plugins/pwnstore_ui/api/configure', {
                    method: 'POST',
                    body: JSON.stringify({ plugin: pluginName, config: config })
                });

                if (result.success) {
                    closeConfigModal();
                    showMessage(`✓ ${pluginName} configured! Restart Pwnagotchi to apply changes.`, 'success');
                } else {
                    showMessage(`✗ Configuration failed: ${result.error || 'Unknown error'}`, 'error');
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            } catch (error) {
                console.error('Config error:', error);
                showMessage(`✗ Configuration error: ${error.message}`, 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        }

        function showSSHInstructions(pluginName, configHints) {
            const overlay = document.getElementById('configOverlay');
            const modal = overlay.querySelector('.config-modal');

            let instructions = `
                <div class="config-header">
                    <h2>💻 SSH Configuration</h2>
                    <p>Configure ${pluginName} manually via SSH</p>
                </div>
                <div class="ssh-instructions">
                    <ol>
                        <li>Connect to your Pwnagotchi:
                            <code>ssh pi@10.0.0.2</code>
                        </li>
                        <li>Edit the configuration file:
                            <code>sudo nano /etc/pwnagotchi/config.toml</code>
                        </li>
                        <li>Add these lines:
                            <div class="code-block">
            `;

            configHints.forEach(hint => {
                instructions += `main.plugins.${pluginName}.${hint.key} = "YOUR_VALUE"<br>`;
            });

            instructions += `
                            </div>
                        </li>
                        <li>Save (Ctrl+O, Enter) and exit (Ctrl+X)</li>
                        <li>Restart: <code>sudo systemctl restart pwnagotchi</code></li>
                    </ol>
                    <button class="config-btn config-btn-secondary" onclick="copySSHCommands('${pluginName}', ${JSON.stringify(configHints).replace(/"/g, '&quot;')})">
                        📋 Copy Config Lines
                    </button>
                    <button class="config-btn config-btn-tertiary" onclick="closeConfigModal()">
                        Close
                    </button>
                </div>
            `;

            modal.innerHTML = instructions;
        }

        function copySSHCommands(pluginName, configHints) {
            let text = '';
            configHints.forEach(hint => {
                text += `main.plugins.${pluginName}.${hint.key} = "YOUR_VALUE"\n`;
            });

            navigator.clipboard.writeText(text).then(() => {
                showMessage('✓ Config lines copied to clipboard!', 'success');
            }).catch(() => {
                showMessage('✗ Could not copy to clipboard', 'error');
            });
        }

        function closeConfigModal() {
            const overlay = document.getElementById('configOverlay');
            if (overlay) {
                overlay.remove();
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

    def _parse_config_hints(self, cli_output, plugin_name):
        """
        Parse config hints from CLI output and enhance with plugin file analysis
        Returns list of dicts with detailed field information
        """
        # First, get basic hints from CLI output
        basic_hints = self._extract_cli_hints(cli_output, plugin_name)
        
        # Parse plugin file for intelligent detection
        enhanced_hints = self._parse_plugin_file(plugin_name, basic_hints)
        
        return enhanced_hints

    def _extract_cli_hints(self, cli_output, plugin_name):
        """Extract basic field names from CLI output"""
        hints = []
        lines = cli_output.split('\n')
        in_config_section = False
        
        for line in lines:
            if '[!] CONFIGURATION REQUIRED:' in line:
                in_config_section = True
                continue
            
            if in_config_section and f'main.plugins.{plugin_name}.' in line:
                import re
                match = re.search(rf'main\.plugins\.{plugin_name}\.(\w+)\s*=', line)
                if match:
                    hints.append(match.group(1))
        
        return hints

    def _parse_plugin_file(self, plugin_name, field_names):
        """
        Parse plugin Python file to extract config information
        Looks for: defaults, valid options, descriptions, types
        """
        plugin_path = f"/usr/local/share/pwnagotchi/custom-plugins/{plugin_name}.py"
        
        if not os.path.exists(plugin_path):
            # Fallback to basic detection
            return [self._detect_field_type(name) for name in field_names]
        
        try:
            with open(plugin_path, 'r', errors='ignore') as f:
                content = f.read()
            
            result = []
            for field_name in field_names:
                field_config = self._analyze_field_in_code(field_name, content)
                field_config['key'] = field_name
                field_config['required'] = True
                result.append(field_config)
            
            return result
        except Exception as e:
            logging.error(f"[pwnstore_ui] Error parsing plugin file: {e}")
            return [self._detect_field_type(name) for name in field_names]

    def _analyze_field_in_code(self, field_name, code):
        """
        Analyze plugin code to extract field configuration
        Comprehensively looks for:
        - Valid options in lists/tuples: in ['a', 'b'], in ('a', 'b')
        - Default values: .get('field', default)
        - Array fields: fields = ['a', 'b', 'c']
        - Comments/docstrings with descriptions
        """
        import re
        
        config = self._detect_field_type(field_name)
        
        # Pattern 1: Look for: if self.options['field'] in ['option1', 'option2', 'option3']
        # Also handles: if self.options.get('field') in ['...']
        enum_patterns = [
            rf"self\.options(?:\.get)?\(['\"]?{field_name}['\"]?\)?\s+in\s+\[([^\]]+)\]",
            rf"self\.options(?:\.get)?\(['\"]?{field_name}['\"]?\)?\s+in\s+\(([^\)]+)\)",
            rf"['\"]?{field_name}['\"]?\s+in\s+\[([^\]]+)\]",
        ]
        
        for pattern in enum_patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                options_str = match.group(1)
                # Extract quoted strings
                options = re.findall(r"['\"]([^'\"]+)['\"]", options_str)
                if options and len(options) >= 2 and len(options) <= 15:
                    config['type'] = 'select'
                    config['options'] = options
                    config['description'] = f"Choose from: {', '.join(options)}"
                    break
        
        # Pattern 2: Look for array/list definitions: fields = ['mem', 'cpu', 'temp']
        # Common for multiselect options
        if not config.get('options'):
            array_patterns = [
                rf"{field_name}\s*=\s*\[([^\]]+)\]",
                rf"['\"]({field_name})['\"].*?\[([^\]]+)\]",
            ]
            
            for pattern in array_patterns:
                match = re.search(pattern, code)
                if match:
                    try:
                        # Get the last capture group (the array contents)
                        array_str = match.groups()[-1]
                        items = re.findall(r"['\"]([^'\"]+)['\"]", array_str)
                        if items and len(items) >= 3:  # Multiple items suggests multiselect
                            config['type'] = 'multiselect'
                            config['options'] = items
                            config['description'] = f"Available options: {', '.join(items)}"
                            config['help'] = 'Select multiple (comma-separated)'
                            break
                    except:
                        pass
        
        # Pattern 3: Look for default values: self.options.get('field', 'default_value')
        default_patterns = [
            rf"self\.options\.get\(['\"]({field_name})['\"],\s*['\"]([^'\"]+)['\"]",  # String default
            rf"self\.options\.get\(['\"]({field_name})['\"],\s*(\d+)",  # Number default
            rf"self\.options\.get\(['\"]({field_name})['\"],\s*\[([^\]]+)\]",  # List default
            rf"self\.options\.get\(['\"]({field_name})['\"],\s*(True|False)",  # Boolean default
        ]
        
        for pattern in default_patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                try:
                    default_val = match.group(2)
                    # Clean up the default value
                    default_val = default_val.strip().strip('"\'')
                    config['default'] = default_val
                    # If we found a list default for multiselect, format it nicely
                    if config['type'] == 'multiselect':
                        items = re.findall(r"['\"]([^'\"]+)['\"]", match.group(2))
                        if items:
                            config['default'] = ','.join(items)
                    break
                except:
                    pass
        
        # Pattern 4: Look for boolean fields
        bool_patterns = [
            rf"self\.options\[['\"]({field_name})['\"]\]\s*(?:==|is)\s*(True|False)",
            rf"if.*?{field_name}.*?(True|False)",
        ]
        
        for pattern in bool_patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match and not config.get('options'):
                config['type'] = 'select'
                config['options'] = ['true', 'false']
                if not config.get('default'):
                    config['default'] = 'true'
                break
        
        # Pattern 5: Look for descriptions in comments/docstrings
        desc_patterns = [
            rf"#\s*{field_name}:?\s+(.+)",  # # field: description
            rf"['\"]({field_name})['\"]:\s*['\"]([^'\"]+)['\"]",  # "field": "description"
            rf"{field_name}\s*\(['\"]([^'\"]+)['\"]",  # field("description")
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, code, re.IGNORECASE)
            if match:
                desc = match.groups()[-1].strip()
                # Only use if reasonable length and doesn't look like code
                if 10 < len(desc) < 150 and not any(x in desc for x in ['self.', 'def ', 'import ', '()', '[]']):
                    config['description'] = desc
                    break
        
        # If we found options but no description, generate one
        if config.get('options') and not config.get('description'):
            if config['type'] == 'select':
                config['description'] = f"Options: {', '.join(config['options'])}"
            elif config['type'] == 'multiselect':
                config['description'] = f"Available: {', '.join(config['options'])}"
        
        return config

    def _detect_field_type(self, field_name):
        """
        Detect field type from field name
        Returns basic field configuration
        """
        field_config = {
            'key': field_name,
            'type': 'text',
            'required': True,
            'description': field_name.replace('_', ' ').title(),
            'help': f'Enter value for {field_name}'
        }
        
        # Type detection based on field name
        name_lower = field_name.lower()
        
        if 'url' in name_lower or 'webhook' in name_lower:
            field_config['type'] = 'url'
            field_config['placeholder'] = 'https://...'
            field_config['help'] = 'Enter the full URL'
        
        elif 'api_key' in name_lower or 'token' in name_lower or 'secret' in name_lower or 'password' in name_lower:
            field_config['type'] = 'password'
            field_config['placeholder'] = 'Your API key or token'
            field_config['help'] = 'Get from service provider'
        
        elif 'enabled' in name_lower or 'enable' in name_lower:
            field_config['type'] = 'select'
            field_config['options'] = ['true', 'false']
            field_config['default'] = 'true'
            field_config['help'] = 'Enable or disable this feature'
        
        elif 'port' in name_lower or 'timeout' in name_lower or 'interval' in name_lower or 'spacing' in name_lower:
            field_config['type'] = 'number'
            field_config['placeholder'] = '0'
            field_config['help'] = 'Enter a number'
        
        elif 'username' in name_lower or 'name' in name_lower:
            field_config['placeholder'] = 'Pwnagotchi'
            field_config['help'] = 'Display name'
        
        elif 'email' in name_lower or 'mail' in name_lower:
            field_config['type'] = 'email'
            field_config['placeholder'] = 'user@example.com'
            field_config['help'] = 'Enter email address'
        
        return field_config

    def _configure_plugin(self, request):
        """
        Configure a plugin by editing config.toml
        """
        try:
            if request.is_json:
                data = request.get_json()
            else:
                data = request.get_json(force=True)
            
            plugin_name = data.get('plugin')
            config_values = data.get('config', {})
            
            if not plugin_name or not config_values:
                return Response(
                    json.dumps({'success': False, 'error': 'Missing plugin name or config values'}),
                    mimetype='application/json',
                    status=400
                )
            
            logging.info(f"[pwnstore_ui] Configuring {plugin_name} with {len(config_values)} settings")
            
            # Backup config file first
            config_file = "/etc/pwnagotchi/config.toml"
            backup_file = f"{config_file}.backup"
            
            try:
                import shutil
                shutil.copy2(config_file, backup_file)
            except Exception as e:
                logging.warning(f"[pwnstore_ui] Could not create backup: {e}")
            
            # Read current config
            with open(config_file, 'r') as f:
                lines = f.readlines()
            
            new_lines = []
            config_section_found = False
            
            # Track which config keys we've added
            added_keys = set()
            
            for line in lines:
                # Check if this line is for our plugin
                is_plugin_line = f'main.plugins.{plugin_name}.' in line
                
                if is_plugin_line:
                    config_section_found = True
                    # Check which config key this line is for
                    for key, value in config_values.items():
                        config_key = f'main.plugins.{plugin_name}.{key}'
                        if config_key in line:
                            # Update existing line
                            new_lines.append(f'{config_key} = "{value}"\n')
                            added_keys.add(key)
                            break
                    else:
                        # Keep line as-is if not updating
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            
            # Add any config keys that weren't found in file
            if new_lines and not new_lines[-1].endswith('\n'):
                new_lines[-1] += '\n'
            
            for key, value in config_values.items():
                if key not in added_keys:
                    new_lines.append(f'main.plugins.{plugin_name}.{key} = "{value}"\n')
            
            # Write back to file
            with open(config_file, 'w') as f:
                f.writelines(new_lines)
            
            logging.info(f"[pwnstore_ui] Successfully configured {plugin_name}")
            
            return Response(
                json.dumps({
                    'success': True,
                    'message': f'{plugin_name} configured successfully'
                }),
                mimetype='application/json'
            )
            
        except Exception as e:
            logging.error(f"[pwnstore_ui] Configuration failed: {e}")
            return Response(
                json.dumps({'success': False, 'error': str(e)}),
                mimetype='application/json',
                status=500
            )

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
                
                # Parse config hints from CLI output
                config_hints = self._parse_config_hints(result.stdout, plugin_name)
                
                return Response(
                    json.dumps({
                        'success': True, 
                        'message': f'{plugin_name} {action}',
                        'reinstall': already_installed,
                        'config_required': len(config_hints) > 0,
                        'config_hints': config_hints
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
