cmake_minimum_required(VERSION 3.8)
project(robot_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

### Fix fatal error: numpy/ndarrayobject.h: No such file or directory
find_package(Python3 REQUIRED COMPONENTS Development NumPy)
# Ajoute le chemin des headers numpy
include_directories(
  ${Python3_INCLUDE_DIRS}
  ${Python3_NumPy_INCLUDE_DIRS}
)

rosidl_generate_interfaces(${PROJECT_NAME}
    "msg/StringTime.msg"
    "srv/SetLedPanel.srv"
    )
ament_package()
