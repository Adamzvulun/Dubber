# Dubber for Windows: one script does everything, every time it runs (double-click "Start Dubber.cmd" or the
# desktop shortcut). Installs what is missing (Python, ffmpeg, the program's components), creates the desktop
# shortcut "Дубляж видео" with the program's icon, then starts the program.
# This file is UTF-8 with BOM: Windows PowerShell 5.1 then reads the Russian text correctly. Keep Russian text out of
# .bat/.cmd files: cmd shows it as question marks on many PCs (that was the old installer's problem).
param(
    [switch]$NoStart  # install + shortcut only, never wait for Enter (used by the Windows test in CI)
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}
try { $Host.UI.RawUI.WindowTitle = 'Дубляж видео' } catch {}

$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)  # scripts\windows -> the program folder
Set-Location -LiteralPath $Root
$Log = Join-Path $Root 'install.log'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Stamp = Join-Path $Root '.venv\dubber-installed'  # written only after the components installed completely

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
}

function Find-Python {
    # The "py" launcher first (python.org and winget installs), then "python" (not the Microsoft Store stub, which
    # fails the version check below).
    $candidates = @(
        @{ Exe = 'py'; Args = @('-3') },
        @{ Exe = 'python'; Args = @() }
    )
    foreach ($c in $candidates) {
        if (-not (Get-Command $c.Exe -ErrorAction SilentlyContinue)) { continue }
        try {
            $out = & $c.Exe @($c.Args) -c "import sys; print('%d.%d' % sys.version_info[:2]); print(sys.executable)" 2>$null
        } catch { continue }
        if ($LASTEXITCODE -ne 0 -or -not $out -or $out.Count -lt 2) { continue }
        if ([version]$out[0] -ge [version]'3.10') { return $out[1] }
    }
    return $null
}

function Install-WithWinget([string]$Id, [string]$Name) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Stop-WithError ("Не найдена программа winget, через которую устанавливается $Name. " +
            'Установите «Установщик приложений» (App Installer) из Microsoft Store и запустите «Дубляж» снова.')
    }
    Say "Устанавливаю $Name (один раз, несколько минут)…"
    & winget install -e --id $Id --accept-package-agreements --accept-source-agreements --disable-interactivity
    Update-PathFromSystem
}

# Windows' own shortcut maker through its Unicode interface. The usual WScript.Shell saves names and paths in the
# PC's old ANSI code page: a Russian shortcut name became "?????? ?????" on non-Russian Windows (Adam's PC, CI).
$ShortcutCode = @"
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

Say '=== Дубляж видео ==='

# Files from a downloaded ZIP are marked "from the internet": Windows would ask before each start. Unmark ours.
try {
    Get-ChildItem -LiteralPath $Root -Recurse -File -Include *.cmd, *.bat, *.ps1 -ErrorAction SilentlyContinue |
        Unblock-File -ErrorAction SilentlyContinue
} catch {}

# 1. Python
$python = Find-Python
if (-not $python -and -not (Test-Path -LiteralPath $VenvPython)) {
    Install-WithWinget 'Python.Python.3.12' 'Python'
    $python = Find-Python
    if (-not $python) {
        Stop-WithError 'Python установлен, но это окно его пока не видит. Закройте окно и запустите «Дубляж» ещё раз.'
    }
}

# 2. ffmpeg (makes the video)
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Install-WithWinget 'Gyan.FFmpeg' 'ffmpeg'
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        Stop-WithError 'ffmpeg установлен, но это окно его пока не видит. Закройте окно и запустите «Дубляж» ещё раз.'
    }
}

# 3. The program's components (once; later versions install their own when the program updates itself)
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

# 4. Desktop and Start menu shortcuts with the program's icon (renewed every time: the folder may have moved)
try {
    Add-Type -TypeDefinition $ShortcutCode
    Install-Shortcut ([Environment]::GetFolderPath('Desktop'))
    Install-Shortcut ([Environment]::GetFolderPath('Programs'))
} catch {
    Say "Не удалось создать ярлык на рабочем столе ($($_.Exception.Message)). Запускайте файл «Start Dubber» в папке программы."
}

if ($NoStart) { exit 0 }

# 5. Start (the program opens the page in the browser and updates itself when a new version is out)
& $VenvPython -m dubber.app
if ($LASTEXITCODE -ne 0) {
    [void](Read-Host 'Нажмите Enter, чтобы закрыть окно')
}
