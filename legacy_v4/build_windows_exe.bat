@echo off
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1
python -m compileall -q app.py enhancements.py imaging.py pro.py launcher.py smoke_test.py
if errorlevel 1 exit /b 1
python -m unittest test_imaging
if errorlevel 1 exit /b 1
pyinstaller --noconfirm --clean --onefile --windowed --collect-all tkinterdnd2 --name BatchWatermarkToolProV4_2 launcher.py
pause
