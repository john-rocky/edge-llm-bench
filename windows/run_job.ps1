<#
Runs one job on this Windows host: the job.json scripts/run_windows_matrix.py plans
(launches = tool + args + runs), every run one fresh engine process with stdout and stderr in one
file, the host facts and the sha256 of every engine file in host.json. Windows PowerShell 5.1.

  powershell -NoProfile -ExecutionPolicy Bypass -File run_job.ps1 -JobDir <dir> -LogDir <dir>
      -ModelDir <dir> -EngineDir <dir> [-BusyFile <file> -BusyLabel <text>] [-DeviceModel <text>]
      [-LitertDirName <dir under EngineDir>] [-PurgeEngineCaches] [-QuietCpuPercent N] [-QuietGpuMiB N]
      [-QuietGpuEnginePercent N] [-QuietWaitMinutes N]

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
    [switch]$PurgeEngineCaches
)

$ErrorActionPreference = "Stop"
$LitertExe = "litert_lm_advanced_main_windows.exe"
$GpuPrefKey = "Software\Microsoft\DirectX\UserGpuPreferences"
$GpuCacheAdapter = @{}   # model file -> the adapter ("" = the engine's own choice) that wrote its GPU caches

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
    try {
        if ($want) {
            Set-GpuPreference $tool $want
            $applied = Get-GpuPreference $tool
            Say "$name GpuPreference on the tool: $applied"
        }
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $start = Get-Date -Format o
        Say "$name start: $envText$tool $argLine"
        $shell = Start-Process -FilePath "$env:SystemRoot\System32\cmd.exe" -ArgumentList "/d /s /c `"$inner`"" `
            -WorkingDirectory (Split-Path $tool) -WindowStyle Hidden -PassThru
        $null = $shell.Handle   # keeps ExitCode readable after the exit

        $engine = Find-Engine $shell.Id (Split-Path $tool -Leaf)
        $peak = [int64]0
        $timedOut = $false
        $gpuSamples = @()
        $sampleGpu = (($Launch.args -join " ") -match "--backend=gpu") -or ($Launch.tool -in "llama-gpu", "llama-cuda")
        $nextGpu = 5.0
        while (-not $shell.HasExited) {
            if ($engine) {
                try {
                    $engine.Refresh()
                    if (-not $engine.HasExited -and $engine.PeakWorkingSet64 -gt $peak) { $peak = $engine.PeakWorkingSet64 }
                } catch { }
            }
            if ($sampleGpu -and $sw.Elapsed.TotalSeconds -ge $nextGpu) {
                $gpuSamples += "$([int]$sw.Elapsed.TotalSeconds)s $(Get-GpuSample)"
                $nextGpu += 5.0
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
    } finally {
        # the value outlives the process: off right after the run, whatever stopped it
        if ($want) {
            $prefGone = Remove-GpuPreference $tool
            Say "$name GpuPreference removed after the run: $(if ($prefGone) { 'none left' } else { 'STILL SET' })"
        }
    }

    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], "Process") }
    $after = [ordered]@{ cpuBusyPercent = Get-CpuBusyPercent; topProcesses = @(Get-TopProcesses) }
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
            gpuPreference         = $applied
            gpuPreferenceRemoved  = $prefGone
            gpuPreferenceLeftover = $leftover
            gpuCacheWrite         = $cacheWrite
            gpuCachePurge         = $purged
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
    Write-Json (Join-Path $LogDir "host.json") (Get-HostFacts)
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
