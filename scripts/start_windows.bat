@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
if not exist .venv (
  echo Программа ещё не установлена. Сначала запустите scripts\install_windows.bat
  pause
  exit /b
)
echo Запускаю «Дубляж видео». Страница откроется в браузере.
echo Не закрывайте это окно, пока пользуетесь программой.
.venv\Scripts\python -m dubber.app
pause
