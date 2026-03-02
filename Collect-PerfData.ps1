<#
.SYNOPSIS
  Continuously collects CPU and Memory metrics from a remote Windows server.
.DESCRIPTION
  Writes two CSV files per day (via a _writing intermediate file):
    - all_<server>_<date>.csv   : Top N processes by CPU and MEM every interval
    - host_<server>_<date>.csv  : Host-level CPU and RAM every interval
  Threshold logic is handled by the dashboard UI, not here.
.EXAMPLE
  .\Collect-PerfData.ps1 -Server "QDDEATAPP01.qdev.net"
  .\Collect-PerfData.ps1 -Server "QDDEATAPP01.qdev.net" -IntervalSeconds 10 -TopN 20
#>
param(
  [Parameter(Mandatory=$true)]
  [string]$Server,

  [int]$IntervalSeconds    = 5,
  [int]$TopN               = 15,
  [string]$OutDir          = "C:\Users\rohit.gaikwad\OneDrive - Quorum Business Solutions\perf",
  [int]$RetentionDays      = 7,
  [int]$PublishEverySeconds = 30
)

Set-StrictMode -Version Latest

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# ── Helpers ───────────────────────────────────────────────────────────────────
function Get-SafeServerName([string]$name) {
  (($name -replace '[^A-Za-z0-9_.-]','_') -replace '\.','_')
}
function DateStamp     { Get-Date -Format "yyyy-MM-dd" }
function TimestampNow  { Get-Date -Format "yyyy-MM-dd HH:mm:ss" }

# ── File paths ────────────────────────────────────────────────────────────────
function AllPublishedPath  { Join-Path $OutDir ("all_{0}_{1}.csv"  -f (Get-SafeServerName $Server),(DateStamp)) }
function HostPublishedPath { Join-Path $OutDir ("host_{0}_{1}.csv" -f (Get-SafeServerName $Server),(DateStamp)) }
function AllWriterPath     { (AllPublishedPath).Replace(".csv","_writing.csv") }
function HostWriterPath    { (HostPublishedPath).Replace(".csv","_writing.csv") }

function EnsureHeaders {
  $allW  = AllWriterPath
  $hostW = HostWriterPath
  if (-not (Test-Path $allW))  { "Timestamp,Server,Metric,ProcessName,ProcessId,Value,Unit,ServiceNames" | Out-File -FilePath $allW  -Encoding utf8 }
  if (-not (Test-Path $hostW)) { "Timestamp,Server,HostCpu_Pct,TotalRam_MB,FreeRam_MB,UsedRam_MB,UsedRam_Pct" | Out-File -FilePath $hostW -Encoding utf8 }
}

# ── Cleanup ───────────────────────────────────────────────────────────────────
function Cleanup-OldLogs {
  $safe   = Get-SafeServerName $Server
  $cutoff = (Get-Date).AddDays(-$RetentionDays)
  foreach ($prefix in @("all_","host_","cpu_thr_","mem_thr_")) {
    Get-ChildItem -Path $OutDir -Filter "${prefix}${safe}_*.csv" -File -EA SilentlyContinue |
      Where-Object { $_.LastWriteTime -lt $cutoff } |
      Remove-Item -Force -EA SilentlyContinue
  }
}

# ── Service name cache (batch-fetched, refreshed every 5 min) ─────────────────
$script:svcCache = @{}
$script:svcCacheTime = Get-Date "2000-01-01"

function Refresh-ServiceCache {
  try {
    $allSvcs = Get-WmiObject -ComputerName $Server -Class Win32_Service -EA Stop |
      Where-Object { $_.ProcessId -gt 0 } |
      Select-Object ProcessId, Name
    $newCache = @{}
    foreach ($s in $allSvcs) {
      $pid = [int]$s.ProcessId
      if ($newCache.ContainsKey($pid)) {
        $newCache[$pid] = $newCache[$pid] + "|" + $s.Name
      } else {
        $newCache[$pid] = $s.Name
      }
    }
    $script:svcCache = $newCache
    $script:svcCacheTime = Get-Date
  } catch {
    # If WMI service query fails, keep old cache
  }
}

function Get-CachedServiceName([int]$processId) {
  if ($processId -le 0) { return "" }
  # Refresh cache every 5 minutes
  if ((New-TimeSpan -Start $script:svcCacheTime -End (Get-Date)).TotalMinutes -ge 5) {
    Refresh-ServiceCache
  }
  if ($script:svcCache.ContainsKey($processId)) {
    return $script:svcCache[$processId]
  }
  return ""
}

# ── IO helpers ────────────────────────────────────────────────────────────────
function Append-LineSafe {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$Line,
    [int]$Retries = 8,
    [int]$DelayMs = 150
  )
  for ($i = 1; $i -le $Retries; $i++) {
    try {
      [System.IO.File]::AppendAllText($Path, $Line + [Environment]::NewLine, [System.Text.Encoding]::UTF8)
      return $true
    } catch { Start-Sleep -Milliseconds $DelayMs }
  }
  return $false
}

function Publish-SnapshotSafe {
  param(
    [Parameter(Mandatory)][string]$WriterPath,
    [Parameter(Mandatory)][string]$PublishedPath
  )
  for ($i = 1; $i -le 6; $i++) {
    try {
      Copy-Item -Path $WriterPath -Destination $PublishedPath -Force -ErrorAction Stop
      return $true
    } catch { Start-Sleep -Milliseconds 250 }
  }
  return $false
}

function Get-TotalRamMB {
  $cs = Get-WmiObject -ComputerName $Server -Class Win32_ComputerSystem -ErrorAction Stop
  [math]::Round(($cs.TotalPhysicalMemory / 1MB), 2)
}

# ── State ─────────────────────────────────────────────────────────────────────
$totalRamMB      = $null
$lastRamRefresh  = Get-Date "2000-01-01"
$ramRefreshMin   = 60
$lastPublish     = Get-Date "2000-01-01"
$cycleCount      = 0

Write-Host "=== Performance Collector ==="
Write-Host "Server   : $Server"
Write-Host "Interval : ${IntervalSeconds}s | Top $TopN processes | Publish every ${PublishEverySeconds}s"
Write-Host "Output   : $OutDir"
Write-Host "Press Ctrl+C to stop.`n"

# Pre-populate service cache at startup
Write-Host "Loading service cache..."
Refresh-ServiceCache
Write-Host "Cached $($script:svcCache.Count) PID-to-service mappings.`n"

# ── Main loop ─────────────────────────────────────────────────────────────────
while ($true) {
  try {
    Cleanup-OldLogs
  } catch {}

  EnsureHeaders

  $ts    = TimestampNow
  $allW  = AllWriterPath
  $hostW = HostWriterPath

  try {
    # Refresh total RAM periodically
    if (-not $totalRamMB -or ((New-TimeSpan -Start $lastRamRefresh -End (Get-Date)).TotalMinutes -ge $ramRefreshMin)) {
      $totalRamMB     = Get-TotalRamMB
      $lastRamRefresh = Get-Date
    }

    # ── Host-level metrics ──
    $hostCpuObj = Get-WmiObject -ComputerName $Server -Class Win32_PerfFormattedData_PerfOS_Processor `
                    -Filter "Name='_Total'" -ErrorAction Stop
    $osObj      = Get-WmiObject -ComputerName $Server -Class Win32_OperatingSystem -ErrorAction Stop

    $hostCpuPct = [math]::Round([double]$hostCpuObj.PercentProcessorTime, 2)
    $freeRamMB  = [math]::Round(($osObj.FreePhysicalMemory / 1024), 2)
    $usedRamMB  = if ($totalRamMB -gt 0) { [math]::Round(($totalRamMB - $freeRamMB), 2) } else { 0 }
    $usedPct    = if ($totalRamMB -gt 0) { [math]::Round((($usedRamMB / $totalRamMB) * 100), 2) } else { 0 }

    [void](Append-LineSafe -Path $hostW -Line ("{0},{1},{2},{3},{4},{5},{6}" -f $ts,$Server,$hostCpuPct,$totalRamMB,$freeRamMB,$usedRamMB,$usedPct))

    # ── Process metrics ──
    $procRows = Get-WmiObject -ComputerName $Server -Class Win32_PerfFormattedData_PerfProc_Process -ErrorAction Stop |
      Where-Object { $_.Name -and $_.Name -notin @("_Total","Idle") }

    # Top MEM
    $topMem = $procRows | Sort-Object WorkingSet -Descending | Select-Object -First $TopN
    foreach ($p in $topMem) {
      $processId = [int]$p.IDProcess
      $svc   = Get-CachedServiceName -processId $processId
      $memMB = [math]::Round(($p.WorkingSet / 1MB), 2)
      [void](Append-LineSafe -Path $allW -Line ("{0},{1},MEM,{2},{3},{4},MB,{5}" -f $ts,$Server,$p.Name,$processId,$memMB,$svc))
    }

    # Top CPU
    $topCpu = $procRows | Sort-Object PercentProcessorTime -Descending | Select-Object -First $TopN
    foreach ($p in $topCpu) {
      $processId = [int]$p.IDProcess
      $svc    = Get-CachedServiceName -processId $processId
      $cpuPct = [math]::Round([double]$p.PercentProcessorTime, 2)
      [void](Append-LineSafe -Path $allW -Line ("{0},{1},CPU,{2},{3},{4},pct,{5}" -f $ts,$Server,$p.Name,$processId,$cpuPct,$svc))
    }

    $cycleCount++

  } catch {
    $msg = $_.Exception.Message -replace "`r"," " -replace "`n"," " -replace ","," "
    try {
      [void](Append-LineSafe -Path $allW  -Line ("{0},{1},ERROR,Message,,{2},text," -f $ts,$Server,$msg))
      [void](Append-LineSafe -Path $hostW -Line ("{0},{1},0,0,0,0,0" -f $ts,$Server))
    } catch {}
  }

  # Publish snapshots
  $sinceLast = (New-TimeSpan -Start $lastPublish -End (Get-Date)).TotalSeconds
  if ($sinceLast -ge $PublishEverySeconds -or ($cycleCount -eq 1)) {
    try {
      [void](Publish-SnapshotSafe -WriterPath (AllWriterPath)  -PublishedPath (AllPublishedPath))
      [void](Publish-SnapshotSafe -WriterPath (HostWriterPath) -PublishedPath (HostPublishedPath))
      $lastPublish = Get-Date
    } catch {}
  }

  Start-Sleep -Seconds $IntervalSeconds
}
