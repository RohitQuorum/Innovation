# 📘 Quick Guide: Adding a New Server

Follow these steps to add a new server to the monitoring dashboard.

## Prerequisites

✅ Remote WMI/PowerShell access to the new server  
✅ Python installed on your monitoring machine  
✅ Administrator rights to configure firewall (if needed for team access)

---

## Step 1: Copy Server Configuration

```powershell
Copy-Item perf_server3.py perf_server4.py
```

## Step 2: Edit Server Configuration

Open `perf_server4.py` and update these 4 lines (around lines 19-22):

```python
CSV_DIR = "perf4"                          # Change to perf4
PORT = 8893                                # Change to 8893
TARGET_SERVER = "NEWSERVER.qdev.net"       # Change to your server name
COLLECTOR_LOG = "collector4.log"           # Change to collector4.log
```

**Quick Find & Replace:**
- Find: `perf3` → Replace: `perf4`
- Find: `8892` → Replace: `8893`
- Find: `QDTQENMT02.qdev.net` → Replace: `NEWSERVER.qdev.net`
- Find: `collector3.log` → Replace: `collector4.log`

## Step 3: Create Launcher Script

```powershell
Copy-Item start_dashboard3.bat start_dashboard4.bat
```

Edit `start_dashboard4.bat` and update:

```batch
title Performance Dashboard - NEWSERVER
echo Server 4: NEWSERVER (Port 8893)
echo   http://localhost:8893
start http://localhost:8893
python perf_server4.py
```

## Step 4: Test Server Access

Verify you can reach the new server:

```powershell
Test-WSMan -ComputerName "NEWSERVER.qdev.net"
Get-Process -ComputerName "NEWSERVER.qdev.net" -Name "System"
```

✅ If both commands succeed, you have proper access.

## Step 5: Update Hub Page

Open `hub.html` and add a new server card before the "Add New Server" placeholder:

```html
<!-- Server 4 -->
<div class="server-card" onclick="openDashboard(8893)" style="cursor: pointer;">
    <div class="server-number">4</div>
    <div class="server-name">NEWSERVER</div>
    <div class="server-url">NEWSERVER.qdev.net</div>
    <div class="status online">
        <span class="status-dot"></span>
        Port 8893
    </div>
    <div class="server-specs">
        <div class="spec-item">
            <span class="spec-label">Type:</span>
            <span>Application Server</span>
        </div>
        <div class="spec-item">
            <span class="spec-label">RAM:</span>
            <span>32 GB</span>
        </div>
        <div class="spec-item">
            <span class="spec-label">Data:</span>
            <span>perf4\</span>
        </div>
    </div>
</div>
```

## Step 6: Update Master Launcher

Open `start_all_dashboards.bat` and add:

**After "Starting 3 servers..." change to "Starting 4 servers..."**

**Add before the hub launch section:**

```batch
start "Server 4 - NEWSERVER" /MIN cmd /k "cd /d "%~dp0" && python perf_server4.py"
timeout /t 3 /nobreak >nul
echo [4/4] Started NEWSERVER (Port 8893)
```

**Update the URLs section:**

```batch
echo  Server 1: http://localhost:8890
echo  Server 2: http://localhost:8891
echo  Server 3: http://localhost:8892
echo  Server 4: http://localhost:8893
```

## Step 7: Open Firewall (For Network Access)

Run PowerShell **as Administrator**:

```powershell
New-NetFirewallRule -DisplayName "Dashboard Server 4" -Direction Inbound -LocalPort 8893 -Protocol TCP -Action Allow
```

## Step 8: Test the New Server

1. **Start the new dashboard:**
   ```batch
   start_dashboard4.bat
   ```

2. **Verify it's running:**
   ```powershell
   netstat -ano | findstr ":8893" | findstr "LISTENING"
   ```

3. **Access the dashboard:**
   - Local: `http://localhost:8893`
   - Network: `http://10.11.33.183:8893`

4. **Check hub page:**
   - Access: `http://10.11.33.183:8890/hub.html`
   - Click the new Server 4 card

---

## 📋 Quick Checklist

- [ ] Copied perf_server3.py → perf_server4.py
- [ ] Updated CSV_DIR, PORT, TARGET_SERVER, COLLECTOR_LOG
- [ ] Created start_dashboard4.bat
- [ ] Verified server access with Test-WSMan and Get-Process
- [ ] Added server card to hub.html
- [ ] Updated start_all_dashboards.bat
- [ ] Opened firewall port 8893
- [ ] Tested individual dashboard
- [ ] Tested hub page access

---

## 🔄 For Server 5, 6, 7...

Simply repeat the process, incrementing:
- File names: `perf_server5.py`, `start_dashboard5.bat`
- Port number: `8894`, `8895`, `8896`...
- Data folder: `perf5`, `perf6`, `perf7`...
- Log file: `collector5.log`, `collector6.log`...

---

## ❓ Troubleshooting

### "Access Denied" errors
- Check you have admin rights on the target server
- Verify WMI/Remote PowerShell is enabled
- Check Windows Firewall on the target server

### Server not appearing in hub
- Clear browser cache (Ctrl+F5)
- Verify Python server is running: `netstat -ano | findstr ":8893"`
- Check hub.html was saved correctly

### No data showing
- Wait 30 seconds for first data collection
- Check collector log: `collector4.log`
- Verify perf4 folder was created automatically

---

**Need help?** Check the main README.md or contact the maintainer.
