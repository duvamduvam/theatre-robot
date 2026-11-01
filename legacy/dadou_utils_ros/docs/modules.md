# Shared Modules Overview

## `dadou_utils_ros.utils_static`
Centralises string constants and enums shared by the controller and robot repositories (e.g., button identifiers, ROS topic names, configuration keys). Keep it up to date when introducing new device inputs or command types.

## `dadou_utils_ros.logging_conf`
Provides the logging configuration factory used across all repos. The custom log-record factory automatically injects the Python class name into log entries, improving backstage debugging.

## `dadou_utils_ros.com`
Serial and message-queue helpers used by both the glove controller (RP2040) and robot components.

## `dadou_utils_ros.files`
File utilities for reading/writing JSON configuration, handling playlist assets, and general file management.

## `dadou_utils_ros.utils.time_utils`
Time helpers used for scheduling sequences, computing durations, and throttling operations.

## Additional Assets
- `fonts/`, `audios/`, `lcd/`: Resource bundles that may be copied to devices during deployment.
- `tests/`: Validation utilities for the shared modules.

When extending these helpers, document the new functionality here and add automated tests covering both controller and robot use cases.
