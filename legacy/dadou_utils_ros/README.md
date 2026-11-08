# Dadou Shared Utilities

> **La lib Python a déménagé (lot L1e-3a, 07/11)** : le code (`utils_static.py`, `misc.py`,
> `com/`, `lcd/`, `utils/`…) et ses tests sont maintenant le package ROS
> [`packages/dadou_utils_ros`](../../packages/dadou_utils_ros/README.md) du mono-dépôt.
> Ce dossier ne garde que l'outillage : `conf/`, `docs/`, `scripts/`, `makefile/` (lot L1e-4a,
> 08/11 : `ansible/` est devenu [`deploy/`](../../deploy/README.md) à la racine, `jenkins/` est supprimé). Les chemins `utils_static.py`, `tests/`, etc. cités plus bas sont à lire sous
> `packages/dadou_utils_ros/dadou_utils_ros/` et `packages/dadou_utils_ros/test/`.
> `.github/workflows/tests.yml` (CI de l'ancien dépôt autonome) est périmé : la CI mono-dépôt vient avec L2.

Common Python utilities, assets, and deployment tooling used by both the controller (`dadou_control_ros`) and the robot runtime (`dadou_robot_ros`).

## Documentation
- [`docs/README.md`](docs/README.md): documentation index.
- [`docs/modules.md`](docs/modules.md): overview of the shared Python packages.
- [`docs/deployment.md`](docs/deployment.md): Ansible playbooks, Makefile integration, and deployment workflow.
- [`docs/logging.md`](docs/logging.md): logging conventions and formatter details shared across repositories.

## Repository Layout
- `ansible/`: moved to `deploy/` at the mono-repo root (L1e-4a, 08/11).
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
