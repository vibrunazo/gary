cmake_minimum_required(VERSION 3.16)
project(gary_resim CXX)

# OpenBW is used as an external dependency (not vendored; its repo has no license file).
# Clone it to external/openbw, or point OPENBW_DIR elsewhere.
set(OPENBW_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../external/openbw" CACHE PATH "OpenBW source checkout")
if(NOT EXISTS "${OPENBW_DIR}/bwgame.h")
  message(FATAL_ERROR "OpenBW not found at ${OPENBW_DIR}. Clone https://github.com/OpenBW/openbw there or set -DOPENBW_DIR=...")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_executable(gary_resim gary_resim.cpp)
target_include_directories(gary_resim PRIVATE "${OPENBW_DIR}")
if(MSVC)
  target_compile_options(gary_resim PRIVATE /bigobj /EHsc /W1)
  target_compile_definitions(gary_resim PRIVATE _CRT_SECURE_NO_WARNINGS NOMINMAX)
endif()

# Optional: extract_gamedata, for installs that store game data in CASC (StarCraft 1.23+).
# Needs CascLib (MIT) cloned to external/CascLib, or set CASCLIB_DIR.
set(CASCLIB_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../external/CascLib" CACHE PATH "CascLib source checkout")
if(EXISTS "${CASCLIB_DIR}/CMakeLists.txt")
  set(CMAKE_POLICY_VERSION_MINIMUM 3.5)  # CascLib still declares an old CMake minimum
  set(CASC_BUILD_SHARED_LIB OFF CACHE BOOL "" FORCE)
  set(CASC_BUILD_STATIC_LIB ON CACHE BOOL "" FORCE)
  add_subdirectory("${CASCLIB_DIR}" casclib EXCLUDE_FROM_ALL)
  add_executable(extract_gamedata extract_gamedata.cpp)
  target_link_libraries(extract_gamedata PRIVATE casc_static)
  target_include_directories(extract_gamedata PRIVATE "${CASCLIB_DIR}/src")
else()
  message(STATUS "CascLib not found at ${CASCLIB_DIR}: skipping extract_gamedata")
endif()
