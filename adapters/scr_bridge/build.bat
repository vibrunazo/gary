@echo off
rem Builds gary_scr (the in-process SC:R adapter DLL) and its offline tests with the Visual
rem Studio C++ toolchain, 32-bit (the pinned target is the x86 client). See build.bat in env/
rem for the 64-bit variant used by gary_env.
rem Usage: adapters\scr_bridge\build.bat   (from any directory)
setlocal
where cl >nul 2>nul && goto :have_cl
rem vcvars32.bat locates Visual Studio via vswhere.exe, which lives here but is often not on PATH.
set "PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer;%PATH%"
set "VCVARS=%ProgramFiles(x86)%\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars32.bat"
if not exist "%VCVARS%" set "VCVARS=%ProgramFiles%\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat"
if not exist "%VCVARS%" set "VCVARS=%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat"
if not exist "%VCVARS%" (echo vcvars32.bat not found: install Visual Studio with the C++ workload & exit /b 1)
call "%VCVARS%" >nul || exit /b 1
:have_cl
set "SRC=%~dp0"
rem Placement sizes come from the game's own units.dat (see tools/gen_unit_dat.py).
python "%SRC%tools\gen_unit_dat.py" || exit /b 1
cmake -S "%SRC%." -B "%SRC%build" -G Ninja -DCMAKE_BUILD_TYPE=Release || exit /b 1
cmake --build "%SRC%build" || exit /b 1
echo Built %SRC%build\gary_scr.dll, %SRC%build\gary_scr_tests.exe, %SRC%build\scr_inject.exe

