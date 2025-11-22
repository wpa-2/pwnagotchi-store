# 🛒 PwnStore - The Unofficial Pwnagotchi App Store

**Stop downloading massive ZIP files.** PwnStore is a lightweight, CLI-based package manager for Pwnagotchi. It allows you to browse, install, update, and manage plugins surgically—downloading only the files you need.

![Version](https://img.shields.io/badge/version-1.7-green) ![Python](https://img.shields.io/badge/python-3-blue) ![License](https://img.shields.io/badge/license-GPL3-red)

## ✨ Features
* **Lightweight Registry:** Queries a remote JSON manifest; doesn't bloat your device.
* **Surgical Installs:** Downloads single `.py` files or extracts specific plugins from large repository archives automatically.
* **Smart Config Hints:** Scans plugin code upon installation and tells you exactly what lines (`self.options`) to add to your `config.toml`.
* **Auto-Config:** Automatically appends `enabled = true` to your config file so the plugin loads on restart.
* **Self-Updating:** The tool can update itself and bulk-upgrade your installed plugins.
* **Web Gallery:** Includes a retro-themed HTML interface for browsing plugins visually.

---

## 🚀 Installation

SSH into your Pwnagotchi and run this single command to install the store:

```bash
sudo wget -O /usr/local/bin/pwnstore [https://raw.githubusercontent.com/YOUR_GITHUB_USER/pwnagotchi-store/main/pwnstore.py](https://raw.githubusercontent.com/YOUR_GITHUB_USER/pwnagotchi-store/main/pwnstore.py) && sudo chmod +x /usr/local/bin/pwnstore
```

*(Note: Replace `YOUR_GITHUB_USER` with your actual username. Verify installation by running `pwnstore list`.)*

---

## 📖 CLI Usage

### 1. List & Search
Browse available plugins. The list is auto-categorized (GPS, Social, Display, etc.).
```bash
pwnstore list
pwnstore search discord
```

### 2. Get Plugin Details
View the author, version, description, and source URL.
```bash
pwnstore info <plugin_name>
```

### 3. Install a Plugin
Downloads the plugin, enables it, and scans for required settings.
```bash
sudo pwnstore install <plugin_name>
```
* **Smart Hint:** If the plugin requires specific settings (like API keys), PwnStore will print them after installation.

### 4. Manage Updates
Update the PwnStore tool itself, or check all installed plugins for new versions.
```bash
# Update the store tool
sudo pwnstore update

# Check for plugin updates
sudo pwnstore upgrade
```

### 5. Uninstall a Plugin
Removes the file and disables it in `config.toml`.
```bash
sudo pwnstore uninstall <plugin_name>
```

---

## 🌐 Web Interface
This repository includes a **Pwnagotchi-themed Web Gallery** (`index.html`).
If you enable **GitHub Pages** for this repository, you can browse plugins, filter by category, and generate install commands directly from your browser.

---

## ⚙️ How it Works
PwnStore does not scan GitHub in real-time (too slow). Instead, it reads a `plugins.json` registry file hosted in this repository.

1.  **The Builder:** A script (`builder.py`) scans known plugin repositories (listed in `repos.txt`), categorizes them using keyword logic, and generates a sorted `plugins.json`.
2.  **The Client:** The `pwnstore` script on your Pwnagotchi reads this JSON to perform actions.

### Adding New Plugins
Want to add a plugin to the store?
1.  Fork this repo.
2.  Add the GitHub URL of the plugin (or the repo zip archive) to `repos.txt`.
3.  Submit a Pull Request.
4.  Once merged, the registry will auto-update via GitHub Actions.

---

## ☕ Support the Development
If this tool saved you time or saved your SD card from clutter, consider buying me a coffee!

**[Buy me a coffee (wpa2)](https://buymeacoffee.com/wpa2)**

<a href="https://buymeacoffee.com/wpa2">
  <img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=wpa2&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff" />
</a>
