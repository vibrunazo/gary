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
