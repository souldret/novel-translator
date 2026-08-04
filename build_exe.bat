@echo off
title Novel Cevirmen - EXE Paketleme
echo.
echo ============================================================
echo   Novel Cevirmen - PyInstaller paketleme
echo ============================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [HATA] Once install.bat ile sanal ortami kurun.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [BILGI] PyInstaller yukleniyor...
    pip install pyinstaller --quiet
)

echo [1/2] EXE olusturuluyor...
pyinstaller --noconfirm novel_cevirmen.spec
if %errorlevel% neq 0 (
    echo [HATA] Paketleme basarisiz.
    pause
    exit /b 1
)

echo.
echo [OK] Cikti: dist\NovelCevirmen.exe
echo.
pause
