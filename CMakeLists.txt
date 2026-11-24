cmake_minimum_required(VERSION 3.28)
include(evogine/src/evogine.cmake)
include(evogine/src/cmake.cmake)
set(APPLICATION_TARGET small-cap)
project(small-cap LANGUAGES C CXX)

set(PROJECT_ROOT_DIR ${CMAKE_CURRENT_LIST_DIR})
file(GLOB_RECURSE PROJECT_SOURCE_FILES "${CMAKE_CURRENT_LIST_DIR}/src/*.cpp")
file(GLOB_RECURSE PROJECT_HEADER_FILES "${CMAKE_CURRENT_LIST_DIR}/src/*.h")
add_executable(small-cap ${PROJECT_SOURCE_FILES} ${PROJECT_HEADER_FILES})
target_include_directories(small-cap PRIVATE "${CMAKE_CURRENT_LIST_DIR}/src/")

# Engine modules this game uses. Tiled/box2d are not needed: maps are Tiled JSON files that the
# game reads through the asset manager and collides against its own tile grid.
set(WINDOW_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(WINDOW_BACKEND sdl CACHE STRING "Set backend" FORCE)
set(INPUT_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(INPUT_BACKEND sdl CACHE STRING "Set backend" FORCE)
set(ECS_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(GRAPHICS_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(GRAPHICS_BACKEND opengl CACHE STRING "Set backend" FORCE)
set(RESOURCE_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(NLOHMANNJSON_EXTENSION_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(STB_EXTENSION_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(SDL_EXTENSION_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(UTILS_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(AUDIO_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(AUDIO_BACKEND miniaudio CACHE STRING "Set backend" FORCE)
set(OS_ENABLED ON CACHE BOOL "Enable feature" FORCE)
# The pinned engine revision does not compile its imgui pass (includes are disabled), and the
# game has no use for it.
set(IMGUI_ENABLED OFF CACHE BOOL "Enable feature" FORCE)
set(IMGUI_EXTENSION_ENABLED OFF CACHE BOOL "Enable feature" FORCE)
# Menus, dialog boxes and the HUD are RmlUi documents (resources/ui).
set(UI_ENABLED ON CACHE BOOL "Enable feature" FORCE)
set(UI_BACKEND rmlui CACHE STRING "Set backend" FORCE)

add_subdirectory(evogine/src engine_build)

target_link_libraries(small-cap PRIVATE evogine)
# RmlUi reads the UI documents straight from the file system: the preloaded /game mount on the
# web, the source tree natively.
if(EMSCRIPTEN)
    target_compile_definitions(small-cap PRIVATE RESOURCE_UI_DIR="/game/ui")
else()
    target_compile_definitions(small-cap PRIVATE RESOURCE_UI_DIR="${CMAKE_CURRENT_LIST_DIR}/resources/ui")
endif()
ADD_RESOURCE_PATH("game,${CMAKE_CURRENT_LIST_DIR}/resources")
GENERATE_RESOURCE_HEADER()
generate_components()
GENERATE_ECS_HEADER()

if(EMSCRIPTEN)
    foreach(resource_path_pair IN LISTS PHYSICAL_MOUNT_PATH_LIST)
        string(REPLACE "," ";" parts "${resource_path_pair}")
        list(GET parts 0 mount_name)
        list(GET parts 1 mount_path)
        target_link_options(small-cap PRIVATE
                "SHELL:--preload-file \"${mount_path}@/${mount_name}\""
        )
    endforeach()
    set_target_properties(small-cap PROPERTIES SUFFIX ".html")
    target_link_options(small-cap PRIVATE
            "-sMIN_WEBGL_VERSION=2"
            "-sMAX_WEBGL_VERSION=2"
            "-sALLOW_MEMORY_GROWTH=1"
            "SHELL:--shell-file ${CMAKE_CURRENT_LIST_DIR}/web/shell.html"
    )
    set_property(TARGET small-cap APPEND PROPERTY LINK_DEPENDS
            "${CMAKE_CURRENT_LIST_DIR}/web/shell.html"
    )
endif()
