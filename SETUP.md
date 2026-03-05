# Quick Setup Guide

## Initialize Git Repository

```bash
cd repo

# Initialize git
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - A12Bypass secure build"

# Add remote (replace with your GitHub repo URL)
git remote add origin https://github.com/YOUR_USERNAME/A12Bypass-Py.git

# Push to GitHub
git push -u origin main
```

## That's It!

Once pushed to GitHub:
- ✅ Automatic builds on every push
- ✅ Manual trigger via Actions tab
- ✅ Automatic releases on version tags

## Build Your Executable

### Option 1: Wait for Auto-Build
After pushing, GitHub Actions will automatically build.

### Option 2: Manual Trigger
1. Go to GitHub repo
2. Click **Actions** tab
3. Click **"Build Secure Executable"**
4. Click **"Run workflow"**
5. Wait ~5 minutes
6. Download from **Artifacts**

### Option 3: Create Release
```bash
# Tag version
git tag v1.0.0

# Push tag
git push origin v1.0.0

# Release created automatically!
```

## What's Included

✅ Source code (core, gui, security, utils)  
✅ Build scripts (build_secure.py)  
✅ Dependencies (requirements.txt)  
✅ Configuration (config.py)  
✅ External DLLs (libs/)  
✅ GitHub Actions workflow (.github/workflows/)  
✅ README.md  

## What's Excluded

❌ Virtual environment (venv/)  
❌ Build artifacts (build/, dist/)  
❌ Documentation files (*.md except README)  
❌ Compiled executables (*.exe)  
❌ Session keys (.session_key)  
❌ Hash files (*.sha256)  

---

**Ready to build!** 🚀
