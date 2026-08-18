# 🛒 PwnStore - The Unofficial Pwnagotchi App Store

**Stop downloading massive ZIP files.** Install Pwnagotchi plugins surgically—one file at a time.

[![CLI Version](https://img.shields.io/badge/CLI-v3.3.4-green)](https://github.com/wpa-2/pwnagotchi-store) [![UI Version](https://img.shields.io/badge/Web_UI-v1.2.10-blue)](https://github.com/wpa-2/pwnagotchi-store) [![Gallery](https://img.shields.io/badge/Gallery-Live-orange)](https://pwnstore.org/) [![License](https://img.shields.io/badge/license-GPL3-red)](LICENSE)

---

## 🚀 Quick Install

SSH into your Pwnagotchi and run:
```bash
sudo wget -O /usr/local/bin/pwnstore https://raw.githubusercontent.com/wpa-2/pwnagotchi-store/main/pwnstore.py && sudo chmod +x /usr/local/bin/pwnstore
```

Then browse and install plugins:
```bash
pwnstore list              # Browse 70+ plugins
sudo pwnstore install <plugin_name>
```

---

## 📦 Four Ways to Use  PwnStore

| Interface | Perfect For | Access |
|-----------|-------------|--------|
| **🖥️ CLI Tool** | SSH users & automation | `pwnstore list` |
| **🌐 Web UI** | Mobile users, one-click installs | `http://<ip>/plugins/pwnstore_ui/` |
| **🌍 Gallery** | Browsing & discovering plugins | [pwnstore.org](https://pwnstore.org/) |
| **🛠️ Troubleshooter** | Fixing problems step-by-step | [pwnstore.org/troubleshoot](https://pwnstore.org/troubleshoot.html) |

---

## 📚 Documentation

**Getting Started:**
- 📖 [CLI Guide](docs/CLI-GUIDE.md) - Commands and usage
- 🌐 [Web UI Guide](docs/WEB-UI-GUIDE.md) - Browser interface setup
- 🛠️ [Troubleshooting](docs/TROUBLESHOOTING.md) - Fix common issues
- ❓ [FAQ](docs/FAQ.md) - Quick answers

**Contributing:**
- 🤝 [Add Your Plugin](docs/CONTRIBUTING.md) - Submit to the store

---

## ✨ Features

- **📦 Lightweight:** No massive ZIP files - download only what you need
- **🎯 Surgical Installs:** Single `.py` files are auto-extracted from archives
- **🧠 Smart Config:** Automatically adds `enabled = true` to config.toml
- **🔄 Auto-Update:** Keep plugins and PwnStore itself up to date
- **📱 Mobile-Friendly:** Touch-optimized web interface
- **🏷️ Auto-Categorized:** GPS, Social, Display, Hardware, Attack, System

---

## 💡 Need Help?

### 🛠️ Interactive Troubleshooter
**Can't connect? Display not working? Plugin issues?**  
👉 **[pwnstore.org/troubleshoot.html](https://pwnstore.org/troubleshoot.html)**

Step-by-step wizard with click-to-copy commands. Works on any device!

### 💬 Community Support
- **[Discord](https://discord.gg/jFasAGdTFm)** - Get help from the community
- **[Telegram](https://t.me/Pwnagotchi_UK_Chat/)** - UK Pwnagotchi chat
- **[Reddit](https://reddit.com/r/pwnagotchi)** - r/pwnagotchi
- **[Wiki](https://github.com/jayofelony/pwnagotchi/wiki)** - Official docs

---

## 📊 Quick Stats

- **70+ plugins** indexed and ready to install
- **8 repository sources** automatically monitored
- **6 categories** for easy discovery
- **Auto-updated** registry via GitHub Actions
```bash
pwnstore sources    # View all plugin sources
```

---

## ☕ Support the Project

If PwnStore saved you time or SD card space, consider buying me a coffee!

[![Buy me a coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=wpa2&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://buymeacoffee.com/wpa2)

**[☕ buymeacoffee.com/wpa2](https://buymeacoffee.com/wpa2)**

---

## 📜 License

GPL-3.0 License - See [LICENSE](LICENSE) file for details

**Made with 💚 for the Pwnagotchi community by [WPA2](https://github.com/wpa-2)**

---

## 🔗 Quick Links

- 🌐 **Plugin Gallery:** [pwnstore.org](https://pwnstore.org/)
- 🛠️ **Troubleshooter:** [pwnstore.org/troubleshoot.html](https://pwnstore.org/troubleshoot.html)
- 💬 **Discord:** [discord.gg/jFasAGdTFm](https://discord.gg/jFasAGdTFm)
- 📱 **Telegram:** [t.me/Pwnagotchi_UK_Chat](https://t.me/Pwnagotchi_UK_Chat/)
- 📖 **Documentation:** [docs/](docs/)
