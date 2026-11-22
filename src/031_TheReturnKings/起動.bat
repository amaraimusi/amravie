@echo off
cd /d "%~dp0"
py -3.9 main.py
if errorlevel 1 pause
