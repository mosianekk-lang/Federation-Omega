cmake_minimum_required(VERSION 3.21)
project(FUSE_LocalLLM_Desktop VERSION 0.2.2 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_CURL OFF CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(llama_cpp
  GIT_REPOSITORY https://github.com/ggml-org/llama.cpp.git
  GIT_TAG 60081bb2b5b3294165a4d67c5cbeebe74c868014
  GIT_SHALLOW FALSE)
FetchContent_MakeAvailable(llama_cpp)

add_executable(FUSE-LocalLLM src/main.cpp src/fuse_core.cpp)
target_include_directories(FUSE-LocalLLM PRIVATE include)
target_link_libraries(FUSE-LocalLLM PRIVATE llama)
if(WIN32)
  target_link_libraries(FUSE-LocalLLM PRIVATE ws2_32 shell32)
  add_executable(FUSE-LocalLLM-Desktop WIN32 src/desktop_launcher.cpp)
  target_link_libraries(FUSE-LocalLLM-Desktop PRIVATE shell32)
endif()
