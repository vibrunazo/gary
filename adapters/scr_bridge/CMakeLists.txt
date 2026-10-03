cmake_minimum_required(VERSION 3.16)
project(gary_scr CXX)

# The in-process SC:R adapter (see README.md). Builds 32-bit because the pinned target is the
# x86 client; build.bat calls vcvars32 before configuring.
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_library(gary_scr SHARED
  src/bridge.cpp
  src/commands.cpp
  src/observe.cpp
  src/pipe_server.cpp
)
target_include_directories(gary_scr PRIVATE src)
target_link_libraries(gary_scr bcrypt)
if(MSVC)
  target_compile_options(gary_scr PRIVATE /EHsc /W3)
  target_compile_definitions(gary_scr PRIVATE _CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
endif()

add_executable(gary_scr_tests
  src/tests_main.cpp
  src/commands.cpp
  src/pipe_server.cpp
)
target_include_directories(gary_scr_tests PRIVATE src)
if(MSVC)
  target_compile_options(gary_scr_tests PRIVATE /EHsc /W3)
  target_compile_definitions(gary_scr_tests PRIVATE _CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
endif()

add_executable(scr_inject src/injector_main.cpp)
if(MSVC)
  target_compile_options(scr_inject PRIVATE /EHsc /W3)
  target_compile_definitions(scr_inject PRIVATE _CRT_SECURE_NO_WARNINGS NOMINMAX WIN32_LEAN_AND_MEAN)
endif()
