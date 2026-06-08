@echo off
echo === MSBatch Environment Setup ===
echo.
echo Creating Python environment...
conda create --prefix "%~dp0env" python=3.11 -y
if %errorlevel% neq 0 (
    echo ERROR: Failed to create conda environment.
    echo Make sure Miniconda/Anaconda is installed.
    pause
    exit /b 1
)
echo.
echo Installing dependencies...
call "%~dp0env\python.exe" -m pip install pymatgen mp-api abtem numpy scipy Pillow click PyQt6 py3Dmol pytest
echo.
echo === Setup Complete ===
echo Run: env\python.exe gui_main.py
pause
