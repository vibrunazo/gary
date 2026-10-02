@echo off
rem Builds gary_view (the replay / POV viewer) with the Visual Studio C++ toolchain (CMake + Ninja ship with Visual Studio).
rem Usage: env\build.bat   (from any directory)
setlocal
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (echo vswhere.exe not found: install Visual Studio with the C++ workload & exit /b 1)
"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath > "%TEMP%\gary_vsdir.txt"
set /p VSDIR=<"%TEMP%\gary_vsdir.txt"
if not defined VSDIR (echo Visual Studio C++ tools not found & exit /b 1)
call "%VSDIR%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
set "SRC=%~dp0"
cmake -S "%SRC%." -B "%SRC%build" -G Ninja -DCMAKE_BUILD_TYPE=Release || exit /b 1
cmake --build "%SRC%build" || exit /b 1
echo Built %SRC%build\gary_view.exe
