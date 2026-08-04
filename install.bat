@echo off
title Novel Cevirmen - Kurulum

echo.
echo ============================================================
echo   Novel Cevirmen - Kurulum
echo ============================================================
echo.

REM Python yuklu mu kontrol et
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi!
    echo.
    echo Lutfen Python 3.11 veya uzeri yukleyin:
    echo https://www.python.org/downloads/
    echo.
    echo Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin.
    pause
    exit /b 1
)

echo [OK] Python bulundu:
python --version
echo.

REM Sanal ortam zaten var mi?
if exist "venv\Scripts\activate.bat" (
    echo [BILGI] Sanal ortam zaten mevcut, atlaniyor...
) else (
    echo [1/3] Sanal ortam olusturuluyor...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [HATA] Sanal ortam olusturulamadi!
        pause
        exit /b 1
    )
    echo [OK] Sanal ortam olusturuldu.
)
echo.

REM Sanal ortami etkinlestir
echo [2/3] Sanal ortam etkinlestiriliyor...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [HATA] Sanal ortam etkinlestirilemedi!
    pause
    exit /b 1
)
echo [OK] Sanal ortam aktif.
echo.

REM Bagimliliklar
echo [3/3] Bagimliliklar yukleniyor...
echo.
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Bagimliliklar yuklenemedi!
    echo requirements.txt dosyasini kontrol edin.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Kurulum tamamlandi!
echo ============================================================
echo.
echo Uygulamayi baslatmak icin: start.bat
echo.
pause