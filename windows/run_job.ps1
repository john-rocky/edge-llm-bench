<#
Runs one job on this Windows host: the job.json scripts/run_windows_matrix.py plans
(launches = tool + args + runs), every run one fresh engine process with stdout and stderr in one
file, the host facts and the sha256 of every engine file in host.json. Windows PowerShell 5.1.

  powershell -NoProfile -ExecutionPolicy Bypass -File run_job.ps1 -JobDir <dir> -LogDir <dir>
      -ModelDir <dir> -EngineDir <dir> [-BusyFile <file> -BusyLabel <text>] [-DeviceModel <text>]
      [-LitertDirName <dir under EngineDir>] [-PurgeEngineCaches] [-QuietCpuPercent N] [-QuietGpuMiB N]
      [-QuietGpuEnginePercent N] [-QuietWaitMinutes N] [-GpuSampleSeconds N]

EngineDir holds the tools by name: litert\litert_lm_advanced_main_windows.exe and its DLLs (another build of it
in the dir -LitertDirName names), llama-cpu\llama-cli.exe, llama-gpu\llama-cli.exe (Vulkan),
llama-cuda\llama-cli.exe (CUDA, with the CUDA runtime DLLs beside it) (scripts/windows_ssh_executor.py stages them).
A run already on disk (<id>_run<k>.json) is kept and skipped, so a stopped job can be started again.
-PurgeEngineCaches removes the engines' caches beside the model files first (LiteRT-LM's program, weight and
XNNPACK caches carry no engine version in their names): the first run of each row is then the one that writes them,
which is what the record's firstEver says. Before each run the job waits (at most QuietWaitMinutes) until the host
is quiet: total CPU under QuietCpuPercent and NVIDIA memory in use under QuietGpuMiB; a run that starts past the
wait says so in its JSON (before.quietGate = timeout) with the load it saw.

A LiteRT-LM GPU launch with an adapter (job.json gpuPreference, from a cells row's adapter=) runs under Windows'
per-app graphics preference: the value named the tool's full path under HKCU\Software\Microsoft\DirectX\
UserGpuPreferences is set right before the run and removed right after it, in a finally; the job stops when it cannot
be removed (every later run of the same exe would take that GPU). Any litert launch first removes a value it finds on
the tool (a job stopped mid-run leaves one). Such a run's gate also waits until the sum of every GPU engine's use is
under QuietGpuEnginePercent (the NVIDIA memory reading does not see the integrated GPU). The engine's GPU caches beside
a model carry no adapter in their names: before a GPU run whose adapter differs from the one that wrote its model's
caches, the job removes them (gpuCachePurge), and a GPU run that starts with none of its model's caches says so
(gpuCacheWrite: it compiles and writes them). Which adapter wrote which caches is kept in <LogDir>\gpu-caches.json
for a resumed job; at its end the job removes the caches an adapter run wrote, so that no later job reads them.

Each run's JSON also carries two reads of the host taken around the engine process, sshConnections and hostCpu;
neither stops or flags a run. sshConnections: the SSH connections the host's sshd accepted from the run's start to its
end, read after the run from the event log -SshLogName names (OpenSSH logs one "Accepted" event per connection), with
each one's second into the run; sessions opened before the run are not counted, the executor's wait among them (one
session from before the job's first run to its end; a wait session opened again after a drop counts in the run it
falls in). A null count carries the reason the log could not be read. hostCpu: each logical
processor's busy share (every process's) and its performance against its nominal performance (which can read over
100), averaged over the run from the Processor Information counters read right before the engine starts and right
after it exits; its lowest performance limit over the reads after the first (one every 5 s while the engine runs, and
the one after it exits); and its limit flags over all of them. The job's first read of those counters is the slow one
(0.7 to 6.3 s on 2026-11-07; job.log says how long) and happens before its first run; each later read takes a
millisecond or two. host.json lists each logical processor's efficiency class, core, last-level cache index and
maxMhz (cpuSets).

Each run's JSON holds the NVIDIA GPU's state, one nvidia-smi read each (Get-GpuSample), right before the engine starts
(before.gpu) and after it exits (gpuAfter). With -GpuSampleSeconds N above 0, a GPU run's JSON also holds one read every
N s while its engine runs (gpuSamples, each labelled with its whole second into the run; gpuSampleWindows, the seconds
into the run, to the ms, at which each read started and ended); the default 0 takes none. gpuSampleSeconds is the N the
job ran with, engineStartSeconds when the engine's process started, in seconds from the run's start.

Written for the host side of scripts/windows_ssh_executor.py; the log and JSON shapes are what
scripts/run_windows_matrix.py write_records reads.
#>
param(
    [Parameter(Mandatory = $true)][string]$JobDir,
    [Parameter(Mandatory = $true)][string]$LogDir,
    [Parameter(Mandatory = $true)][string]$ModelDir,
    [Parameter(Mandatory = $true)][string]$EngineDir,
    [string]$BusyFile = "",
    [string]$BusyLabel = "windows-job",
    [string]$DeviceModel = "",
    [string]$LitertDirName = "litert",
    [int]$BusyMaxAgeMinutes = 120,
    [int]$BetweenRunsSeconds = 30,
    [int]$QuietCpuPercent = 25,
    [int]$QuietGpuMiB = 800,
    [int]$QuietGpuEnginePercent = 10,
    [int]$QuietWaitMinutes = 30,
    [string]$SshLogName = "OpenSSH/Operational",
    [int]$GpuSampleSeconds = 0,
    [switch]$PurgeEngineCaches
)

$ErrorActionPreference = "Stop"
$LitertExe = "litert_lm_advanced_main_windows.exe"
$GpuPrefKey = "Software\Microsoft\DirectX\UserGpuPreferences"
$GpuCacheAdapter = @{}   # model file -> the adapter ("" = the engine's own choice) that wrote its GPU caches
$CpuCategory = $null     # the Processor Information counter category, once read
$CpuReadError = ""       # why the last read of it failed

function Write-Utf8([string]$Path, [string]$Text) {
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Write-Json([string]$Path, $Value) {
    Write-Utf8 $Path ($Value | ConvertTo-Json -Depth 8)
}

function Say([string]$Text) {
    $line = "[{0}] {1}" -f (Get-Date -Format o), $Text
    [IO.File]::AppendAllText((Join-Path $LogDir "job.log"), "$line`r`n", (New-Object Text.UTF8Encoding($false)))
}

# Another lane's marker younger than BusyMaxAgeMinutes holds this job back; an older one is stale.
function Wait-Busy {
    if (-not $BusyFile) { return }
    while (Test-Path $BusyFile) {
        $item = Get-Item $BusyFile
        $text = Get-Content $BusyFile -Raw -ErrorAction SilentlyContinue
        $age = ((Get-Date) - $item.LastWriteTime).TotalMinutes
        if ($text -like "$BusyLabel *") { break }
        if ($age -ge $BusyMaxAgeMinutes) { Say "busy marker is $([int]$age) min old, taken over: $text"; break }
        Say "waiting for the busy marker ($([int]$age) min old): $text"
        Start-Sleep -Seconds 60
    }
    Write-Utf8 $BusyFile "$BusyLabel $(Get-Date -Format o)"
}

function Clear-Busy {
    if ($BusyFile -and (Test-Path $BusyFile)) {
        $text = Get-Content $BusyFile -Raw -ErrorAction SilentlyContinue
        if ($text -like "$BusyLabel *") { Remove-Item $BusyFile -ErrorAction SilentlyContinue }
    }
}

function Get-GpuSample {
    $smi = Join-Path $env:SystemRoot "System32\nvidia-smi.exe"
    if (-not (Test-Path $smi)) { return $null }
    try {
        $q = "name,driver_version,pstate,temperature.gpu,clocks.current.graphics,clocks.current.memory,power.draw,utilization.gpu,memory.used"
        return ((& $smi "--query-gpu=$q" "--format=csv,noheader" 2>$null) -join " | ")
    } catch { return $null }
}

function Get-CpuBusyPercent {
    try {
        return [math]::Round((Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'").PercentProcessorTime, 1)
    } catch { return $null }
}

# Foreign load right before a run: the top processes by CPU time used over one second. A process that started within
# that second counts from zero: a build's compiler runs one short process per file, and a process that started after
# the first read never showed in a list built from the processes alive at both reads. Callers wrap it in @(): from a
# function, PowerShell 5.1 hands back one item as the item itself and none as AutomationNull, which ConvertTo-Json
# writes as a bare string and as {}; wrapped, the record holds a list (possibly empty) every time.
function Get-TopProcesses {
    try {
        $a = @{}
        Get-Process | ForEach-Object { $a[$_.Id] = $_.CPU }
        Start-Sleep -Seconds 1
        return @(Get-Process | ForEach-Object {
                $was = $a[$_.Id]
                if ($null -eq $was -and -not $a.ContainsKey($_.Id)) { $was = 0 }
                if ($null -ne $was -and $null -ne $_.CPU) {
                    [pscustomobject]@{ n = $_.ProcessName; s = [math]::Round($_.CPU - $was, 2) }
                }
            } | Where-Object { $_.s -ge 0.05 } | Sort-Object s -Descending | Select-Object -First 5 |
            ForEach-Object { "$($_.n) $($_.s)" })
    } catch { return @() }
}

function Get-GpuMemoryMiB {
    $smi = Join-Path $env:SystemRoot "System32\nvidia-smi.exe"
    if (-not (Test-Path $smi)) { return 0 }
    try { return [int]((& $smi "--query-gpu=memory.used" "--format=csv,noheader,nounits" 2>$null) | Select-Object -First 1) } catch { return 0 }
}

# The sum of every GPU engine's use (all adapters, all processes) in percent; $null when the counters do not answer.
function Get-GpuEnginePercent {
    try {
        $e = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction Stop)
        if ($e.Count -eq 0) { return $null }
        return [math]::Round(($e | Measure-Object UtilizationPercentage -Sum).Sum, 1)
    } catch { return $null }
}

# Three reads a second apart, so that one quiet instant does not open the gate. -Engines (a run on a chosen adapter)
# also waits for the GPU engines.
function Wait-Quiet([switch]$Engines) {
    $deadline = (Get-Date).AddMinutes($QuietWaitMinutes)
    $last = ""
    while ($true) {
        $busy = @(1..3 | ForEach-Object { Start-Sleep -Seconds 1; Get-CpuBusyPercent })
        $cpu = ($busy | Measure-Object -Maximum).Maximum
        $gpu = Get-GpuMemoryMiB
        $eng = $null
        if ($Engines) { $eng = Get-GpuEnginePercent }
        $engOk = (-not $Engines) -or ($null -eq $eng) -or ($eng -lt $QuietGpuEnginePercent)
        if ($cpu -lt $QuietCpuPercent -and $gpu -lt $QuietGpuMiB -and $engOk) { return "quiet" }
        $text = "host not quiet: cpu $cpu %, gpu memory $gpu MiB"
        if ($Engines) { $text += ", gpu engines $eng %" }
        if ((Get-Date) -ge $deadline) { Say "$text, past the $QuietWaitMinutes min wait: running"; return "timeout" }
        if ($text -ne $last) { Say $text; $last = $text }
        Start-Sleep -Seconds 30
    }
}

# Windows' per-app graphics preference of one exe (the value named its full path), through the registry API: the
# provider cmdlets read -Name as a wildcard.
function Get-GpuPreference([string]$Exe) {
    $k = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($GpuPrefKey)
    if ($null -eq $k) { return $null }
    try { return $k.GetValue($Exe) } finally { $k.Close() }
}

function Set-GpuPreference([string]$Exe, [string]$Value) {
    $k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($GpuPrefKey)
    try { $k.SetValue($Exe, $Value, [Microsoft.Win32.RegistryValueKind]::String) } finally { $k.Close() }
}

# -> $true when no value is left on the exe
function Remove-GpuPreference([string]$Exe) {
    $k = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($GpuPrefKey, $true)
    if ($null -ne $k) { try { $k.DeleteValue($Exe, $false) } finally { $k.Close() } }
    return ($null -eq (Get-GpuPreference $Exe))
}

# The engine's GPU caches of one model file (ml_drift's program and weight caches beside it). Callers wrap it in @().
function Get-GpuCaches([string]$ModelFile) {
    $rx = '^' + [regex]::Escape($ModelFile) + '_.+_mldrift_(program|weight)_cache\.bin$'
    return @(Get-ChildItem $ModelDir -File | Where-Object { $_.Name -match $rx })
}

function Save-GpuCacheAdapter {
    Write-Json (Join-Path $LogDir "gpu-caches.json") $GpuCacheAdapter
}

# The SSH connections the host's sshd accepted between two times: how many, and each one's second after $From.
# OpenSSH logs every connection as three events of one id ("Accepted ...", "Received disconnect ...", "Disconnected
# ..."), so the message is what picks the connections. Get-WinEvent reports a window without events as the error
# NoMatchingEventsFound: a count of 0. The log is circular (1 MiB held about seven hours of the bench PC's SSH traffic
# on 2026-11-07): a window that starts before its oldest event is not counted. A null count carries the reason.
function Get-SshAccepted([datetime]$From, [datetime]$To) {
    try {
        $log = Get-WinEvent -ListLog $SshLogName -ErrorAction Stop
        if (-not $log.IsEnabled) { return [ordered]@{ accepted = $null; reason = "the $SshLogName log is not enabled" } }
        $oldest = Get-WinEvent -LogName $SshLogName -Oldest -MaxEvents 1 -ErrorAction SilentlyContinue
        if ($null -eq $oldest) { return [ordered]@{ accepted = $null; reason = "the $SshLogName log holds no event" } }
        if ($oldest.TimeCreated -gt $From) {
            return [ordered]@{ accepted = $null; reason = "the $SshLogName log's oldest event ($($oldest.TimeCreated.ToString('o'))) is later than the run's start" }
        }
        $events = @()
        try {
            $events = @(Get-WinEvent -FilterHashtable @{ LogName = $SshLogName; StartTime = $From; EndTime = $To } -ErrorAction Stop |
                    Where-Object { $_.Message -match '^sshd[^:]*: Accepted ' })
        } catch {
            if ($_.FullyQualifiedErrorId -notlike 'NoMatchingEventsFound*') { throw }
        }
        $at = @($events | Sort-Object TimeCreated | ForEach-Object { [math]::Round(($_.TimeCreated - $From).TotalSeconds, 1) })
        return [ordered]@{ accepted = $events.Count; atSeconds = $at }
    } catch {
        return [ordered]@{ accepted = $null; reason = "the $SshLogName log was not read: $($_.Exception.Message)" }
    }
}

# Every logical processor's Processor Information counters, raw, in one read inside this process (no WMI provider).
# $null when the counters do not answer ($CpuReadError says why).
function Read-CpuCounters {
    try {
        if ($null -eq $script:CpuCategory) {
            $script:CpuCategory = New-Object Diagnostics.PerformanceCounterCategory('Processor Information')
        }
        return , $script:CpuCategory.ReadCategory()
    } catch {
        $script:CpuReadError = $_.Exception.Message
        return $null
    }
}

# A run's performance limit is read every 5 s while the engine runs, the reads right before and after included: per
# logical processor the lowest % Performance Limit any read after the first held (an instantaneous counter: Calculate
# over two reads returns the newer one's value), and the Performance Limit Flags any read held, OR-ed. A read that
# fails is skipped; it never stops the run.
function New-CpuLimits { return [ordered]@{ reads = 0; last = $null; lowest = @{}; flags = @{} } }

function Add-CpuLimits($Acc, $Read) {
    if ($null -eq $Read) { return }
    try {
        if ($null -ne $Acc.last -and $Read.Contains('% Performance Limit')) {
            $prev = $Acc.last['% Performance Limit']
            foreach ($n in @($Read['% Performance Limit'].Keys)) {
                if ($n -match '^\d+,_total$' -or -not $prev.Contains($n)) { continue }
                $v = [Diagnostics.CounterSample]::Calculate($prev[$n].Sample, $Read['% Performance Limit'][$n].Sample)
                if (-not $Acc.lowest.ContainsKey($n) -or $v -lt $Acc.lowest[$n]) { $Acc.lowest[$n] = $v }
            }
        }
        if ($Read.Contains('Performance Limit Flags')) {
            foreach ($n in @($Read['Performance Limit Flags'].Keys)) {
                if ($n -match '^\d+,_total$') { continue }
                $f = [int64]$Read['Performance Limit Flags'][$n].RawValue
                if ($f -ne 0) { $Acc.flags[$n] = $(if ($Acc.flags.ContainsKey($n)) { $Acc.flags[$n] -bor $f } else { $f }) }
            }
        }
        $Acc.last = $Read
        $Acc.reads++
    } catch { }
}

# Each logical processor over one run, between two raw reads: busy (% Processor Time, every process's) and performance
# (% Processor Performance: the processor's average performance while executing instructions, against its nominal
# performance, which can read over 100). With $Limits (New-CpuLimits, at least two reads): the lowest performance limit
# and the limit flags of those reads; without: the limit and the flags of the second read. Keys are the counters'
# instances, "<group>,<processor>" and "_Total" (a group's own total is left out).
function Get-CpuDuringRun($Before, $After, $Limits = $null) {
    if ($null -eq $Before -or $null -eq $After) { return [ordered]@{ reason = "Processor Information not read: $CpuReadError" } }
    try {
        $names = @($After['% Processor Time'].Keys | Where-Object { $_ -notmatch '^\d+,_total$' } | Sort-Object {
                if ($_ -eq '_total') { [int]::MaxValue } else { $g, $p = $_ -split ','; [int]$g * 1000 + [int]$p } })
        $out = [ordered]@{ seconds = $null; busyPercent = [ordered]@{}; performancePercent = [ordered]@{};
            performanceLimitPercent = [ordered]@{}; performanceLimitFlags = [ordered]@{} }
        $useReads = ($null -ne $Limits) -and ($Limits.reads -ge 2)
        $maps = [ordered]@{ '% Processor Time' = 'busyPercent'; '% Processor Performance' = 'performancePercent' }
        if (-not $useReads) { $maps['% Performance Limit'] = 'performanceLimitPercent' }
        foreach ($n in $names) {
            $key = $(if ($n -eq '_total') { '_Total' } else { $n })
            foreach ($c in $maps.Keys) {
                if (-not $After.Contains($c)) { continue }
                $v = [Diagnostics.CounterSample]::Calculate($Before[$c][$n].Sample, $After[$c][$n].Sample)
                $out[$maps[$c]][$key] = [math]::Round($v, 1)
            }
            if ($useReads) {
                if ($Limits.lowest.ContainsKey($n)) { $out.performanceLimitPercent[$key] = [math]::Round($Limits.lowest[$n], 1) }
                if ($Limits.flags.ContainsKey($n)) { $out.performanceLimitFlags[$key] = $Limits.flags[$n] }
            } elseif ($After.Contains('Performance Limit Flags')) {
                $f = [int64]$After['Performance Limit Flags'][$n].RawValue
                if ($f -ne 0) { $out.performanceLimitFlags[$key] = $f }
            }
        }
        if ($useReads) { $out['limitReads'] = $Limits.reads }
        $s0 = $Before['% Processor Time']['_total'].Sample
        $s1 = $After['% Processor Time']['_total'].Sample
        $out.seconds = [math]::Round(($s1.TimeStamp100nSec - $s0.TimeStamp100nSec) / 1e7, 3)
        return $out
    } catch {
        return [ordered]@{ reason = "Processor Information: $($_.Exception.Message)" }
    }
}

# Each logical processor's efficiency class (Windows' class of its core: a higher one is faster and less
# power-efficient), core and last-level cache index (GetSystemCpuSetInformation; processors with the same index share
# that cache) and the MaxMhz that CallNtPowerInformation's ProcessorInformation reports for it, for reading hostCpu.
# Callers wrap it in @().
function Get-CpuSets {
    try {
        if (-not ('BenchCpuSets' -as [type])) {
            Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class BenchCpuSets {
  [DllImport("kernel32.dll", SetLastError=true)]
  public static extern bool GetSystemCpuSetInformation(IntPtr info, uint len, out uint ret, IntPtr proc, uint flags);
  [DllImport("powrprof.dll")]
  public static extern uint CallNtPowerInformation(int level, IntPtr input, uint inputLen, IntPtr output, uint outputLen);
}
"@
        }
        $mhz = @{}
        $count = [Environment]::ProcessorCount
        $pbuf = [Runtime.InteropServices.Marshal]::AllocHGlobal(24 * $count)
        try {
            # ProcessorInformation (11): one PROCESSOR_POWER_INFORMATION of six ULONGs per logical processor
            if ([BenchCpuSets]::CallNtPowerInformation(11, [IntPtr]::Zero, 0, $pbuf, [uint32](24 * $count)) -eq 0) {
                for ($i = 0; $i -lt $count; $i++) {
                    $mhz[[Runtime.InteropServices.Marshal]::ReadInt32($pbuf, 24 * $i)] = [Runtime.InteropServices.Marshal]::ReadInt32($pbuf, 24 * $i + 4)
                }
            }
        } finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($pbuf) }
        [uint32]$len = 0
        [void][BenchCpuSets]::GetSystemCpuSetInformation([IntPtr]::Zero, 0, [ref]$len, [IntPtr]::Zero, 0)
        $buf = [Runtime.InteropServices.Marshal]::AllocHGlobal([int]$len)
        $sets = @()
        try {
            if (-not [BenchCpuSets]::GetSystemCpuSetInformation($buf, $len, [ref]$len, [IntPtr]::Zero, 0)) { throw "GetSystemCpuSetInformation failed" }
            $off = 0
            while ($off -lt $len) {
                $size = [Runtime.InteropServices.Marshal]::ReadInt32($buf, $off)
                $lp = [int][Runtime.InteropServices.Marshal]::ReadByte($buf, $off + 14)
                $sets += [ordered]@{
                    group           = [int][Runtime.InteropServices.Marshal]::ReadInt16($buf, $off + 12)
                    lp              = $lp
                    core            = [int][Runtime.InteropServices.Marshal]::ReadByte($buf, $off + 15)
                    llc             = [int][Runtime.InteropServices.Marshal]::ReadByte($buf, $off + 16)
                    efficiencyClass = [int][Runtime.InteropServices.Marshal]::ReadByte($buf, $off + 18)
                    maxMhz          = $(if ($mhz.ContainsKey($lp)) { $mhz[$lp] } else { $null })
                }
                $off += $size
            }
        } finally { [Runtime.InteropServices.Marshal]::FreeHGlobal($buf) }
        return $sets
    } catch { return @("not read: $($_.Exception.Message)") }
}

function Get-HostFacts {
    $cs = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
    # The update build revision: Win32_OperatingSystem.Version stops at the build (10.0.26200), and the 2026-11-06
    # update on the bench PC moved only this number (26200.6899 to 26200.9711), so the record names it.
    $ubr = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion" -ErrorAction SilentlyContinue).UBR
    $battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
    $state = "unknown"
    if ($battery) {
        $state = switch ([int]$battery.BatteryStatus) { 1 { "discharging" } 2 { "ac" } 3 { "full" } 6 { "charging" } default { "other-$($battery.BatteryStatus)" } }
    }
    $npu = Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue |
        Where-Object { $_.DeviceName -match "AI Boost|\bNPU\b" } | Select-Object -First 1
    $gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
            [ordered]@{ name = $_.Name; driverVersion = $_.DriverVersion; adapterRamBytes = $_.AdapterRAM }
        })
    $scheme = ((& powercfg /getactivescheme) -join " ")
    $binaries = [ordered]@{}
    foreach ($tool in "litert", "llama-cpu", "llama-gpu", "llama-cuda", "openvino") {
        $dir = Join-Path $EngineDir $(if ($tool -eq "litert") { $LitertDirName } else { $tool })
        if (-not (Test-Path $dir)) { continue }
        Get-ChildItem $dir -File | Where-Object { $_.Extension -in ".exe", ".dll" } | ForEach-Object {
            $sha = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
            $key = if ($_.Name -eq $LitertExe) { $LitertExe } else { "$tool/$($_.Name)" }
            $binaries[$key] = $sha
        }
    }
    return [ordered]@{
        model           = $(if ($DeviceModel) { $DeviceModel } else { $cs.Model })
        manufacturer    = $cs.Manufacturer
        systemModel     = $cs.Model
        os              = $(if ($ubr) { "$($os.Caption) $($os.Version).$ubr" } else { "$($os.Caption) $($os.Version)" })
        cpu             = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
        gpus            = $gpus
        memoryBytes     = [int64]$cs.TotalPhysicalMemory
        batteryState    = $state
        batteryLevel    = $(if ($battery) { [int]$battery.EstimatedChargeRemaining } else { $null })
        powerScheme     = $scheme
        npuDriver       = $(if ($npu) { "$($npu.DeviceName) $($npu.DriverVersion)" } else { $null })
        binaries        = $binaries
        cpuSets         = @(Get-CpuSets)
    }
}

function Resolve-Arg([string]$Arg, [string]$ToolDir) {
    $a = $Arg.Replace("{job}", $JobDir).Replace("{tool_dir}", $ToolDir)
    $m = [regex]::Match($a, "\{model:([^}]+)\}")
    if ($m.Success) {
        $a = $a.Replace($m.Value, (Join-Path $ModelDir $m.Groups[1].Value))
    }
    return $a
}

# job.json args are cmd.exe-safe words already (run_windows_matrix.lab_args); only a path this host
# substituted can bring a blank, and only a word without quotes of its own is wrapped.
function Quote-Arg([string]$Arg) {
    if ($Arg -notmatch '\s' -or $Arg.Contains('"')) { return $Arg }
    return '"' + $Arg + '"'
}

function Get-Tool($Launch) {
    if ($Launch.tool -eq "litert") { return Join-Path (Join-Path $EngineDir $LitertDirName) $LitertExe }
    return Join-Path (Join-Path $EngineDir $Launch.tool) "llama-cli.exe"
}

function Find-Engine([int]$ParentId, [string]$ExeName) {
    for ($i = 0; $i -lt 40; $i++) {
        $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ieq $ExeName } | Select-Object -First 1
        if ($child) {
            try { return Get-Process -Id $child.ProcessId -ErrorAction Stop } catch { return $null }
        }
        Start-Sleep -Milliseconds 250
    }
    return $null
}

function Invoke-Run($Launch, [int]$RunIndex, [int]$TimeoutSeconds) {
    $name = "$($Launch.id)_run$RunIndex"
    $metaPath = Join-Path $LogDir "$name.json"
    if (Test-Path $metaPath) { Say "$name kept from an earlier start"; return }
    $logPath = Join-Path $LogDir "$name.log"
    $tool = Get-Tool $Launch
    $words = @($Launch.args | ForEach-Object { Quote-Arg (Resolve-Arg $_ (Split-Path $tool)) })
    $argLine = $words -join " "
    $inner = "`"$tool`" $argLine < NUL > `"$logPath`" 2>&1"

    $saved = @{}
    $envText = ""
    if ($Launch.env) {
        foreach ($p in $Launch.env.PSObject.Properties) {
            $saved[$p.Name] = [Environment]::GetEnvironmentVariable($p.Name, "Process")
            $value = $p.Value -replace "%PATH%", $env:Path
            [Environment]::SetEnvironmentVariable($p.Name, $value, "Process")
            if ($p.Name -ne "Path") { $envText += "$($p.Name)=$($p.Value) " }
        }
    }

    # A LiteRT-LM GPU run on a chosen adapter (gpuPreference) and its model's GPU caches (see the head of this file).
    $isGpu = ($Launch.tool -eq "litert") -and (($Launch.args -join " ") -match "--backend=gpu")
    $want = [string]$Launch.gpuPreference
    $adapter = [string]$Launch.adapter
    $leftover = $null
    if ($Launch.tool -eq "litert") {
        $leftover = Get-GpuPreference $tool
        if ($null -ne $leftover) {
            if (-not (Remove-GpuPreference $tool)) { throw "the GpuPreference value on $tool ($leftover) could not be removed" }
            Say "$name removed a GpuPreference value left on the tool: $leftover"
        }
    }
    $purged = @()
    $cacheWrite = $null
    if ($isGpu -and $Launch.modelFile) {
        $mf = [string]$Launch.modelFile
        $have = @(Get-GpuCaches $mf)
        $was = $null
        if ($GpuCacheAdapter.ContainsKey($mf)) { $was = [string]$GpuCacheAdapter[$mf] }
        # caches another adapter wrote, or of unknown origin when the run asks for an adapter, go first
        if ($have.Count -gt 0 -and ((($null -ne $was) -and ($was -ne $adapter)) -or (($null -eq $was) -and ($adapter -ne "")))) {
            $whose = $(if ($null -eq $was) { "an unknown" } elseif ($was) { "the $was" } else { "the default" })
            foreach ($c in $have) {
                Remove-Item -LiteralPath $c.FullName
                $purged += $c.Name
                Say "$name purged $($c.Name) ($([int]($c.Length / 1MB)) MB): written under $whose adapter, the run asks for $(if ($adapter) { $adapter } else { 'the default' })"
            }
            $have = @()
        }
        $cacheWrite = ($have.Count -eq 0)
    }

    $gate = $(if ($want) { Wait-Quiet -Engines } else { Wait-Quiet })
    $top = @(Get-TopProcesses)
    $before = [ordered]@{ quietGate = $gate; cpuBusyPercent = Get-CpuBusyPercent; topProcesses = $top; gpu = Get-GpuSample }
    if ($want) { $before["gpuEnginePercent"] = Get-GpuEnginePercent }
    $applied = $null
    $prefGone = $null
    $cpu0 = $null
    $cpu1 = $null
    $t0 = $null
    $t1 = $null
    $limits = New-CpuLimits
    try {
        if ($want) {
            Set-GpuPreference $tool $want
            $applied = Get-GpuPreference $tool
            Say "$name GpuPreference on the tool: $applied"
        }
        $cpu0 = Read-CpuCounters
        Add-CpuLimits $limits $cpu0
        $t0 = Get-Date
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $start = $t0.ToString("o")
        Say "$name start: $envText$tool $argLine"
        $shell = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList "/d /s /c `"$inner`"" `
            -WorkingDirectory (Split-Path $tool) -WindowStyle Hidden -PassThru
        $null = $shell.Handle   # keeps ExitCode readable after the exit

        $engine = Find-Engine $shell.Id (Split-Path $tool -Leaf)
        $peak = [int64]0
        $timedOut = $false
        $gpuSamples = @()
        $gpuWindows = @()
        $engineStart = $null
        if ($engine) { try { $engineStart = [math]::Round(($engine.StartTime - $t0).TotalSeconds, 3) } catch { } }
        $sampleGpu = ($GpuSampleSeconds -gt 0) -and (((($Launch.args -join " ") -match "--backend=gpu") -or ($Launch.tool -in "llama-gpu", "llama-cuda")))
        $nextGpu = [double]$GpuSampleSeconds
        $nextCpu = 5.0
        while (-not $shell.HasExited) {
            if ($engine) {
                try {
                    $engine.Refresh()
                    if (-not $engine.HasExited -and $engine.PeakWorkingSet64 -gt $peak) { $peak = $engine.PeakWorkingSet64 }
                } catch { }
            }
            if ($sw.Elapsed.TotalSeconds -ge $nextCpu) {
                Add-CpuLimits $limits (Read-CpuCounters)
                $nextCpu += 5.0
            }
            if ($sampleGpu -and $sw.Elapsed.TotalSeconds -ge $nextGpu) {
                $readAt = $sw.Elapsed.TotalSeconds
                $read = Get-GpuSample
                $gpuSamples += "$([int]$readAt)s $read"
                $gpuWindows += , ([ordered]@{ startSeconds = [math]::Round($readAt, 3); endSeconds = [math]::Round($sw.Elapsed.TotalSeconds, 3) })
                $nextGpu += $GpuSampleSeconds
            }
            if ($sw.Elapsed.TotalSeconds -ge $TimeoutSeconds) {
                $timedOut = $true
                Say "$name timed out after $TimeoutSeconds s"
                & "$env:SystemRoot\System32\taskkill.exe" /PID $shell.Id /T /F 2>&1 | Out-Null
                break
            }
            Start-Sleep -Milliseconds 500
        }
        $shell.WaitForExit()
        $elapsed = $sw.Elapsed.TotalSeconds
        $exit = $shell.ExitCode
        $cpu1 = Read-CpuCounters
        Add-CpuLimits $limits $cpu1
        $t1 = Get-Date
    } finally {
        # the value outlives the process: off right after the run, whatever stopped it
        if ($want) {
            $prefGone = Remove-GpuPreference $tool
            Say "$name GpuPreference removed after the run: $(if ($prefGone) { 'none left' } else { 'STILL SET' })"
        }
    }

    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process") }
    $after = [ordered]@{ cpuBusyPercent = Get-CpuBusyPercent; topProcesses = @(Get-TopProcesses) }
    $ssh = Get-SshAccepted $t0 $t1
    if ($isGpu -and $Launch.modelFile) {
        $GpuCacheAdapter[[string]$Launch.modelFile] = $adapter
        Save-GpuCacheAdapter
    }

    Write-Json $metaPath ([ordered]@{
            exitCode              = $(if ($timedOut) { $null } else { [int]$exit })
            timedOut              = $timedOut
            start                 = $start
            elapsedSeconds        = [math]::Round($elapsed, 3)
            peakWorkingSetBytes   = $peak
            command               = "$envText$(Split-Path $tool -Leaf) $argLine"
            before                = $before
            after                 = $after
            gpuAfter              = Get-GpuSample
            gpuSamples            = $gpuSamples
            gpuSampleSeconds      = $GpuSampleSeconds
            gpuSampleWindows      = @($gpuWindows)
            engineStartSeconds    = $engineStart
            gpuPreference         = $applied
            gpuPreferenceRemoved  = $prefGone
            gpuPreferenceLeftover = $leftover
            gpuCacheWrite         = $cacheWrite
            gpuCachePurge         = $purged
            sshConnections        = $ssh
            hostCpu               = Get-CpuDuringRun $cpu0 $cpu1 $limits
        })
    Say "$name exit=$exit timedOut=$timedOut elapsed=$([math]::Round($elapsed, 1)) peakMB=$([int]($peak / 1MB))"
    if ($want -and -not $prefGone) {
        throw "the GpuPreference value on $tool is still set after ${name}: every later run of the tool would take that GPU"
    }
}

New-Item -ItemType Directory -Force $LogDir | Out-Null
$donePath = Join-Path $LogDir "job.done"
Remove-Item $donePath -ErrorAction SilentlyContinue
$failure = $null
try {
    $job = Get-Content (Join-Path $JobDir "job.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    Wait-Busy
    Say "job $($job.campaign): $(@($job.launches).Count) launches"
    Say $(if ($GpuSampleSeconds -gt 0) { "GPU reads while a GPU run's engine runs: one every $GpuSampleSeconds s" } else { "GPU reads while a GPU run's engine runs: none (-GpuSampleSeconds 0)" })
    Write-Json (Join-Path $LogDir "host.json") (Get-HostFacts)
    $cpuLoad = [Diagnostics.Stopwatch]::StartNew()
    if ($null -eq (Read-CpuCounters)) { Say "Processor Information counters not read: $CpuReadError (each run's hostCpu carries the reason)" }
    else { Say "Processor Information counters loaded in $([int]$cpuLoad.Elapsed.TotalMilliseconds) ms (the job's first read)" }
    if ($PurgeEngineCaches) {
        Get-ChildItem $ModelDir -File | Where-Object { $_.Name -match "_cache\.bin$|\.xnnpack_cache$" } | ForEach-Object {
            Say "purged $($_.Name) ($([int]($_.Length / 1MB)) MB)"
            Remove-Item $_.FullName
        }
    }
    $state = Join-Path $LogDir "gpu-caches.json"
    if (Test-Path $state) {
        # a resumed job: which adapter wrote which model's GPU caches before it stopped
        $o = Get-Content $state -Raw -Encoding UTF8 | ConvertFrom-Json
        foreach ($p in $o.PSObject.Properties) { $GpuCacheAdapter[$p.Name] = [string]$p.Value }
        Say "GPU caches by adapter from the earlier start: $((Get-Content $state -Raw) -replace '\s+', ' ')"
    }
    foreach ($model in @($job.models)) {
        $p = Join-Path $ModelDir $model.name
        if (-not (Test-Path $p)) { throw "model file $p is not on this host" }
        if ((Get-Item $p).Length -ne [int64]$model.bytes) { throw "model file $p is not $($model.bytes) bytes" }
    }
    foreach ($launch in @($job.launches)) {
        for ($r = 1; $r -le [int]$launch.runs; $r++) {
            Wait-Busy
            Invoke-Run $launch $r ([int]$job.runTimeoutSeconds)
            Start-Sleep -Seconds $BetweenRunsSeconds
        }
    }
} catch {
    $failure = "$_"
    Say "job failed: $failure"
} finally {
    try {
        # the caches a run on a chosen adapter wrote, so that no later job reads them on another GPU, and no value
        # left on the tool, whatever stopped the job
        foreach ($mf in @($GpuCacheAdapter.Keys)) {
            if ($GpuCacheAdapter[$mf]) {
                foreach ($c in @(Get-GpuCaches $mf)) {
                    Remove-Item -LiteralPath $c.FullName
                    Say "purged $($c.Name) at the end: written under the $($GpuCacheAdapter[$mf]) adapter"
                }
                $GpuCacheAdapter.Remove($mf)
                Save-GpuCacheAdapter
            }
        }
        $litert = Join-Path (Join-Path $EngineDir $LitertDirName) $LitertExe
        if ($null -ne (Get-GpuPreference $litert)) {
            $gone = Remove-GpuPreference $litert
            Say "a GpuPreference value was on the tool at the end: $(if ($gone) { 'removed' } else { 'STILL SET' })"
            if (-not $gone -and -not $failure) { $failure = "the GpuPreference value on $litert could not be removed" }
        }
    } catch {
        Say "end of the job: $_"
        if (-not $failure) { $failure = "end of the job: $_" }
    }
    Clear-Busy
    Write-Utf8 $donePath $(if ($failure) { "FAILED $failure" } else { "OK" })
}
