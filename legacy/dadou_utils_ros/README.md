# Dadou Shared Utilities

Common Python utilities, assets, and deployment tooling used by both the controller (`dadou_control_ros`) and the robot runtime (`dadou_robot_ros`).

## Documentation
- [`docs/README.md`](docs/README.md): documentation index.
- [`docs/modules.md`](docs/modules.md): overview of the shared Python packages.
- [`docs/deployment.md`](docs/deployment.md): Ansible playbooks, Makefile integration, and deployment workflow.
- [`docs/logging.md`](docs/logging.md): logging conventions and formatter details shared across repositories.

## Repository Layout
- `ansible/`: deployment playbooks, roles, templates.
- `utils_static.py`, `logging_conf.py`, `misc.py`: core modules imported by the other repositories.
- `com/`, `files/`, `utils/`: communication and helper packages.
- `tests/`: unit tests for the utilities.

## Quick Start
```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt  # if/when a requirements file is added
```

## Contributing
- Update documentation when adding new shared helpers.
- Ensure backward compatibility for existing imports (`dadou_control_ros`, `dadou_robot_ros`).

## License
To be defined by the project owner.
