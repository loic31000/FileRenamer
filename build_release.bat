@echo off
chcp 65001 >nul
title FileRenamer - Build Release
color 0A

cd /d "%~dp0"

echo.
echo  ================================================
echo   FileRenamer - Build Release GitHub
echo  ================================================
echo.

set VERSION=3.0.0
set /p VERSION="Version (defaut: 3.0.0, appuyez Entree) : "
if "%VERSION%"=="" set VERSION=3.0.0
echo.
echo  Version : v%VERSION%
echo.

:: Chercher Python
set PYTHON=
for %%P in (python python3) do (
    if not defined PYTHON (
        %%P --version >nul 2>&1 && set PYTHON=%%P
    )
)
if not defined PYTHON (
    for %%P in (
        "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
    ) do (
        if not defined PYTHON (
            if exist %%P set PYTHON=%%P
        )
    )
)
if not defined PYTHON (
    echo [ERREUR] Python introuvable.
    pause & exit /b 1
)
echo [OK] Python : %PYTHON%

:: PyInstaller
%PYTHON% -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installation PyInstaller...
    %PYTHON% -m pip install pyinstaller --quiet
    if errorlevel 1 (
        echo [ERREUR] Impossible d installer PyInstaller.
        pause & exit /b 1
    )
)
echo [OK] PyInstaller disponible

:: Nettoyage
echo.
echo  Compilation en cours...
if exist dist           rmdir /s /q dist
if exist build          rmdir /s /q build
if exist FileRenamer.spec del /q FileRenamer.spec
echo.

:: Compilation
if exist icon.ico (
    echo [OK] Icone trouvee
    if exist icon_48.png (
        %PYTHON% -m PyInstaller --onefile --windowed --uac-admin --name FileRenamer --clean --icon icon.ico --add-data "icon.ico;." --add-data "icon_48.png;." file_renamer.py
    ) else (
        %PYTHON% -m PyInstaller --onefile --windowed --uac-admin --name FileRenamer --clean --icon icon.ico --add-data "icon.ico;." file_renamer.py
    )
) else (
    echo [INFO] Sans icone
    %PYTHON% -m PyInstaller --onefile --windowed --uac-admin --name FileRenamer --clean file_renamer.py
)

if errorlevel 1 (
    echo.
    echo [ERREUR] Compilation echouee.
    pause & exit /b 1
)
echo [OK] EXE : dist\FileRenamer.exe

:: Dossier release
set "RELEASE_DIR=%~dp0release\FileRenamer-v%VERSION%"
if exist "%~dp0release" rmdir /s /q "%~dp0release"
mkdir "%RELEASE_DIR%"
copy "%~dp0dist\FileRenamer.exe" "%RELEASE_DIR%\FileRenamer.exe" >nul
copy "%~dp0README.md"            "%RELEASE_DIR%\README.md"        >nul
if exist "%~dp0CHANGELOG.md" copy "%~dp0CHANGELOG.md" "%RELEASE_DIR%\CHANGELOG.md" >nul
echo [OK] Fichiers copies

:: ZIP
echo  Creation du ZIP...
powershell -NoProfile -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%~dp0release\FileRenamer-v%VERSION%-Windows.zip' -Force"
if errorlevel 1 (
    echo [ERREUR] Impossible de creer le ZIP.
    pause & exit /b 1
)
echo [OK] ZIP : release\FileRenamer-v%VERSION%-Windows.zip

echo.
echo  ================================================
echo   Termine ! Fichiers a uploader sur GitHub :
echo.
echo   dist\FileRenamer.exe
echo   release\FileRenamer-v%VERSION%-Windows.zip
echo  ================================================
echo.
pause