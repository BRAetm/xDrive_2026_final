@echo off
title AuraSync V4 - Dependency Installer
echo ==========================================
echo    AuraSync V4 Dependency Installer
echo ==========================================
echo.
echo This script will install all necessary Python libraries for AuraSync.
echo.
echo Step 1: Installing Core GUI components...
py -m pip install PyQt5 PyQtWebEngine
echo.
echo Step 2: Installing AuraSync dependencies...
py -m pip install requests pywebview vgamepad psutil mss opencv-python numpy pynput
echo.
echo NOTE: If 'pythonnet' fails to install, you can IGNORE it. 
echo xDrive uses PyQt5 and does not need it.


echo.
echo ==========================================
echo INSTALLATION COMPLETE!
echo.
echo You can now run 'xDrive.exe' to launch the program.

echo ==========================================
pause
