@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
echo === Установка программы «Дубляж видео» ===
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo Устанавливаю Python...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo Python установлен. Закройте это окно и запустите install_windows.bat ещё раз.
  pause
  exit /b
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo Устанавливаю ffmpeg...
  winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
  echo.
  echo ffmpeg установлен. Закройте это окно и запустите install_windows.bat ещё раз.
  pause
  exit /b
)

if not exist .venv (
  echo Создаю окружение Python...
  py -3 -m venv .venv || goto :error
)
echo Устанавливаю и обновляю компоненты (это может занять несколько минут)...
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install --upgrade -e . || goto :error
.venv\Scripts\python -m pip install --upgrade yt-dlp >nul

echo Создаю ярлык «Дубляж видео» на рабочем столе...
rem Non-ASCII text on the powershell command line arrives as '?', so the shortcut name is built
rem from char codes and the folder path is passed through an environment variable.
set "DUBBER_DIR=%CD%"
powershell -NoProfile -Command "try { $n=[string]::new([char[]](0x414,0x443,0x431,0x43B,0x44F,0x436,0x20,0x432,0x438,0x434,0x435,0x43E)); $d=$env:DUBBER_DIR; $s=(New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), $n+'.lnk')); $s.TargetPath=$d+'\scripts\start_windows.bat'; $s.WorkingDirectory=$d; $s.Save() } catch { Write-Host $_; exit 1 }"
if errorlevel 1 goto :noshortcut

echo.
echo Готово! Запускайте программу ярлыком «Дубляж видео» на рабочем столе.
pause
exit /b

:noshortcut
echo.
echo Программа установлена, но ярлык создать не удалось.
echo Запускайте её файлом scripts\start_windows.bat (двойной щелчок).
pause
exit /b

:error
echo.
echo Ошибка установки. Сфотографируйте это окно и отправьте помощнику.
pause
