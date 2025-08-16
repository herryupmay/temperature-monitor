# 🌡️ Temperature Monitor - Complete Setup Guide

## 📋 **What This Software Does**

Temperature Monitor automatically:
- ✅ **Reads temperature emails** from Clever Logger and similar systems
- ✅ **Announces daily temperatures** with voice alerts
- ✅ **Logs data to Google Sheets** for record keeping
- ✅ **Detects temperature breaches** and alerts staff
- ✅ **Runs automatically** when Windows starts

---

## 🚀 **Quick Start (Overview)**

1. **Download & Extract** the portable app
2. **Set up Google Cloud Console** (10 minutes, one-time setup)
3. **Run the app** and connect Gmail
4. **Configure settings** through web interface
5. **Test the system** and you're done!

---

## 📁 **Step 1: Download & Install**

### 1.1 Download
1. Go to: `https://github.com/herryupmay/temperature-monitor/releases`
2. Download: **`TemperatureMonitor_v1.0_Portable.zip`**
3. **Extract** the zip file to a permanent location (e.g., `C:\TemperatureMonitor\`)

### 1.2 First Run Test
1. **Double-click** `TemperatureMonitor.exe`
2. **Look for system tray icon** (blue thermometer in bottom-right corner)
3. **Right-click the tray icon** → **Click "Show Window"** to open the desktop app
4. **Manually open web browser** and go to: `http://localhost:8080`

**✅ If the system tray icon appears and the web interface loads, continue to Step 2!**

---

## ☁️ **Step 2: Google Cloud Console Setup** 

**⚠️ Important:** This is a one-time setup that takes about 10 minutes. You need this to connect to Gmail.

### 2.1 Create Google Cloud Project

1. **Go to:** [Google Cloud Console](https://console.cloud.google.com/)
2. **Sign in** with the Gmail account that receives temperature emails
3. **Click** the project dropdown (top-left, next to "Google Cloud")
4. **Click** "NEW PROJECT"
5. **Project name:** `Temperature Monitor`
6. **Click** "CREATE"
7. **Wait** for project creation (30 seconds)
8. **Make sure** the new project is selected (check top-left dropdown)

### 2.2 Enable Required APIs

1. **In the left menu, click:** "APIs & Services" → "Library"
2. **Search for:** `Gmail API`
3. **Click** on "Gmail API" → **Click** "ENABLE"
4. **Go back** to Library (use browser back button)
5. **Search for:** `Google Sheets API`
6. **Click** on "Google Sheets API" → **Click** "ENABLE"
7. **Go back** to Library
8. **Search for:** `Google Drive API`
9. **Click** on "Google Drive API" → **Click** "ENABLE"

### 2.3 Configure OAuth Consent Screen

1. **In the left menu, click:** "APIs & Services" → "OAuth consent screen"
2. **Choose:** "External" → **Click** "CREATE"
3. **Fill in required fields:**
   - **App name:** `Temperature Monitor`
   - **User support email:** Your email address
   - **Developer contact email:** Your email address
4. **Click** "SAVE AND CONTINUE"
5. **Scopes page:** Just click "SAVE AND CONTINUE"
6. **Test users page:** 
   - **Click** "ADD USERS"
   - **Enter** your Gmail address
   - **Click** "ADD"
   - **Click** "SAVE AND CONTINUE"
7. **Summary page:** **Click** "BACK TO DASHBOARD"

### 2.4 Create Credentials

1. **In the left menu, click:** "APIs & Services" → "Credentials"
2. **Click** "CREATE CREDENTIALS" → "OAuth client ID"
3. **If prompted about consent screen:** Click "CONFIGURE CONSENT SCREEN" and complete 2.3 above
4. **Application type:** Desktop application
5. **Name:** `Temperature Monitor Desktop`
6. **Click** "CREATE"
7. **Download dialog appears:** **Click** "DOWNLOAD JSON"
8. **Save the file** - it will be named something like `client_secret_xxxxx.json`

### 2.5 Install Credentials File

1. **Rename** the downloaded file to exactly: `credentials.json`
2. **Copy** it to your Temperature Monitor folder: `C:\TemperatureMonitor\config\credentials.json`

**✅ Google Cloud setup complete!**

---

## 🔗 **Step 3: Connect Gmail**

### 3.1 Start the Application
1. **Double-click** `TemperatureMonitor.exe`
2. **Look for system tray icon** (blue thermometer)
3. **Open web browser** and go to: `http://localhost:8080`
4. **Tip:** Right-click tray icon → "Open Web Interface" for quick access

### 3.2 Connect Gmail Account
1. **In the web interface, find:** "Gmail Integration" section
2. **Click** "Connect Gmail Account"
3. **Browser opens** Google's permission page
4. **Sign in** with your Gmail account (if not already signed in)
5. **Click** "Allow" to grant permissions:
   - Read Gmail messages
   - Create/edit Google Sheets
   - Access Google Drive
6. **Return to** the Temperature Monitor web page
7. **Should show:** "✅ Gmail connected: your-email@gmail.com"

**✅ Gmail connection complete!**

---

## ⚙️ **Step 4: Configure Email Filters**

**Tell the system which emails contain temperature data.**

### 4.1 Configure Sender Addresses
1. **In "Email Filter Settings" section**
2. **Sender Email Addresses box:** Enter your temperature system's email
   - Example: `notifications@cleverlogger.com`
   - **One email per line** if you have multiple
3. **Required Subject Keywords:** Words that must appear in email subjects
   - Example: `min-max` or `temperature report`
   - **One keyword per line**
4. **Exclude Keywords:** Skip emails containing these words
   - Example: `test`, `configuration`
5. **Options:**
   - ✅ **Require PDF attachment** (recommended for Clever Logger)
   - ✅ **Auto-update when new emails arrive**

### 4.2 Test Email Filters
1. **Click** "Test Filters"
2. **Should show:** "Found X emails matching your filters"
3. **If no emails found:** Check your sender addresses and keywords
4. **Click** "Save Email Filters"

**✅ Email filters configured!**

---

## 🌡️ **Step 5: Temperature Settings**

### 5.1 Choose Temperature Type
**Select your monitoring type:**

- **🥶 Fridge Temperature:** 2°C - 8°C (medicine storage)
- **🌡️ Room Temperature:** Alert above 25°C
- **⚙️ Custom Range:** Set your own thresholds

### 5.2 Configure Daily Scheduler
1. **Scroll to "Temperature Scheduler" section**
2. **Daily Announce Time:** When to check temperatures (e.g., `09:00`)
3. **✅ Enable Daily Scheduler**
4. **✅ Auto-log to Google Sheets**
5. **✅ Require Staff Confirmation** (recommended)
6. **Click** "Save Scheduler Settings"
7. **Click** "Start Scheduler"

**✅ Should show: "🟢 Running (Enabled)"**

---

## 🖥️ **Step 6: Windows Auto-Startup (Optional)**

**Make Temperature Monitor start automatically when Windows boots.**

1. **Scroll to "Windows Auto-Startup" section**
2. **✅ Check** "Enable Auto-Startup with Windows"
3. **Click** "Save Auto-Startup Setting"
4. **Should show:** "✅ Enabled"

**✅ Auto-startup configured!**

---

## 🧪 **Step 7: Test the System**

### 7.1 Test Voice Alerts
1. **Click** "Test Voice Alert"
2. **Should hear:** Voice announcement through speakers
3. **Adjust volume** if needed

### 7.2 Test Temperature Check
1. **Click** "Test Manual Announcement"
2. **Should show:** Results of temperature email search
3. **Check Google Sheets:** Should create/update spreadsheet automatically

### 7.3 Test Gmail Connection
1. **Click** "Test Gmail Connection"
2. **Should show:** Number of temperature emails found

**✅ All tests passing = system ready!**

---

## 📊 **Using Google Sheets**

### Automatic Logging
- **Spreadsheet created automatically** on first temperature check
- **Separate tabs** for each monitoring location
- **Daily entries** with date, temperatures, and staff confirmation

### Access Your Sheets
1. **In web interface, click:** "Open Google Sheets"
2. **Or visit:** [Google Sheets](https://sheets.google.com) and look for "Temperature Monitor" spreadsheet

---

## 🔧 **Daily Operation**

### What Happens Automatically
- **Daily at scheduled time:** System checks emails for temperature data
- **Voice announcement:** Reports temperatures and any breaches
- **Google Sheets:** Updated with latest data
- **Staff confirmation:** Required to complete the daily check

### What Staff Need to Do
1. **Listen for voice announcement** at scheduled time
2. **Check actual temperature loggers** to verify readings
3. **Confirm in system** that temperatures are safe
4. **If breach detected:** Follow your temperature breach procedures

---

## ❗ **Troubleshooting**

### Gmail Connection Issues
**Problem:** "Gmail not connected" or authentication errors
**Solution:**
1. Check `credentials.json` file is in `config/` folder
2. Verify your email is in Google Cloud Console test users
3. Try disconnecting and reconnecting Gmail

### No Emails Found
**Problem:** "No temperature data found"
**Solution:**
1. Check sender email addresses match exactly
2. Verify subject keywords appear in email subjects
3. Test with longer time range (48 hours)

### Voice Alerts Not Working
**Problem:** No voice announcements
**Solution:**
1. Check speakers/volume are working
2. Test during allowed hours (not in quiet hours)
3. Click "Test Voice Alert" button

### Scheduler Not Running
**Problem:** Shows "🔴 Stopped"
**Solution:**
1. Click "Start Scheduler" button
2. Check Gmail is connected
3. Restart the application

### Auto-Startup Not Working
**Problem:** Doesn't start with Windows
**Solution:**
1. Check Windows startup programs (msconfig)
2. Run as Administrator once
3. Re-enable auto-startup in settings

---

## 📞 **Support**

### Log Files
- **Check recent activity** in the desktop application
- **Look for error messages** in red text
- **Test individual components** (Gmail, Voice, Sheets)

### Getting Help
1. **Check the troubleshooting section** above
2. **Test each component** individually
3. **Note any error messages** for support

---

## 🔒 **Security & Privacy**

- **Your credentials stay on your computer** - not shared with anyone
- **Google Sheets accessible only to you** (unless you share them)
- **No temperature data** sent to third parties
- **All processing happens locally** on your computer

---

## ✅ **Setup Complete!**

**Your Temperature Monitor is now:**
- ✅ **Connected to Gmail** and reading temperature emails
- ✅ **Scheduled for daily** automated temperature checks  
- ✅ **Logging data** to Google Sheets automatically
- ✅ **Starting automatically** with Windows (if enabled)
- ✅ **Ready for daily operation!**

**🎉 Congratulations! Your temperature monitoring system is fully operational.**
