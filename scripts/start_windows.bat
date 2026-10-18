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
rem The program updates itself, this file included. cmd reads a .bat file line by line while it runs, so the start and
rem everything after it stay on one line: a changed file is never read half-way.
.venv\Scripts\python -m dubber.app & pause & exit /b
