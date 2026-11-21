cmake_minimum_required(VERSION 3.8)
project(didier_sim)

find_package(ament_cmake REQUIRED)
# relais_horloge (21/11) : /clock gz -> ROS décimé (src/relais_horloge.cpp). FACULTATIF : construit
# seulement là où gz-transport et gz-msgs (paquets « vendor » de Jazzy, comme pour ros_gz_bridge)
# sont installés, c'est-à-dire dans le conteneur monde. didier_sim est aussi construit par le
# conteneur robot et sur le Pi (machines/robot/machine.yml), qui n'ont pas Gazebo et n'en ont pas
# besoin. Monde sans relais : monde.launch.py échoue au lancement, bruyamment.
find_package(gz_transport_vendor QUIET)
find_package(gz_msgs_vendor QUIET)
if(gz_transport_vendor_FOUND AND gz_msgs_vendor_FOUND)
  find_package(rclcpp REQUIRED)
  find_package(rosgraph_msgs REQUIRED)
  find_package(gz-transport REQUIRED)
  find_package(gz-msgs REQUIRED)
  add_executable(relais_horloge src/relais_horloge.cpp)
  target_compile_features(relais_horloge PRIVATE cxx_std_17)
  target_compile_options(relais_horloge PRIVATE -Wall -Wextra -Wpedantic)
  target_link_libraries(relais_horloge
    rclcpp::rclcpp ${rosgraph_msgs_TARGETS} gz-transport::core gz-msgs::core)
  install(TARGETS relais_horloge DESTINATION lib/${PROJECT_NAME})
else()
  message(STATUS "didier_sim : gz-transport absent, relais_horloge non construit (normal hors conteneur monde)")
endif()

install(DIRECTORY launch worlds config DESTINATION share/${PROJECT_NAME})

# leds_sim_node / servos_sim_node / passant_sim_node : scripts Python + leur lib pure commune
# didier_sim_lib installés côte à côte dans lib/didier_sim/ (pas de mécanisme
# ament_python ici, didier_sim est ament_cmake). Chaque script fait un
# sys.path.insert(dirname(__file__)) pour importer didier_sim_lib comme un
# module frère -- voir scripts/leds_sim_node et scripts/servos_sim_node.
install(PROGRAMS scripts/leds_sim_node scripts/servos_sim_node scripts/passant_sim_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY didier_sim_lib DESTINATION lib/${PROJECT_NAME}
        PATTERN "__pycache__" EXCLUDE)

ament_package()
