cmake_minimum_required(VERSION 3.16)
project(gary_view CXX)

# OpenBW (no license file) and SDL2 (zlib) are external dependencies, not vendored.
set(OPENBW_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../external/openbw" CACHE PATH "OpenBW source checkout")
set(SDL2_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../external/sdl2/SDL2-2.32.10" CACHE PATH "SDL2 development package (VC)")
if(NOT EXISTS "${OPENBW_DIR}/ui/ui.h")
  message(FATAL_ERROR "OpenBW not found at ${OPENBW_DIR}")
endif()
if(NOT EXISTS "${SDL2_ROOT}/include/SDL.h")
  message(FATAL_ERROR "SDL2 not found at ${SDL2_ROOT} (unpack SDL2-devel-*-VC.zip into external/sdl2)")
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

add_executable(gary_view gary_view.cpp "${OPENBW_DIR}/ui/sdl2.cpp")
target_include_directories(gary_view PRIVATE "${OPENBW_DIR}" "${OPENBW_DIR}/ui" "${SDL2_ROOT}/include")
target_link_directories(gary_view PRIVATE "${SDL2_ROOT}/lib/x64")
target_link_libraries(gary_view PRIVATE SDL2 SDL2main)
target_compile_definitions(gary_view PRIVATE OPENBW_NO_SDL_IMAGE OPENBW_NO_SDL_MIXER OPENBW_ENABLE_UI
                           _CRT_SECURE_NO_WARNINGS NOMINMAX SDL_MAIN_HANDLED)
if(MSVC)
  # OpenBW headers use these without including them
  target_compile_options(gary_view PRIVATE /bigobj /EHsc /W1 /FIstdexcept /FIchrono /FIcmath /FIalgorithm)
  set_target_properties(gary_view PROPERTIES LINK_FLAGS "/SUBSYSTEM:CONSOLE")
endif()
add_custom_command(TARGET gary_view POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different "${SDL2_ROOT}/lib/x64/SDL2.dll" $<TARGET_FILE_DIR:gary_view>)
