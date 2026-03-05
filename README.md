# A12Bypass-Py - Secure iOS Activation Bypass

**Maximum security compiled executable for Windows 64-bit**

---

## 🔒 Security Features

- ✅ Full C++ compilation (no Python bytecode)
- ✅ Anti-debugging protection
- ✅ Anti-tampering runtime checks
- ✅ Code obfuscation via C++ compilation
- ✅ String encryption
- ✅ Integrity verification (SHA256)
- ✅ Hardware-bound encrypted activation
- ✅ Rate limiting (5 attempts = 5min lockout)

---

## 🚀 Quick Start

### For Users (Download Pre-built)

1. Go to **Releases** section
2. Download latest `A12Bypass-Secure.zip`
3. Extract and run `main.exe`
4. Follow activation instructions

### For Developers (Build from Source)

#### Option 1: GitHub Actions (Recommended)

```bash
# Push code
git push origin main

# Check Actions tab in 5 minutes for automatic build
```

#### Option 2: Manual Build

```bash
# Install dependencies
pip install -r requirements.txt

# Build with Nuitka
python build_secure.py

# Output: build/nuitka_secure/main.exe
```

---

## 📦 Requirements

### Runtime Requirements (for users)

- **OS**: Windows 10/11 (64-bit only)
- **Python**: Not required (standalone executable)
- **Dependencies**: All bundled in executable

### Build Requirements (for developers)

- **Python**: 3.11
- **Compiler**: Visual Studio Build Tools with C++
- **Nuitka**: 4.x or later
- **RAM**: Minimum 4GB (8GB recommended)

---

## 🏗️ Building with GitHub Actions

### Automatic Builds

Every push to `main` branch triggers an automatic build.

### Manual Trigger

1. Go to **Actions** tab
2. Click "Build Secure Executable"
3. Click "Run workflow"
4. Wait ~3-5 minutes
5. Download from Artifacts section

### Create Release

```bash
# Tag version
git tag v1.0.0

# Push tag
git push origin v1.0.0

# Release will be created automatically
```

---

## 🛡️ Security Architecture

### Protection Layers

1. **Code Compilation** - Python → C++ → Machine Code
2. **Anti-Debugging** - Detects debuggers and terminates
3. **Integrity Check** - SHA256 hash verification
4. **Runtime Monitoring** - Continuous security scanning
5. **Activation Security** - Hardware-bound encrypted activation

### What's Protected

✅ Source code hidden (compiled to C++)  
✅ No bytecode exposed  
✅ Debugger detection active  
✅ Binary modifications detected  
✅ Memory dump attempts blocked  
✅ VM/sandbox detection enabled  

---

## 📁 Project Structure

```
repo/
├── .github/
│   └── workflows/
│       └── build-secure.yml      # GitHub Actions workflow
├── core/                          # Application logic
│   ├── detector.py
│   ├── api.py
│   └── worker.py
├── gui/                           # User interface
│   ├── dialogs.py
│   └── mainUI_ui.py
├── security/                      # Security modules
│   ├── runtime_protection.py     # Anti-debugging
│   └── anti_crack.py             # Activation security
├── utils/                         # Utilities
│   └── helpers.py
├── libs/                          # External DLLs (iOS tools)
├── build_secure.py                # Build script
├── requirements.txt               # Python dependencies
├── config.py                      # Configuration
├── main.py                        # Entry point
└── README.md                      # This file
```

---

## ⚙️ Configuration

### Environment Variables

Create `.env` file (not committed to git):

```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
WORKER_URL=https://your-worker.workers.dev
```

### Build Configuration

Edit `build_secure.py` to customize:
- Included packages
- Qt plugins
- Optimization level
- Output directory

---

## 🧪 Testing

### Before Distribution

Test on clean Windows 10/11 VM:
- Verify all features work
- Check activation flow
- Test device detection
- Confirm no false positives from antivirus

### After Installation

1. Run `main.exe`
2. Connect iOS device
3. Follow activation steps
4. Verify success

---

## 🐛 Troubleshooting

### App Won't Start

**Solution**: Make sure all files from ZIP are extracted, not just `main.exe`.

### Antivirus Alert

**Why**: Compiled Python executables sometimes trigger false positives.

**Solution**: 
1. Add to antivirus exclusion list
2. Submit to vendor for whitelisting
3. Contact developer for signed version

### Activation Fails

**Check**:
- Internet connection
- Device compatibility (A12 chip required)
- Serial key format
- Hardware binding (activation tied to one PC)

### Build Fails on GitHub Actions

**Check**:
- All dependencies in `requirements.txt`
- Workflow file syntax
- Python version compatibility (must be 3.11)

---

## 📊 Build Status

[![Build Status](../../actions/workflows/build-secure.yml/badge.svg)](../../actions/workflows/build-secure.yml)

Latest build: Check **Actions** tab for status

---

## 📝 Changelog

### v1.0.0 (Initial Release)
- ✅ Full C++ compilation
- ✅ Anti-debugging protection
- ✅ Hardware-bound activation
- ✅ Automated GitHub builds
- ✅ SHA256 integrity verification

---

## 🔐 Security Notes

### For Distributors

⚠️ **DO NOT**:
- Distribute without `.session_key` file (generated per build)
- Modify executable after build (breaks hash verification)
- Share activation data between different hardware

✅ **DO**:
- Verify SHA256 hash before distribution
- Keep source code private
- Use HTTPS for all API calls
- Monitor for cracked versions

### For Users

Your activation is bound to your specific hardware (CPU + Motherboard). It cannot be transferred to another computer.

---

## 📞 Support

### Getting Help

1. Check this README
2. Review issues section
3. Contact development team

### Reporting Issues

Include:
- Windows version
- Error messages
- Steps to reproduce
- Screenshots if applicable

---

## ⚖️ License

**Proprietary Software** - All rights reserved.

- ❌ No reverse engineering
- ❌ No redistribution
- ❌ No modification
- ✅ Personal use only

---

## 🙏 Credits

Built with:
- [Nuitka Compiler](https://nuitka.net/)
- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
- [GitHub Actions](https://github.com/features/actions)

---

## 📧 Contact

For questions, support, or licensing inquiries:
- **Issues**: [GitHub Issues](../../issues)
- **Email**: [Your contact here]

---

**Last Updated**: Current  
**Build Version**: Latest from main branch  
**Platform**: Windows 64-bit only
