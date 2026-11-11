# atelier/

Essais, firmwares de microcontrôleurs et scripts d'atelier — **jamais déployé** sur un Pi.

- `essais/` : bancs d'essai (ex `legacy/dadou_robot_ros/essais`, lot L1e-4e) — voix, etc.
- `firmware/` : firmwares du Pico d'odométrie, de la télécommande USB, etc. (ex `legacy/dadou_robot_ros/firmware`). La logique PURE des protocoles (`odom_protocol.py`, `remote_protocol.py`) est importée par les tests de `packages/didier_core` (`test/conftest.py` pose `atelier/firmware/*` dans `sys.path`).
- `outils/` : scripts d'atelier (étiqueteuse, relevé de Pi, schémas du banc témoin).
- `seances/` : traces brutes de séances.
