cmake_minimum_required(VERSION 3.13 FATAL_ERROR)

if("${CMAKE_SOURCE_DIR}" STREQUAL "${CMAKE_BINARY_DIR}")
    set(MSG "")
    message(STATUS "Warning! Building from the source directory is not recommended")
    message(STATUS "If unintented, please remove 'CMakeCache.txt' and 'CMakeFiles'")
    message(STATUS "and build from a separate directory")
    message(WARNING "In-source build")
endif()

#----------------------------------------------------------------------------------------#
#   policies
#----------------------------------------------------------------------------------------#

cmake_policy(SET CMP0010 NEW)
cmake_policy(SET CMP0022 NEW)
cmake_policy(SET CMP0048 NEW)
cmake_policy(SET CMP0042 NEW)
cmake_policy(SET CMP0053 NEW)
cmake_policy(SET CMP0063 NEW)
cmake_policy(SET CMP0077 NEW)
cmake_policy(SET CMP0079 NEW)

if("${CMAKE_BUILD_TYPE}" STREQUAL "")
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()

#----------------------------------------------------------------------------------------#
#   versioning
#----------------------------------------------------------------------------------------#

file(READ "${CMAKE_CURRENT_LIST_DIR}/VERSION" FULL_VERSION_STRING LIMIT_COUNT 1)
string(REGEX REPLACE "(\n|\r)" "" FULL_VERSION_STRING "${FULL_VERSION_STRING}")
string(REGEX REPLACE "[A-Za-z].*" "" VERSION_STRING "${FULL_VERSION_STRING}")
set(COMPILE_TIME_PERF_VERSION "${VERSION_STRING}")
message(STATUS "compile-time-perf version ${COMPILE_TIME_PERF_VERSION} (${FULL_VERSION_STRING})")

#----------------------------------------------------------------------------------------#
#   project
#----------------------------------------------------------------------------------------#

project(compile-time-perf
        VERSION         ${COMPILE_TIME_PERF_VERSION}
        DESCRIPTION     "Measures high-level timing and memory usage metrics during compilation"
        HOMEPAGE_URL    "https://github.com/jrmadsen/compile-time-perf"
        LANGUAGES       CXX)

include(GNUInstallDirs)
set(CMAKE_MODULE_PATH        ${PROJECT_SOURCE_DIR}/cmake/Modules ${CMAKE_MODULE_PATH})
set(CMAKE_INSTALL_CONFIGDIR  ${CMAKE_INSTALL_DATAROOTDIR}/cmake/${PROJECT_NAME})

#----------------------------------------------------------------------------------------#
#   various cache settings
#----------------------------------------------------------------------------------------#

set(CMAKE_CXX_STANDARD          14  CACHE STRING "C++ language standard")
set(CMAKE_CXX_EXTENSIONS        OFF CACHE BOOL "C++ language extensions")
set(CMAKE_CXX_STANDARD_REQUIRED ON)

#----------------------------------------------------------------------------------------#
#   configure submodule
#----------------------------------------------------------------------------------------#

set(TIMEMORY_INSTALL_HEADERS        OFF CACHE BOOL "Disable timemory header install" FORCE)
set(TIMEMORY_INSTALL_CONFIG         OFF CACHE BOOL "Disable timemory cmake configuration install" FORCE)
set(TIMEMORY_INSTALL_ALL            OFF CACHE BOOL "Disable install target depending on all target" FORCE)
set(TIMEMORY_BUILD_TOOLS            OFF CACHE BOOL "Ensure timem executable is built" FORCE)
set(TIMEMORY_BUILD_TIMEM            ON  CACHE BOOL "Ensure timem executable is built" FORCE)
set(TIMEMORY_BUILD_EXCLUDE_FROM_ALL ON  CACHE BOOL "Set timemory to only build dependencies" FORCE)
set(TIMEMORY_QUIET_CONFIG           ON  CACHE BOOL "Make timemory configuration quieter" FORCE)

include(Utilities)

ctp_checkout_git_submodule(
    RELATIVE_PATH       source/timemory
    WORKING_DIRECTORY   ${PROJECT_SOURCE_DIR}
    REPO_URL            https://github.com/NERSC/timemory.git
    REPO_BRANCH         develop)

add_subdirectory(source/timemory)

#----------------------------------------------------------------------------------------#
#   build target
#----------------------------------------------------------------------------------------#

add_custom_target(compile-time-perf ALL
    ${CMAKE_COMMAND} -E touch ${PROJECT_SOURCE_DIR}/source/compile-time-perf.cpp
    COMMENT "Building timem executable..."
    DEPENDS timem)

configure_file(${PROJECT_SOURCE_DIR}/source/compile-time-perf-analyzer.py
    ${PROJECT_BINARY_DIR}/compile-time-perf-analyzer COPYONLY)

install(
    PROGRAMS    ${PROJECT_BINARY_DIR}/compile-time-perf-analyzer
    DESTINATION ${CMAKE_INSTALL_BINDIR})

find_package(Python3 REQUIRED COMPONENTS Interpreter)

#----------------------------------------------------------------------------------------#
#   packaging
#----------------------------------------------------------------------------------------#

include(CMakePackageConfigHelpers)

set(BIN_INSTALL_DIR ${CMAKE_INSTALL_BINDIR})

configure_package_config_file(
    ${PROJECT_SOURCE_DIR}/cmake/Templates/compile-time-perf-config.cmake.in
    ${PROJECT_BINARY_DIR}/compile-time-perf-config.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_CONFIGDIR}
    INSTALL_PREFIX      ${CMAKE_INSTALL_PREFIX}
    PATH_VARS           BIN_INSTALL_DIR)

write_basic_package_version_file(
    ${PROJECT_BINARY_DIR}/compile-time-perf-config-version.cmake
    VERSION         ${PROJECT_VERSION}
    COMPATIBILITY   SameMajorVersion)

install(
    FILES
        ${PROJECT_BINARY_DIR}/compile-time-perf-config.cmake
        ${PROJECT_BINARY_DIR}/compile-time-perf-config-version.cmake
    DESTINATION
        ${CMAKE_INSTALL_CONFIGDIR})

export(PACKAGE compile-time-perf)
