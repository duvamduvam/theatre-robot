# Logging Reference

## Overview
All three repositories use the shared logging factory defined in `dadou_utils_ros.logging_conf`. The factory overrides Python's `LogRecord` creation to inject the class name (`record.classname`) into the log output format.

### Formatter Example
```
%(asctime)s controller_node USBGamepad |%(lineno)s: %(levelname)s %(message)s
```

## Usage Pattern
```
from dadou_utils_ros.logging_conf import LoggingConf
logging.config.dictConfig(LoggingConf.get(log_file_path, process_name))
```

- `log_file_path`: defined in repository-specific config (`controller/control_config.py`, `robot/robot_config.py`).
- `process_name`: typically the ROS node name (`audio_node`, `wheels_node`, etc.).

## Tips
- Call `_ensure_classname_factory()` once per process (done automatically by `LoggingConf`).
- When writing new modules, avoid configuring logging manually—reuse the shared configuration to keep output consistent during rehearsals.
- Use structured messages (dicts or key=value) when possible to simplify filtering backstage.

## Troubleshooting
- If class names do not appear in logs, ensure `dadou_utils_ros` is up to date on the target device.
- Mixing other logging configurations (e.g., third-party libraries) may reset the factory. Re-run the `LoggingConf` initialisation after such libraries are configured.

Related documentation: check `dadou_control_ros/docs/testing.md` and `dadou_robot_ros/docs/operations.md` for log locations.
