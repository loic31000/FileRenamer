@echo off
chcp 65001 >nul
title Creation du .exe FileRenamer
cd /d "%~dp0"

echo.
echo === Creation de FileRenamer.exe ===
echo.

:: Trouver python
set PYTHON=
python --version >nul 2>&1
if %errorlevel% == 0 ( set PYTHON=python & goto found_python )

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do ( if exist %%P ( set PYTHON=%%P & goto found_python ) )

echo ERREUR : Python introuvable.
echo Telechargez Python sur https://www.python.org/downloads/
echo Cochez bien "Add to PATH" lors de l'installation.
pause & exit /b 1

:found_python
echo Python trouve : %PYTHON%
echo.

echo [1/2] Installation de PyInstaller...
%PYTHON% -m pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERREUR pip. Verifiez votre connexion internet.
    pause & exit /b 1
)
echo OK.
echo.

echo [2/2] Compilation...
:: Utiliser "python -m PyInstaller" plutot que la commande pyinstaller directement
%PYTHON% -m PyInstaller --onefile --windowed --uac-admin --name FileRenamer file_renamer.py

if %errorlevel% == 0 (
    echo.
    echo ========================================
    echo  SUCCES !
    echo  Votre exe : %~dp0dist\FileRenamer.exe
    echo  - Pas besoin de Python
    echo  - Demande les droits Admin automatiquement
    echo ========================================
    echo.
    explorer "%~dp0dist"
) else (
    echo.
    echo ERREUR lors de la compilation.
    echo Verifiez que file_renamer.py est dans le meme dossier.
)
pause