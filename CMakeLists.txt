# Minimum version of CMake required
cmake_minimum_required(VERSION 3.10)

# Project name and version
project(TimeStretchGrain VERSION 1.0)

# Set C++ standard to C++11
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Include the directory where our header files are located
include_directories(include)

# Add the executable by specifying source files
add_executable(time_stretch src/cpp/time_stretch.cpp)

# Optional: Add optimization flags (e.g., for release builds)
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    target_compile_options(time_stretch PRIVATE -O3)
endif()

# Optional: Add debug flags (e.g., for debug builds)
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    target_compile_options(time_stretch PRIVATE -g)
endif()

