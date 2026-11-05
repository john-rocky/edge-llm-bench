<#
Builds LiteRT-LM's CLI tools on Windows from a tag and stages them for scripts/windows_ssh_executor.py:
<EngineDir>\litert_lm_advanced_main_windows.exe, the prebuilt DLLs of the tag, the Intel dispatch and the
DirectX shader compiler, plus pins.json, the registry entry of the build (windows/engine-pins.json, or
BENCH_EXTRA_PINS for a label not listed there). Windows PowerShell 5.1.

  powershell -NoProfile -ExecutionPolicy Bypass -File build_litert_lm.ps1 -Tag v0.19.0 -Label v0.19.0
      -Src C:\src\LiteRT-LM -OutputBase C:\bzl -EngineDir C:\Users\me\bench\engines\litert
      [-DxcDir <dir>] [-Log <file>] [-StageOnly]

Needs (LiteRT-LM docs/getting-started/build-and-run.md "Deploy to Windows"): Visual Studio 2022 or its Build
Tools with the C++ workload, Git for Windows with LFS, Python 3.13 for all users, Bazelisk, a JDK with JAVA_HOME,
LongPathsEnabled, and an elevated shell or Developer Mode for symlinks. Two things the build needs beyond those:

- /utf-8 on every action: on a Windows whose system code page is not 1252 (Japanese: 932) MSVC reads the
  BOM-less UTF-8 sources in that code page; litert's stablehlo_reduce_window.cc fails on it, and a string literal
  elsewhere can change without an error.
- BAZEL_VC when only the Build Tools are installed.

-DxcDir: a dir with dxcompiler.dll and dxil.dll (the PyPI wheel litert-lm-api carries them); Dawn's D3D12 backend
loads them from beside the tool.
#>
param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [Parameter(Mandatory = $true)][string]$Label,
    [Parameter(Mandatory = $true)][string]$Src,
    [Parameter(Mandatory = $true)][string]$OutputBase,
    [Parameter(Mandatory = $true)][string]$EngineDir,
    [string]$DxcDir = "",
    [string]$Log = "",
    [switch]$StageOnly
)

$ExeName = "litert_lm_advanced_main_windows.exe"
$DispatchTarget = "@litert//litert/vendors/intel_openvino/dispatch:LiteRtDispatch"
$Targets = "//runtime/engine:litert_lm_advanced_main //runtime/engine:litert_lm_main $DispatchTarget"

function Say([string]$Text) {
    $line = "[{0}] {1}" -f (Get-Date -Format o), $Text
    Write-Output $line
    if ($Log) { [IO.File]::AppendAllText($Log, "$line`r`n", (New-Object Text.UTF8Encoding($false))) }
}

function Stop-Build([string]$Text) {
    Say "ERROR: $Text"
    exit 1
}

# Native tools run through cmd.exe so that stderr reaches the log as bytes (PowerShell 5.1 wraps it in records).
function Invoke-Tool([string]$CommandLine) {
    if ($Log) {
        & "$env:SystemRoot\System32\cmd.exe" /d /c "$CommandLine >> `"$Log`" 2>&1"
    } else {
        & "$env:SystemRoot\System32\cmd.exe" /d /c "$CommandLine 2>&1" | Out-Host   # or its lines join the return value
    }
    return $LASTEXITCODE
}

function Find-Tools {
    if (-not $env:BAZEL_VC) {
        $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
        if (Test-Path $vswhere) {
            $vs = & $vswhere -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -latest -property installationPath
            if ($vs) { $env:BAZEL_VC = Join-Path $vs "VC" }
        }
    }
    if (-not $env:BAZEL_VC -or -not (Test-Path $env:BAZEL_VC)) { Stop-Build "no MSVC found: install the C++ workload or set BAZEL_VC" }
    if (-not $env:BAZEL_SH) { $env:BAZEL_SH = "C:\Program Files\Git\bin\bash.exe" }
    if (-not (Test-Path $env:BAZEL_SH)) { Stop-Build "no Git Bash at $env:BAZEL_SH" }
    $py = "C:\Program Files\Python313"
    if (-not (Test-Path "$py\python.exe")) { Stop-Build "no Python 3.13 for all users at $py" }
    $env:PYTHON_BIN_PATH = "$py\python.exe"
    $env:Path = "$py;$py\Scripts;C:\Program Files\Git\bin;C:\Program Files\Git\cmd;C:\Program Files\Git\usr\bin;" + $env:Path
    if (-not $env:JAVA_HOME) { $env:JAVA_HOME = [Environment]::GetEnvironmentVariable("JAVA_HOME", "Machine") }
    if (-not $env:JAVA_HOME -or -not (Test-Path "$env:JAVA_HOME\bin\java.exe")) { Stop-Build "JAVA_HOME has no bin\java.exe" }
    $env:Path = "$env:JAVA_HOME\bin;" + $env:Path
    $links = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
    if (Test-Path $links) { $env:Path = "$links;" + $env:Path }
    if (-not (Get-Command bazelisk -ErrorAction SilentlyContinue)) { Stop-Build "bazelisk is not on PATH" }
}

function Get-Source {
    $env:GIT_LFS_SKIP_SMUDGE = "1"
    if (-not (Test-Path "$Src\.git")) {
        Say "clone"
        $rc = Invoke-Tool "git -c core.longpaths=true -c core.symlinks=true clone https://github.com/google-ai-edge/LiteRT-LM.git `"$Src`""
        if ($rc -ne 0) { Stop-Build "git clone: exit $rc" }
    }
    Set-Location $Src
    $null = Invoke-Tool "git config core.longpaths true"
    $null = Invoke-Tool "git config core.symlinks true"
    $rc = Invoke-Tool "git fetch --tags origin"
    if ($rc -ne 0) { Stop-Build "git fetch: exit $rc" }
    # bazel's crate rule rewrites this lock file with LF line ends on every build; nothing else may differ
    $dirty = & git status --porcelain --untracked-files=no | Where-Object { $_ -notmatch "cxxbridge_cmd/Cargo\.lock" }
    if ($dirty) { Stop-Build "$Src has local changes: $dirty" }
    $rc = Invoke-Tool "git checkout -B windows-$Tag $Tag"
    if ($rc -ne 0) { Stop-Build "git checkout ${Tag}: exit $rc" }
    $rc = Invoke-Tool "git lfs pull --include `"prebuilt/windows_x86_64/*`""
    if ($rc -ne 0) { Stop-Build "git lfs pull: exit $rc" }
}

function Build-Tools {
    Say "bazel build $Targets"
    $flags = "--config=windows --copt=/utf-8 --host_copt=/utf-8 --curses=no --color=no --show_progress_rate_limit=30"
    $rc = Invoke-Tool "bazelisk --output_base=`"$OutputBase`" build $Targets $flags"
    if ($rc -ne 0) { Stop-Build "bazel build: exit $rc" }
}

function Stage-Tools {
    # Bazel's outputs are read-only and a copy keeps that: without -Force and Stop, staging over an earlier stage keeps
    # the old tool and names it in pins.json with no error.
    $ErrorActionPreference = "Stop"
    if (-not (Test-Path $Src)) { Stop-Build "$Src is not there" }
    Set-Location $Src
    $bin = Join-Path $Src "bazel-bin"
    $exe = "$bin\runtime\engine\litert_lm_advanced_main.exe"
    if (-not (Test-Path $exe)) { Stop-Build "$exe is not there" }
    New-Item -ItemType Directory -Force $EngineDir | Out-Null
    Get-ChildItem $EngineDir -File | Remove-Item -Force
    Copy-Item $exe (Join-Path $EngineDir $ExeName) -Force
    $built = (Get-FileHash -Algorithm SHA256 $exe).Hash
    $staged = (Get-FileHash -Algorithm SHA256 (Join-Path $EngineDir $ExeName)).Hash
    if ($built -ne $staged) { Stop-Build "staged tool $staged is not the built one $built" }
    Copy-Item "$bin\runtime\engine\litert_lm_main.exe" $EngineDir
    foreach ($dll in "libGemmaModelConstraintProvider.dll", "libLiteRt.dll", "libLiteRtWebGpuAccelerator.dll", "libwebgpu_dawn.dll", "webgpu_dawn.dll") {
        Copy-Item "$Src\prebuilt\windows_x86_64\$dll" $EngineDir
    }
    $dispatch = Get-ChildItem "$bin\external\litert" -Recurse -Filter LiteRtDispatch.dll -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $dispatch) { Stop-Build "no LiteRtDispatch.dll under $bin\external\litert" }
    Copy-Item $dispatch.FullName $EngineDir
    if ($DxcDir) {
        foreach ($dll in "dxcompiler.dll", "dxil.dll") {
            if (-not (Test-Path "$DxcDir\$dll")) { Stop-Build "$DxcDir has no $dll" }
            Copy-Item "$DxcDir\$dll" $EngineDir
        }
    }
    $files = [ordered]@{}
    Get-ChildItem $EngineDir -File | Where-Object { $_.Extension -eq ".dll" } | ForEach-Object {
        $files[$_.Name] = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLower()
    }
    $pin = [ordered]@{
        tag                                   = $Tag
        commit                                = (& git rev-parse HEAD)
        engine_version                        = $Tag
        gpu_accelerator                       = "static-source"
        built_with                            = "bazel --config=windows --copt=/utf-8 --host_copt=/utf-8"
        litert_lm_advanced_main_windows_sha256 = (Get-FileHash -Algorithm SHA256 (Join-Path $EngineDir $ExeName)).Hash.ToLower()
        dll_files                             = $files
    }
    $doc = [ordered]@{ "windows_litert-lm" = [ordered]@{ $Label = $pin } }
    [IO.File]::WriteAllText((Join-Path $EngineDir "pins.json"), ($doc | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
    Say "staged $EngineDir, exe sha256 $($pin.litert_lm_advanced_main_windows_sha256)"
}

$PSDefaultParameterValues["Out-File:Encoding"] = "utf8"
if ($Log) { New-Item -ItemType Directory -Force (Split-Path $Log) | Out-Null }
Find-Tools
if (-not $StageOnly) {
    Get-Source
    Build-Tools
}
Stage-Tools
