@echo off
title FileRenamer
setlocal EnableDelayedExpansion

set SCRIPT=%~dp0file_renamer.py

python --version >nul 2>&1
if %errorlevel% == 0 (
    python "%SCRIPT%"
    goto fin
)

set FOUND=

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
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python310\python.exe"
) do (
    if exist %%P (
        set FOUND=%%P
        goto found
    )
)

for /f "skip=2 tokens=2,*" %%A in ('reg query "HKLM\SOFTWARE\Python\PythonCore" /s /v ExecutablePath 2^>nul') do (
    if exist "%%B" ( set FOUND=%%B & goto found )
)
for /f "skip=2 tokens=2,*" %%A in ('reg query "HKCU\SOFTWARE\Python\PythonCore" /s /v ExecutablePath 2^>nul') do (
    if exist "%%B" ( set FOUND=%%B & goto found )
)

echo.
echo Python introuvable. Solutions :
echo.
echo  1) Creer un .exe (recommande) - dans un terminal NORMAL (pas admin) :
echo     pip install pyinstaller
echo     pyinstaller --onefile --windowed --uac-admin --name FileRenamer file_renamer.py
echo     Le .exe sera dans le dossier dist\
echo.
echo  2) Reinstaller Python : https://www.python.org/downloads/
echo     IMPORTANT : cocher "Install for all users" ET "Add to PATH"
echo.
pause
goto fin

:found
echo Utilisation de : %FOUND%
%FOUND% "%SCRIPT%"

:fin
endlocal
