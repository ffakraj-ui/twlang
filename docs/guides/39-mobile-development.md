# Mobile Development

TW Framework is the only web framework designed to work on mobile devices.

## Why TW Works on Mobile

- **Python-based** — runs on Termux (Android)
- **No Node.js needed** — no `npm install`, no `node_modules`
- **Small install** — `pip install tw-framework` is ~164KB
- **ACode plugin** — syntax highlighting + LSP on Android

## Setup on Android

### 1. Install Termux

```bash
# From F-Droid (recommended) or Play Store
pkg update && pkg upgrade
pkg install python git
```

### 2. Install TW Framework

```bash
pip install tw-framework
```

### 3. Create a Project

```bash
tw create my-site
cd my-site
```

### 4. Develop

```bash
tw dev
```

Open `http://localhost:3000` in your mobile browser.

### 5. Build and Deploy

```bash
tw build --prod
tw deploy
```

## ACode Editor Setup

### Install ACode

From Play Store or F-Droid.

### Install TW Language Plugin

1. Download `tw-language-acode.zip`
2. ACode → Settings → Plugins → Install from local
3. Select the zip file
4. Restart ACode

### Configure LSP Server

1. ACode → Settings → Language servers → Add custom server
2. Fill in:
   - **Server ID:** `tw`
   - **Language IDs:** `tw, twm, tss`
   - **Type:** `STDIO`
   - **Install method:** `Manual binary`
   - **Binary:** `/data/data/com.termux/files/usr/bin/python3`
   - **Args:** `["-m", "tw_framework.lsp_server"]`

### File Access

ACode's LSP works best with files in Termux-accessible directories:

```bash
# Keep project in Termux home
mkdir -p ~/projects
cp -r /storage/emulated/0/my-site ~/projects/
```

Open from: `/data/data/com.termux/files/home/projects/my-site/`

## Termux Storage Access

Grant Termux storage permission:

```bash
termux-setup-storage
```

This creates symlinks to shared storage at `~/storage/`:
- `~/storage/shared/` → `/storage/emulated/0/`
- `~/storage/downloads/` → Downloads folder
- `~/storage/dcim/` → Camera photos

## Git on Mobile

```bash
pkg install git
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Clone, commit, and push from Termux:

```bash
git clone https://github.com/user/repo.git
# Make changes...
git add .
git commit -m "Update from mobile"
git push
```

## Deploying from Mobile

### Vercel from Mobile

1. Push to GitHub from Termux
2. Vercel auto-deploys on push (with `vercel.json` configured)

### Static hosting from Mobile

```bash
tw export
# Upload dist/ to any static host
```

## Tips for Mobile Development

1. **Use ACode** — best code editor with TW support on Android
2. **Keep projects in Termux home** — faster file access than shared storage
3. **Use `tw dev` for testing** — live reload in mobile browser
4. **Use `git` for version control** — commit frequently
5. **Deploy via GitHub + Vercel** — push triggers auto-deploy
6. **Use a Bluetooth keyboard** — typing code on phone keyboard is slow
