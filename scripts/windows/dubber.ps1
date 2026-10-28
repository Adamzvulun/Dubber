# Dubber for Windows: one script does everything, every time it runs (double-click "Start Dubber.cmd" or the
# desktop shortcut). Installs what is missing (Python, ffmpeg, the program's components), creates the desktop
# shortcut "Дубляж видео" with the program's icon, then starts the program.
# This file is UTF-8 with BOM: Windows PowerShell 5.1 then reads the Russian text correctly. Keep Russian text out of
# .bat/.cmd files: cmd shows it as question marks on many PCs (that was the old installer's problem).
param(
    [switch]$NoStart,  # install + shortcut only, never wait for Enter (used by the Windows test in CI)
    [switch]$ShortcutOnly  # only the shortcuts, silently: asked by the program when it started without this script
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
try { $Host.UI.RawUI.WindowTitle = 'Дубляж видео' } catch {}

# Small helpers from Windows itself, compiled once at start: the window's font, and shortcuts written through the
# Unicode interface. The usual WScript.Shell saves names and paths in the
# PC's old ANSI code page: a Russian shortcut name became "?????? ?????" on non-Russian Windows (Adam's PC, CI).
$NativeCode = @"
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;
namespace DubberSetup {
    [ComImport, Guid("00021401-0000-0000-C000-000000000046")] class CShellLink {}
    [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
    interface IShellLinkW {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int max, IntPtr data, int flags);
        void GetIDList(out IntPtr idl);
        void SetIDList(IntPtr idl);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int max);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder dir, int max);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string dir);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder args, int max);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string args);
        void GetHotkey(out short key);
        void SetHotkey(short key);
        void GetShowCmd(out int cmd);
        void SetShowCmd(int cmd);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int max, out int index);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, int reserved);
        void Resolve(IntPtr hwnd, int flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string file);
    }
    // The window's font. Old console windows often use "Raster Fonts", which only has the letters of the PC's own
    // language: on Hebrew or English Windows every Russian letter showed as "?" (Adam's screenshot, 0.6.0).
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct FontInfo {
        public uint Size; public uint Index; public short Width; public short Height; public int Family; public int Weight;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string Face;
    }
    public static class ConsoleFont {
        [DllImport("kernel32.dll")] static extern IntPtr GetStdHandle(int handle);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool GetCurrentConsoleFontEx(IntPtr output, bool max, ref FontInfo font);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern bool SetCurrentConsoleFontEx(IntPtr output, bool max, ref FontInfo font);
        // Switches a raster font to Consolas (has Cyrillic); a TrueType font the user chose stays. True if changed.
        public static bool UseCyrillicFont() {
            IntPtr output = GetStdHandle(-11);
            FontInfo font = new FontInfo();
            font.Size = (uint)Marshal.SizeOf(font);
            if (!GetCurrentConsoleFontEx(output, false, ref font) || (font.Family & 4) != 0) return false;  // 4 = TrueType
            font.Face = "Consolas";
            font.Family = 54;  // TrueType, fixed width, modern
            font.Weight = 400;
            font.Width = 0;
            if (font.Height < 16) font.Height = 16;
            return SetCurrentConsoleFontEx(output, false, ref font);
        }
    }
    public static class Shortcut {
        public static void Save(string lnk, string target, string args, string dir, string icon, string description) {
            IShellLinkW link = (IShellLinkW)new CShellLink();
            link.SetPath(target);
            link.SetArguments(args);
            link.SetWorkingDirectory(dir);
            link.SetIconLocation(icon, 0);
            link.SetDescription(description);
            ((IPersistFile)link).Save(lnk, true);
        }
    }
}
"@
$Native = $false
try {
    Add-Type -TypeDefinition $NativeCode
    $Native = $true
    [void][DubberSetup.ConsoleFont]::UseCyrillicFont()  # before the first Russian line
} catch {}

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)  # scripts\windows -> the program folder
Set-Location -LiteralPath $Root
$Log = Join-Path $Root 'install.log'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Stamp = Join-Path $Root '.venv\dubber-installed'  # written only after the components installed completely

$LocalFfmpeg = Join-Path $Root 'ffmpeg\bin'  # ffmpeg downloaded here when winget is missing (dubber/config.py)
# CI only: no winget, and Python, ffmpeg and the C++ runtime downloaded directly (the path a PC without winget takes)
$TestMode = $env:DUBBER_SETUP_TEST -eq '1'
$PythonUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'  # 3.12's last release with an installer
$FfmpegUrls = @('https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
    'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip')
$VCRedistUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'

function Say([string]$Text) { Write-Host $Text }

function Stop-WithError([string]$Text) {
    Write-Host ''
    Write-Host $Text -ForegroundColor Red
    if (Test-Path -LiteralPath $Log) { Write-Host "Подробный журнал: $Log (его можно отправить Адаму)." }
    if (-not $NoStart) { [void](Read-Host 'Нажмите Enter, чтобы закрыть окно') }
    exit 1
}

function Update-PathFromSystem {
    # winget changes PATH for new windows only; read it again so this window sees Python/ffmpeg right away
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
    if (Test-Path -LiteralPath $LocalFfmpeg) { $env:Path = "$LocalFfmpeg;$env:Path" }
}

function Find-Python {
    # The "py" launcher first (python.org and winget installs), then "python" (not the Microsoft Store stub, which
    # fails the version check below), then where the python.org installer puts it for this user.
    # Only 64-bit Intel/AMD Python: Whisper has no build for ARM or 32-bit Windows (an ARM PC runs x64 Python fine).
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python'; Args = @() },
        @{ Exe = (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'); Args = @() }
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $out = & $c.Exe @($c.Args) -c "import sys, sysconfig; print('%d.%d' % sys.version_info[:2]); print(sys.executable); print(sysconfig.get_platform())" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -ne 0 -or -not $out -or $out.Count -lt 3) { continue }
        if ([version]$out[0] -ge [version]'3.10' -and $out[2] -eq 'win-amd64') { return $out[1] }
    }
    return $null
}

function Test-Winget { return (-not $TestMode) -and [bool](Get-Command winget -ErrorAction SilentlyContinue) }

function Install-WithWinget([string]$Id, [string]$Name, [string[]]$Extra = @()) {
    # A fresh Windows 11 may not have winget yet (it comes with a Microsoft Store update): the callers then download
    # the program directly.
    if (-not (Test-Winget)) { return }
    Say "Устанавливаю $Name (один раз, несколько минут)…"
    & winget install -e --id $Id @Extra --accept-package-agreements --accept-source-agreements --disable-interactivity
    Update-PathFromSystem
}

function Save-Download([string]$Url, [string]$File) {
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $ProgressPreference = 'SilentlyContinue'  # its progress bar makes downloads many times slower in PowerShell 5.1
        Invoke-WebRequest -Uri $Url -OutFile $File -UseBasicParsing
        return $true
    } catch {
        Add-Content -LiteralPath $Log -Value "download failed: $Url $($_.Exception.Message)" -ErrorAction SilentlyContinue
        return $false
    }
}

function Install-Python {
    Install-WithWinget 'Python.Python.3.12' 'Python' @('--architecture', 'x64')
    if (Find-Python) { return }
    Say 'Скачиваю и устанавливаю Python (один раз, пару минут)…'
    $exe = Join-Path $env:TEMP 'python-3.12.10-amd64.exe'
    if (-not (Save-Download $PythonUrl $exe)) {
        Stop-WithError 'Не удалось скачать Python. Проверьте интернет и запустите «Дубляж» снова.'
    }
    # For this user only: no administrator rights needed
    $p = Start-Process -FilePath $exe -Wait -PassThru -ArgumentList @('/quiet', 'InstallAllUsers=0', 'PrependPath=1',
        'Include_launcher=1', 'InstallLauncherAllUsers=0', 'Include_test=0')
    Remove-Item -LiteralPath $exe -Force -ErrorAction SilentlyContinue
    Update-PathFromSystem
    # The caller checks that a usable Python is there now (a non-zero code can also mean "already installed")
    if ($p.ExitCode -ne 0) { Add-Content -LiteralPath $Log -Value "python installer exit $($p.ExitCode)" -ErrorAction SilentlyContinue }
}

function Install-Ffmpeg {
    Install-WithWinget 'Gyan.FFmpeg' 'ffmpeg'
    if ((Get-Command ffmpeg -ErrorAction SilentlyContinue) -and -not $TestMode) { return }
    Say 'Скачиваю ffmpeg (один раз, около 100 МБ)…'
    $zip = Join-Path $env:TEMP 'dubber-ffmpeg.zip'
    $unpack = Join-Path $env:TEMP 'dubber-ffmpeg'
    $ok = $false
    foreach ($url in $FfmpegUrls) { if (Save-Download $url $zip) { $ok = $true; break } }
    if (-not $ok) { Stop-WithError 'Не удалось скачать ffmpeg. Проверьте интернет и запустите «Дубляж» снова.' }
    Remove-Item -LiteralPath $unpack -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -LiteralPath $zip -DestinationPath $unpack -Force
    $exe = Get-ChildItem -LiteralPath $unpack -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if (-not $exe -or -not (Test-Path -LiteralPath (Join-Path $exe.DirectoryName 'ffprobe.exe'))) {
        Stop-WithError 'В скачанном архиве нет ffmpeg. Запустите «Дубляж» снова.'
    }
    $target = Join-Path $Root 'ffmpeg'
    Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $exe.Directory.Parent.FullName -Destination $target  # <top>\bin\ffmpeg.exe -> ffmpeg\bin
    Remove-Item -LiteralPath $zip, $unpack -Recurse -Force -ErrorAction SilentlyContinue
    Update-PathFromSystem
}

function Test-VCRuntime {
    # Whisper and the offline translator (ctranslate2, onnxruntime) need the Microsoft Visual C++ runtime, which
    # Python doesn't bring and a fresh Windows may not have: without it every dub fails ("DLL load failed").
    # Version 14.40+: older ones crash programs built with the current Visual Studio.
    if ($TestMode -and -not $script:VCInstalled) { return $false }
    $system = Join-Path $env:SystemRoot $(if ([Environment]::Is64BitProcess) { 'System32' } else { 'Sysnative' })
    foreach ($dll in 'msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll') {
        if (-not (Test-Path -LiteralPath (Join-Path $system $dll))) { return $false }
    }
    $v = (Get-Item -LiteralPath (Join-Path $system 'msvcp140.dll')).VersionInfo
    return [version]('{0}.{1}.{2}' -f $v.FileMajorPart, $v.FileMinorPart, $v.FileBuildPart) -ge [version]'14.40.0'
}

function Install-VCRuntime {
    Say 'Устанавливаю библиотеки Microsoft Visual C++ (один раз). Если Windows спросит разрешение, нажмите «Да».'
    Install-WithWinget 'Microsoft.VCRedist.2015+.x64' 'Microsoft Visual C++'
    if ($TestMode -or -not (Test-VCRuntime)) {
        $exe = Join-Path $env:TEMP 'vc_redist.x64.exe'
        if (-not (Save-Download $VCRedistUrl $exe)) {
            Stop-WithError 'Не удалось скачать библиотеки Microsoft Visual C++. Проверьте интернет и запустите «Дубляж» снова.'
        }
        try {
            $p = Start-Process -FilePath $exe -Wait -PassThru -ArgumentList @('/install', '/passive', '/norestart')
        } catch {
            Stop-WithError 'Без разрешения Windows библиотеки Microsoft Visual C++ не установить. Запустите «Дубляж» снова и нажмите «Да».'
        }
        Remove-Item -LiteralPath $exe -Force -ErrorAction SilentlyContinue
        # 0 = installed, 1638 = a newer version is already there, 3010 = installed, restart suggested
        if ($p.ExitCode -notin 0, 1638, 3010) { Add-Content -LiteralPath $Log -Value "vc_redist exit $($p.ExitCode)" }
    }
    $script:VCInstalled = $true
    if (-not (Test-VCRuntime)) {
        Stop-WithError 'Не удалось установить библиотеки Microsoft Visual C++. Перезагрузите компьютер и запустите «Дубляж» снова.'
    }
}


function Install-Shortcut([string]$Folder) {
    if (-not $Folder -or -not (Test-Path -LiteralPath $Folder)) { return }
    [DubberSetup.Shortcut]::Save(
        (Join-Path $Folder 'Дубляж видео.lnk'),
        (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'),
        "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"",
        $Root,
        (Join-Path $Root 'dubber\assets\dubber.ico'),
        'Дубляж видео: озвучка видео на русском и других языках')
}

if ($ShortcutOnly) {
    if (-not $Native) { exit 1 }
    try {
        Install-Shortcut ([Environment]::GetFolderPath('Desktop'))
        Install-Shortcut ([Environment]::GetFolderPath('Programs'))
    } catch { exit 1 }
    exit 0
}

Say '=== Дубляж видео ==='

# Files from a downloaded ZIP are marked "from the internet": Windows would ask before each start. Unmark ours.
try {
    Get-ChildItem -LiteralPath $Root -Recurse -File -Include *.cmd, *.bat, *.ps1 -ErrorAction SilentlyContinue |
        Unblock-File -ErrorAction SilentlyContinue
} catch {}

if (Test-Path -LiteralPath $LocalFfmpeg) { $env:Path = "$LocalFfmpeg;$env:Path" }

# A first install in a deep folder: some component files have names so long that the full path passes Windows' old
# limit of 260 characters, and the install would fail halfway with a puzzling error. Say it plainly instead.
if (-not (Test-Path -LiteralPath $Stamp) -and $Root.Length -gt 90) {
    $long = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -ErrorAction SilentlyContinue).LongPathsEnabled
    if ($long -ne 1) {
        Stop-WithError ("Папка программы лежит слишком глубоко ($($Root.Length) символов): $Root`n" +
            'Перенесите папку программы ближе к началу диска, например в C:\Dubber, и запустите «Start Dubber» оттуда.')
    }
}

# The program's own Python stops working when the Python it was made from is removed or upgraded: start it afresh.
if (Test-Path -LiteralPath $VenvPython) {
    $ErrorActionPreference = 'Continue'
    & $VenvPython -c "pass" 2>$null
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) {
        Say 'Окружение Python повреждено — устанавливаю компоненты заново.'
        Remove-Item -LiteralPath (Join-Path $Root '.venv') -Recurse -Force
    }
}

# 1. Python (64-bit, 3.10 or newer)
$python = Find-Python
if ((-not $python -and -not (Test-Path -LiteralPath $VenvPython)) -or ($TestMode -and -not (Test-Path -LiteralPath $Stamp))) {
    Install-Python
    $python = Find-Python
    if (-not $python) {
        Stop-WithError 'Python установлен, но это окно его пока не видит. Закройте окно и запустите «Дубляж» ещё раз.'
    }
}

# 2. ffmpeg (makes the video)
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or ($TestMode -and -not (Test-Path -LiteralPath $LocalFfmpeg))) {
    Install-Ffmpeg
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
        Stop-WithError 'ffmpeg установлен, но это окно его пока не видит. Закройте окно и запустите «Дубляж» ещё раз.'
    }
}

# 2b. The Microsoft Visual C++ runtime (Whisper and the offline translator need it)
if (-not (Test-VCRuntime)) { Install-VCRuntime }

# 3. The program's components (once; later versions install their own when the program updates itself)
if (-not (Test-Path -LiteralPath $Stamp) -and (Test-Path -LiteralPath $VenvPython)) {
    # Installed by an older version (before this script existed): nothing to install if the program imports.
    & $VenvPython -c "import dubber.app" 2>$null
    if ($LASTEXITCODE -eq 0) { Set-Content -LiteralPath $Stamp -Value (Get-Date -Format s) -Encoding ASCII }
}
if (-not (Test-Path -LiteralPath $Stamp)) {
    Say 'Устанавливаю компоненты программы. В первый раз это 10–15 минут: скачивается около 1 ГБ.'
    Say 'Строки ниже должны меняться. Не закрывайте окно.'
    if (Test-Path -LiteralPath $Log) { Remove-Item -LiteralPath $Log -Force }
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        & $python -m venv (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0) { Stop-WithError 'Не удалось создать окружение Python.' }
    }
    & $VenvPython -m pip install --upgrade pip setuptools wheel --log $Log
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Не удалось установить компоненты. Проверьте интернет и запустите «Дубляж» снова.' }
    # No pip "build isolation": that hidden step could sit silently for a long time on a slow PC.
    & $VenvPython -m pip install --upgrade --no-build-isolation --log $Log -e $Root
    if ($LASTEXITCODE -ne 0) { Stop-WithError 'Не удалось установить компоненты. Проверьте интернет и запустите «Дубляж» снова.' }
    & $VenvPython -m pip install --upgrade yt-dlp --log $Log | Out-Null
    Set-Content -LiteralPath $Stamp -Value (Get-Date -Format s) -Encoding ASCII
    Say 'Компоненты установлены.'
}

function Test-Components {
    # stderr not captured: with ErrorActionPreference Stop, Windows PowerShell turns a redirected warning into an error
    $ErrorActionPreference = 'Continue'
    $out = & $VenvPython -m dubber.deps
    return ($out -join ' ')
}

# 3b. Every start: every component there and loading (an interrupted install or update, a file an antivirus took,
# a component a newer version needs). dubber/deps.py: exit 1 = missing (reinstall), 2 = doesn't load (C++ runtime).
$problem = Test-Components
if ($LASTEXITCODE -eq 1) {
    Say "Доустанавливаю недостающие компоненты: $problem"
    & $VenvPython -m pip install --upgrade --no-build-isolation --log $Log -e $Root
    $problem = Test-Components
}
if ($LASTEXITCODE -eq 2) {
    Add-Content -LiteralPath $Log -Value "components don't load: $problem" -ErrorAction SilentlyContinue
    Install-VCRuntime
    $problem = Test-Components
}
if ($LASTEXITCODE -ne 0) {
    Add-Content -LiteralPath $Log -Value "dubber.deps: $problem" -ErrorAction SilentlyContinue
    Stop-WithError "Не удалось установить компоненты программы ($problem). Проверьте интернет и запустите «Дубляж» снова."
}

# YouTube changes often and a fresh downloader (yt-dlp) fixes most "couldn't download" errors: refresh it every few days.
$Fresh = Join-Path $Root '.venv\yt-dlp-checked'
if (-not (Test-Path -LiteralPath $Fresh) -or (Get-Item -LiteralPath $Fresh).LastWriteTime -lt (Get-Date).AddDays(-3)) {
    Say 'Проверяю обновление загрузчика видео…'
    & $VenvPython -m pip install -q --upgrade --disable-pip-version-check yt-dlp 2>$null
    if ($LASTEXITCODE -eq 0) { Set-Content -LiteralPath $Fresh -Value (Get-Date -Format s) -Encoding ASCII }
}

# 4. Desktop and Start menu shortcuts with the program's icon (renewed every time: the folder may have moved)
try {
    if (-not $Native) { throw 'Windows helper not available' }
    Install-Shortcut ([Environment]::GetFolderPath('Desktop'))
    Install-Shortcut ([Environment]::GetFolderPath('Programs'))
} catch {
    Say "Не удалось создать ярлык на рабочем столе ($($_.Exception.Message)). Запускайте файл «Start Dubber» в папке программы."
}

if ($NoStart) { exit 0 }

# 5. Start (the program opens the page in the browser and updates itself when a new version is out)
$env:DUBBER_LAUNCHER = '1'  # the shortcuts are done: the program needn't make them
& $VenvPython -m dubber.app
if ($LASTEXITCODE -ne 0) {
    [void](Read-Host 'Нажмите Enter, чтобы закрыть окно')
}
