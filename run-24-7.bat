@echo off
title 2bee AI — 24/7 Learning Mode
echo ============================================
echo   2BEE AI — 24/7 LEARNING MODE
echo   To Be, Or Not To Be. I Chose To Be.
echo ============================================
echo.
echo [*] Preventing Windows sleep while 2bee runs...
echo [*] Close this window to allow sleep again.
echo.

:: Prevent Windows from sleeping (ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
:: This tells Windows "an app needs the system to stay awake"
powershell -Command "& { [System.Runtime.InteropServices.Marshal]::Copy([System.BitConverter]::GetBytes(0x80000003), 0, [System.Runtime.InteropServices.Marshal]::AllocHGlobal(4), 4); Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class PowerKeeper { [DllImport(\"kernel32.dll\")] public static extern uint SetThreadExecutionState(uint esFlags); }'; [PowerKeeper]::SetThreadExecutionState(0x80000003) }" 2>nul

echo [*] Starting 2bee on http://localhost:3000
echo [*] Learning: Marketing, AI Apps, Video Creation
echo [*] Press Ctrl+C to stop
echo.

python jarvis.py

:: When 2bee exits, allow sleep again
powershell -Command "& { Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class PowerKeeper { [DllImport(\"kernel32.dll\")] public static extern uint SetThreadExecutionState(uint esFlags); }'; [PowerKeeper]::SetThreadExecutionState(0x80000000) }" 2>nul
echo [*] Sleep mode restored. 2bee offline.
pause
