cmake_minimum_required(VERSION 3.16)
project(gary_env CXX)

# OpenBW is used as an external dependency (not vendored); see resim/README.md.
set(OPENBW_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../external/openbw" CACHE PATH "OpenBW source checkout")
if(NOT EXISTS "${OPENBW_DIR}/bwgame.h")
  message(FATAL_ERROR "OpenBW not found at ${OPENBW_DIR}")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_library(gary_env SHARED gary_env.cpp)
target_include_directories(gary_env PRIVATE "${OPENBW_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/../resim")
if(MSVC)
  target_compile_options(gary_env PRIVATE /bigobj /EHsc /W1)
  target_compile_definitions(gary_env PRIVATE _CRT_SECURE_NO_WARNINGS NOMINMAX)
endif()
