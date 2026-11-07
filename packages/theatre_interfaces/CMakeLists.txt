cmake_minimum_required(VERSION 3.8)
project(theatre_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# En-têtes numpy FACULTATIFS — bloc repris de l'ancienne copie de la
# télécommande (ex-dadou_control_ros, avant le lot L1a),
# qui l'avait ajouté contre « fatal error: numpy/ndarrayobject.h: No such file
# or directory » au build de son image. Sans REQUIRED (lot L1a, copie unique) :
# les images sim/robot/vision qui n'ont pas les en-têtes de développement
# numpy compilent comme avant ; celle de la télécommande les trouve.
find_package(Python3 COMPONENTS Development NumPy)
if(Python3_NumPy_FOUND)
  include_directories(
    ${Python3_INCLUDE_DIRS}
    ${Python3_NumPy_INCLUDE_DIRS}
  )
endif()

rosidl_generate_interfaces(${PROJECT_NAME}
    "msg/StringTime.msg"
    "srv/SetLedPanel.srv"
    )
ament_package()
