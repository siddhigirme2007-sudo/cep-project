@echo off
REM Builds the native helpers used by modules\analysis.py and
REM modules\extraction.py. Requires MinGW-w64 (gcc/g++) on PATH or Dev-Cpp.
REM Run once after cloning the project: native\build.bat

cd /d "%~dp0"

set "CC=gcc"
set "CXX=g++"

where gcc >nul 2>nul
if errorlevel 1 (
    if exist "C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\gcc.exe" (
        set "CC=C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\gcc.exe"
        set "CXX=C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\g++.exe"
    )
)

echo Building classify.exe (C)...
"%CC%" -O2 -Wall -Wextra -o classify.exe classify.c
if errorlevel 1 goto :error

echo Building parse_lines.exe (C++)...
"%CXX%" -O2 -std=c++11 -Wall -Wextra -o parse_lines.exe parse_lines.cpp
if errorlevel 1 goto :error

echo Done. Built classify.exe and parse_lines.exe in %cd%
goto :eof

:error
echo.
echo Build failed. Make sure MinGW-w64 (gcc/g++) is installed and on PATH.
echo   Easiest option: install MSYS2 (https://www.msys2.org/), then run:
echo     pacman -S mingw-w64-ucrt-x86_64-gcc
echo   and add its bin folder to PATH before re-running this script.
exit /b 1

