@echo off
echo Stopping the Evaluation System...

:: Kill python running app.py
wmic process where "name='python.exe' and commandline like '%%app.py%%'" call terminate

:: Kill pythonw running app.py (just in case)
wmic process where "name='pythonw.exe' and commandline like '%%app.py%%'" call terminate

echo.
echo Done.
pause
