@echo off
title Novel Cevirmen

REM Sanal ortam kurulu mu kontrol et — yoksa otomatik kur
if not exist "venv\Scripts\activate.bat" (
    echo.
    echo [BILGI] Sanal ortam bulunamadi, kuruluyor...
    echo.
    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo [HATA] Python bulunamadi! Lutfen python.org adresinden yukleyin.
        pause
        exit /b 1
    )
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [HATA] Bagimliliklar yuklenemedi!
        pause
        exit /b 1
    )
    echo [OK] Kurulum tamamlandi.
    echo.
) else (
    REM Sanal ortami etkinlestir
    call venv\Scripts\activate.bat

    REM PyQt6 yuklu mu kontrol et — venv bozuksa yeniden kur
    python -c "import PyQt6" >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [BILGI] Eksik bagimliliklar tespit edildi, yukleniyor...
        pip install -r requirements.txt --quiet
        echo [OK] Bagimliliklar yuklendi.
        echo.
    )
)

REM Uygulamayi baslat
python main.py

REM Uygulama hatayla kapandiysa mesaj goster
if %errorlevel% neq 0 (
    echo.
    echo [HATA] Uygulama beklenmedik sekilde kapandi. Hata kodu: %errorlevel%
    echo.
    pause
)