# 🎬 VideoMaker Pro - AI Video Creator & Affiliate Automation
> **The ultimate command center for TikTok Creators and Affiliate Marketers.**

VideoMaker Pro is a high-performance, automated video production suite integrated with a premium web dashboard. It combines cutting-edge AI (Gemini 1.5 Pro) for script generation with a robust automation pipeline for multi-account management, stealth browsing, and scheduled content distribution.

---

## ✨ Key Features

### 🎨 Premium Meme Studio (Creation Mode)
- **Triple-Column Workspace:** Script Editor, Asset Management, and Live Preview all on one screen.
- **AI Brain (Gemini 1.5 Pro):** Generate viral-ready scripts from simple ideas in seconds.
- **Dynamic Asset Library:** Seamlessly mix local uploads with Pexels stock footage.
- **Advanced Audio Engine:** Support for background music mixing, voice-over (TTS) synchronization, and volume normalization.
- **Video Library:** Premium grid view to manage, preview, and batch-delete your creations.

### 🛡️ Stealth Browser & Affiliate Pipeline (Automation Mode)
- **CloakBrowser Integration:** Native support for CloakBrowser binaries to bypass TikTok's bot detection and automation checks.
- **Multi-Account Management:** Isolated Chrome profiles with per-account proxy support and fingerprint spoofing.
- **Content Factory:** Automatic "Freshness" processing—re-render existing videos with new music/TTS to evade copyright strikes.
- **Auto Uploader & Scheduler:**
    - **Intelligent Queue:** Multi-threaded uploading with automatic retries and detailed logs.
    - **Golden Hour Scheduler:** Set your uploads for peak engagement times (11h-13h, 18h-21h).
    - **Showcase Integration:** Automatic product tagging via Product IDs.
- **Health Check & Account Warming:** Automated browsing scripts to build account trust.

---

## 🚀 Getting Started

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/your-repo/videomaker-pro.git
cd videomaker-pro

# Set up virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env  # Add your GEMINI_API_KEY and FPT_AI_API_KEY
```

### 2. Launch the Web Dashboard
```bash
# Start the main application
python app.py

# Optional: Start the Scheduler for Golden Hour uploads
python scheduler.py

# → Open http://localhost:5000 in your browser
```

---

## 🎙️ Supported AI Voices (Premium Engines)

| Engine | Gender | Accent | Highlights |
|---|---|---|---|
| **Edge-TTS** | Male/Female | North | High-quality, Free |
| **FPT.AI** | Male/Female | North/Central/South | Pro-grade, Natural |

---

## 🛠️ CLI Power Tools
For advanced users, VideoMaker Pro offers a robust CLI interface:

```bash
# Manage Accounts
python main.py nick login test_nick     # Initialize a new stealth session
python main.py nick list                # View status of all satellite accounts

# Process Content
python main.py process --url 'https://...'      # Download & Clean a video
python main.py process --file v.mp4 --bg-music music.mp3 # Manual re-render

# Account Maintenance
python health_check.py                  # Run automated warm-up routines
```

---

## 📁 Project Architecture
```
play/
├── app.py              # Main Web Server & API Gateway
├── main.py             # CLI Controller for Automation
├── cloakbrowser.py     # CloakBrowser detection & initialization module
├── tts.py              # Multi-engine Text-to-Speech logic
├── video_maker.py      # Core Studio rendering engine (FFmpeg)
├── uploader.py         # Stealth Automation via CloakBrowser + DrissionPage
├── scheduler.py        # Background Golden Hour daemon
├── webapp/             # Premium SPA (HTML5, Vanilla JS, TailwindCSS)
├── profiles/           # Isolated stealth browser session data
├── data/               # Persistent storage for accounts and queues
└── logs/               # Operation logs and upload history
```

---

## ⚠️ Important Notes
- **CloakBrowser:** Ensure CloakBrowser is installed in your Applications folder for maximum stealth. The system will fall back to standard Chrome if not found.
- **Automation Safety:** The system includes a **Random Delay** mechanism and human-like interaction patterns. Do not disable these if you want to keep your accounts safe.
- **Monitoring:** Check `logs/upload_history.log` for detailed success/failure reports of your automated uploads.

---
*Built with ❤️ for the next generation of Content Creators.*

