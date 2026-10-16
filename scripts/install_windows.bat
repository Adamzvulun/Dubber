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
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Дубляж видео.lnk'); $s.TargetPath='%CD%\scripts\start_windows.bat'; $s.WorkingDirectory='%CD%'; $s.Save()"

echo.
echo Готово! Запускайте программу ярлыком «Дубляж видео» на рабочем столе.
pause
exit /b

:error
echo.
echo Ошибка установки. Сфотографируйте это окно и отправьте помощнику.
pause
