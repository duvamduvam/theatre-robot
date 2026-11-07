cmake_minimum_required(VERSION 3.8)
project(didier_sim)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch worlds config DESTINATION share/${PROJECT_NAME})

# leds_sim_node / servos_sim_node : scripts Python + leur lib pure commune
# didier_sim_lib installés côte à côte dans lib/didier_sim/ (pas de mécanisme
# ament_python ici, didier_sim est ament_cmake). Chaque script fait un
# sys.path.insert(dirname(__file__)) pour importer didier_sim_lib comme un
# module frère -- voir scripts/leds_sim_node et scripts/servos_sim_node.
install(PROGRAMS scripts/leds_sim_node scripts/servos_sim_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY didier_sim_lib DESTINATION lib/${PROJECT_NAME}
        PATTERN "__pycache__" EXCLUDE)

ament_package()
