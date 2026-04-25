@echo off
title xDrive V1.0 - Chiaki Downloader
echo ==========================================
echo    xDrive Chiaki Downloader
echo ==========================================
echo.
echo Downloading the latest compatible Chiaki release...
echo.
:: Using curl (Windows 10/11 standard)
curl -L -o Chiaki_Installer.zip https://github.com/thestr4ng3r/chiaki/releases/latest/download/Chiaki-v2.2.0-Windows-x86_64.zip
echo.
echo ==========================================
echo DOWNLOAD COMPLETE! 
echo.
echo NEXT STEPS:
echo 1. Extract the 'Chiaki_Installer.zip' folder.
echo 2. Run 'chiaki.exe' inside that folder.
echo ==========================================
pause
