# 🛠️ Temperature Monitor Setup Guide

Complete step-by-step setup instructions for the Temperature Monitor system.

## 📋 Prerequisites

Before starting, ensure you have:

- **Python 3.7+** installed on your system
- **Gmail account** for receiving temperature emails
- **Google Cloud Console** access
- **Temperature monitoring system** that sends emails (Clever Logger format preferred)
- **Windows/macOS/Linux** computer to run the application

## 🔧 Step 1: System Setup

### 1.1 Install Python Dependencies

```bash
# Navigate to project directory
cd temperature-monitor

# Install required packages
pip install -r requirements.txt
```

### 1.2 Verify Installation

```bash
# Test Python installation
python --version

# Test key dependencies
python -c "import flask, pyttsx3, pystray; print('✅ Dependencies OK')"
```

## ☁️ Step 2: Google Cloud Console Setup

### 2.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Create Project"** or select existing project
3. Name your project (e.g., "Temperature Monitor")
4. Note the **Project ID** for reference

### 2.2 Enable Required APIs

1. Navigate to **"APIs & Services" > "Library"**
2. Search and enable these APIs:
   - **Gmail API** ✅
   - **Google Sheets API** ✅
   - **Google Drive API** ✅

### 2.3 Create OAuth 2.0 Credentials

1. Go to **"APIs & Services" > "Credentials"**
2. Click **"+ Create Credentials" > "OAuth client ID"**
3. Configure OAuth consent screen first if prompted:
   - **Application type**: Desktop application
   - **App name**: Temperature Monitor
   - **User support email**: Your email
   - **Authorized domains**: Leave empty for desktop app
4. Create OAuth client ID:
   - **Application type**: Desktop application
   - **Name**: Temperature Monitor Desktop
5. **Download** the credentials JSON file
6. **Rename** it to `credentials.json`
7. **Place** it in the `config/` folder

### 2.4 OAuth Consent Screen (Important!)

1. Go to **"OAuth consent screen"**
2. Add your Gmail address to **"Test users"** 
3. This allows you to authenticate during development

## 📁 Step 3: Project Configuration

### 3.1 Create Configuration File

```bash
# Copy example settings
cp config/settings.example.json config/settings.json
```

### 3.2 Verify File Structure

Your project should look like this:

```
temperature_monitor/
├── main.py
├── requirements.txt
├── services/
│   ├── __init__.py
│   ├── auth_manager.py
│   ├── gmail_service.py
│   ├── sheets_service.py
│   ├── location_manager.py
│   ├── pdf_parser.py
│   └── temperature_scheduler.py
├── web_interface/
│   ├── __init__.py
│   ├── app.py
│   └── static/app.js
└── config/
    ├── credentials.json        # ← Your OAuth credentials
    ├── settings.json           # ← Your configuration
    └── settings.example.json   # ← Example template
```

## 🚀 Step 4: First Run

### 4.1 Start the Application

```bash
python main.py
```

**Expected behavior:**
- Application window opens
- System tray icon appears
- Web browser opens to setup wizard
- Console shows startup messages

### 4.2 Troubleshooting First Run

**If application fails to start:**

```bash
# Check Python path
which python

# Verify dependencies
pip list | grep -E "(flask|pyttsx3|google)"

# Check for errors
python main.py 2>&1 | tee startup.log
```

**Common issues:**
- Missing dependencies → Run `pip install -r requirements.txt`
- Port conflict → Change port in `config/settings.json`
- Permission errors → Run as administrator (Windows) or check file permissions

## 🌐 Step 5: Web Setup Wizard

### 5.1 Connect Gmail Account

1. In the web interface, click **"Connect Gmail Account"**
2. Browser opens Google OAuth page
3. **Sign in** with your Gmail account
4. **Allow** Temperature Monitor access to:
   - Read Gmail messages
   - Create/edit Google Sheets
   - Access Google Drive
5. Return to web interface - should show "✅ Connected"

### 5.2 Configure Email Filters

Configure which emails to monitor:

**Sender Addresses:**
```
notifications@cleverlogger.com
alerts@yourmonitoring.com
reports@temperaturesystem.net
```

**Subject Keywords:** (emails must contain at least one)
```
min-max
temperature report
daily summary
```

**Exclude Keywords:** (skip emails containing these)
```
test
configuration
welcome
```

**Options:**
- ✅ **Require PDF attachment** (recommended for Clever Logger)
- ✅ **Auto-update when new emails arrive**

### 5.3 Set Temperature Thresholds

Choose monitoring type:

**🥶 Fridge Temperature (Recommended for pharmacy)**
- Range: 2°C - 8°C
- Use: Medicine storage, vaccines

**🌡️ Room Temperature**
- Alert: Above 25°C  
- Use: General medicine storage

**⚙️ Custom Range**
- Set your own min/max values
- Custom alert name

### 5.4 Configure Voice Announcements

**Daily Time:** When to announce (24-hour format)
```
09:00  # 9:00 AM
```

**Volume:** Voice announcement level
- Low / Medium / High

**Announcement Content:**
```
Daily temperature check required. Please verify all temperatures are within safe ranges.
```

**Staff Confirmation:**
- ✅ **Require staff confirmation** (recommended)

## 📊 Step 6: Google Sheets Setup

### 6.1 Automatic Spreadsheet Creation

The system automatically creates a Google Sheets spreadsheet when:
- First temperature data is logged
- Manual announcement is run
- Scheduled announcement executes

### 6.2 Spreadsheet Structure

Each monitoring location gets its own tab:
- **Date** - YYYY-MM-DD format
- **Day of Week** - Monday, Tuesday, etc.
- **Min (°C)** - Minimum temperature recorded
- **Max (°C)** - Maximum temperature recorded  
- **Logged Time** - When data was logged
- **Staff Name** - Staff confirmation

### 6.3 Manual Spreadsheet Access

Click **"📊 Open Google Sheets"** in web interface or visit:
```
https://docs.google.com/spreadsheets/d/[SPREADSHEET_ID]/edit
```

## 🔄 Step 7: Scheduler Configuration

### 7.1 Enable Daily Scheduler

1. In web interface, go to **"Temperature Scheduler"** section
2. Set **"Daily Announce Time"**: `09:00`
3. Set **"Search Hours Back"**: `24`
4. ✅ **Enable Daily Scheduler**
5. ✅ **Auto-log to Google Sheets**
6. ✅ **Require Staff Confirmation**
7. Click **"💾 Save Scheduler Settings"**
8. Click **"▶️ Start Scheduler"**

### 7.2 Test the System

**Test Voice Alert:**
```
Click "🔊 Test Voice Alert" button
```

**Test Gmail Connection:**
```
Click "Test Gmail Connection" button
```

**Test Manual Announcement:**
```
Click "🧪 Test Manual Announcement" button
```

## 🔧 Step 8: Advanced Configuration

### 8.1 Email Filter Tuning

Monitor the **"Recent Activity"** log for:
- Emails found vs expected
- False positives (wrong emails)
- Missing emails

**Adjust filters if needed:**
- Add more sender addresses
- Refine subject keywords
- Add exclude keywords for noise

### 8.2 PDF Format Support

The system works best with **Clever Logger** format PDFs containing:
- Location Details sections
- Temperature recordings tables
- Min/max temperature data

**For other formats:** The system falls back to email body parsing.

### 8.3 Location Discovery

The system automatically discovers monitoring locations from:
- PDF Location Details sections
- Email subject lines
- Email body content

**View discovered locations:**
```
Check logs for: "Extracted location: [Name]"
```

## 🚨 Step 9: Troubleshooting

### 9.1 Common Issues

**Gmail Authentication Fails:**
- Check credentials.json is in config/ folder
- Verify OAuth consent screen includes your email
- Clear browser cache and retry

**No Emails Found:**
- Test email filters with longer time range
- Check sender addresses match exactly
- Verify subject keywords appear in emails

**Voice Announcements Not Working:**
- Check TTS engine installation
- Verify quiet hours settings
- Test with "Test Voice Alert" button

**Google Sheets Not Updating:**
- Check Google Sheets API is enabled
- Verify spreadsheet permissions
- Test with "Test Manual Announcement"

### 9.2 Debug Mode

Enable detailed logging:

```bash
# Run with debug output
python main.py --debug

# Or check log files
tail -f logs/temperature_monitor.log
```

### 9.3 Reset Configuration

If needed, reset to defaults:

```bash
# Backup current settings
cp config/settings.json config/settings.backup.json

# Reset to defaults
cp config/settings.example.json config/settings.json

# Restart application
python main.py
```

## ✅ Step 10: Verification Checklist

Before going live, verify:

- [ ] **Gmail connected** and finding temperature emails
- [ ] **Email filters** configured for your monitoring system
- [ ] **Temperature thresholds** set appropriately  
- [ ] **Voice announcements** working and audible
- [ ] **Google Sheets** creating and updating correctly
- [ ] **Scheduler** running and announcing daily
- [ ] **Staff confirmation** process understood
- [ ] **System tray** icon visible and functional

## 🎯 Step 11: Going Live

### 11.1 Production Checklist

- [ ] Test system for at least 3 days
- [ ] Train staff on confirmation process
- [ ] Set up backup monitoring
- [ ] Document any custom configurations
- [ ] Plan for maintenance windows

### 11.2 Maintenance

**Daily:** Check recent activity log
**Weekly:** Verify Google Sheets updates
**Monthly:** Review and update email filters
**Quarterly:** Update Python dependencies

---

## 🆘 Need Help?

1. **Check Recent Activity log** in the application
2. **Review console output** for error messages
3. **Test individual components** (Gmail, Sheets, Voice)
4. **Verify Google Cloud Console** API access
5. **Check file permissions** and directory structure

**Remember:** The system is designed to be robust - most issues are configuration-related and easily resolved! 🚀