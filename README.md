# Performance Dashboard - Multi-Server Monitoring

A lightweight performance monitoring solution for Windows servers. Monitor CPU, Memory, and Process metrics across multiple servers from a centralized web dashboard.

## 🚀 Features

- **Real-time Monitoring**: Track CPU and Memory usage with 5-second granularity
- **Multi-Server Support**: Monitor multiple servers simultaneously
- **Process Tracking**: View top 15 CPU/Memory consuming processes
- **Historical Data**: 7-day data retention with timeline views
- **Network Accessible**: Share dashboards with your team via network IP
- **Zero Dependencies**: Uses Python's built-in HTTP server and Chart.js

## 📋 Requirements

- **Python 3.x** (built-in on Windows Server 2012+)
- **PowerShell 5.1+** (built-in on Windows)
- **Network Access**: Remote WMI/PowerShell access to monitored servers
- **Firewall**: Ports 8890, 8891, 8892 opened for team access

## 🏗️ Architecture

```
Innovation/
├── Collect-PerfData.ps1       # PowerShell collector script
├── perf_server.py             # Server 1 backend (QDDEATAPP01)
├── perf_server2.py            # Server 2 backend (QDTQENWEB02)
├── perf_server3.py            # Server 3 backend (QDTQENMT02)
├── perf_dashboard.html        # Dashboard UI
├── hub.html                   # Multi-server hub page
├── start_all_dashboards.bat   # Launch all servers
├── perf/                      # Server 1 data directory
├── perf2/                     # Server 2 data directory
└── perf3/                     # Server 3 data directory
```

## 🔧 Configuration

### Current Servers

| Server | Port | Data Folder | Target Server |
|--------|------|-------------|---------------|
| Server 1 | 8890 | perf/ | QDDEATAPP01.qdev.net |
| Server 2 | 8891 | perf2/ | QDTQENWEB02.qdev.net |
| Server 3 | 8892 | perf3/ | QDTQENMT02.qdev.net |

### Network Access

- **Your Machine**: `http://localhost:8890/hub.html`
- **Team Access**: `http://10.11.33.183:8890/hub.html`

## 🚦 Quick Start

### Start All Dashboards

```batch
start_all_dashboards.bat
```

This will:
1. Launch all 3 server monitoring processes
2. Open the hub page in your browser
3. Start data collection from each server

### Start Individual Dashboard

```batch
start_dashboard.bat   # Server 1
start_dashboard2.bat  # Server 2
start_dashboard3.bat  # Server 3
```

### Stop All Dashboards

Simply close the terminal windows running the Python servers.

## ➕ Adding a New Server

1. **Copy server file**:
   ```powershell
   Copy-Item perf_server3.py perf_server4.py
   ```

2. **Edit configuration** in `perf_server4.py`:
   ```python
   CSV_DIR = "perf4"
   PORT = 8893
   TARGET_SERVER = "NEWSERVER.qdev.net"
   COLLECTOR_LOG = "collector4.log"
   ```

3. **Create launcher**:
   ```batch
   Copy start_dashboard3.bat start_dashboard4.bat
   # Edit to use port 8893 and server name
   ```

4. **Update hub.html**:
   - Add new server card with `onclick="openDashboard(8893)"`

5. **Open firewall** (as Administrator):
   ```powershell
   New-NetFirewallRule -DisplayName "Dashboard Server 4" -Direction Inbound -LocalPort 8893 -Protocol TCP -Action Allow
   ```

6. **Update `start_all_dashboards.bat`** to include the new server

## 📊 Data Collection

- **Frequency**: Every 5 seconds
- **Publishing**: CSV files updated every 30 seconds
- **Retention**: 7 days (automatic cleanup)
- **Formats**: 
  - `host_{server}_{date}.csv` - Host-level metrics
  - `all_{server}_{date}.csv` - Process-level metrics

## 🔒 Security

- Data collection requires **remote WMI access** to monitored servers
- Dashboard web interface is **read-only**
- No authentication (suitable for internal networks only)
- Use Windows Firewall to restrict access if needed

## 🛠️ Troubleshooting

### Servers not starting

Check Python is installed:
```powershell
python --version
```

### Can't access from network

Open firewall ports (as Administrator):
```powershell
New-NetFirewallRule -DisplayName "Dashboard Server 1" -Direction Inbound -LocalPort 8890 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Dashboard Server 2" -Direction Inbound -LocalPort 8891 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "Dashboard Server 3" -Direction Inbound -LocalPort 8892 -Protocol TCP -Action Allow
```

### No data appearing

Verify access to remote server:
```powershell
Test-WSMan -ComputerName "SERVER.qdev.net"
Get-Process -ComputerName "SERVER.qdev.net" -Name "System"
```

## 📝 Technical Details

### Data Flow

1. **Collector**: PowerShell script runs on your machine, queries remote servers via WMI
2. **Storage**: Metrics saved to CSV files in respective `perf*/` folders
3. **Backend**: Python HTTP server reads CSVs and serves JSON APIs
4. **Frontend**: HTML dashboard fetches data via AJAX and renders with Chart.js

### API Endpoints

- `GET /` - Dashboard UI
- `GET /hub.html` - Multi-server hub
- `GET /api/info` - Server information
- `GET /api/dates` - Available data dates
- `GET /api/host?date=YYYY-MM-DD` - Host metrics
- `GET /api/cpu-alerts?date=YYYY-MM-DD&threshold=80` - CPU alerts
- `GET /api/mem-alerts?date=YYYY-MM-DD&threshold=80` - Memory alerts
- `GET /api/top-processes?date=YYYY-MM-DD` - Top processes

## 📄 License

Internal use only - Quorum Business Solutions

## 👤 Maintainer

Created by: Rohit Gaikwad  
Last Updated: March 2026
