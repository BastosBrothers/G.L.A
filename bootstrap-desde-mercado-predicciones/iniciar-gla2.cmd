@echo off
set "NVIM=%LOCALAPPDATA%\nvim-win64\bin\nvim.exe"
cd /d "%~dp0"
"%NVIM%" %*
