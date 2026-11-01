#!/usr/bin/env bash

# Simplified CI orchestrator: provision the remote test runner with Ansible
# (install-pios-full) and run the test command on that host. Jenkins only
# orchestrates; it no longer builds Docker images or executes tests locally.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"

INVENTORY="${INVENTORY:-${REPO_ROOT}/ansible/hosts}"
PROVISION_PLAYBOOK="${PROVISION_PLAYBOOK:-${REPO_ROOT}/ansible/install-pios-full.yml}"
TARGET_GROUP="${TARGET_GROUP:-robot-test}"
TEST_COMMAND="${TEST_COMMAND:-}"
ANSIBLE_ARGS="${ANSIBLE_ARGS:-}"
SKIP_PROVISION="${SKIP_PROVISION:-}"

# Global array populated by parse_ansible_args.
ANSIBLE_ARGS_ARR=()

require_command() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    printf "Missing required command: %s\n" "${cmd}" >&2
    exit 1
  fi
}

parse_ansible_args() {
  if [[ -n "${ANSIBLE_ARGS}" ]]; then
    # shellcheck disable=SC2206 # Intentional split on whitespace for ansible args.
    ANSIBLE_ARGS_ARR=( ${ANSIBLE_ARGS} )
  else
    ANSIBLE_ARGS_ARR=()
  fi
}

validate_inputs() {
  if [[ ! -f "${INVENTORY}" ]]; then
    printf "Inventory not found: %s\n" "${INVENTORY}" >&2
    exit 1
  fi
  if [[ ! -f "${PROVISION_PLAYBOOK}" ]]; then
    printf "Provisioning playbook not found: %s\n" "${PROVISION_PLAYBOOK}" >&2
    exit 1
  fi
  if [[ -z "${TEST_COMMAND}" ]]; then
    printf "TEST_COMMAND must be provided (command executed on the test runner).\n" >&2
    exit 1
  fi
}

provision_test_runner() {
  if [[ -n "${SKIP_PROVISION}" ]]; then
    echo "[CI][1/2] Provisioning skipped (SKIP_PROVISION set)."
    return
  fi

  echo "[CI][1/2] Provisioning target group '${TARGET_GROUP}' via ${PROVISION_PLAYBOOK}..."
  ansible-playbook -i "${INVENTORY}" "${PROVISION_PLAYBOOK}" \
    --extra-vars "target_group=${TARGET_GROUP}" \
    "${ANSIBLE_ARGS_ARR[@]}"
  echo "[CI][1/2] Provisioning completed."
}

run_remote_tests() {
  echo "[CI][2/2] Running tests on '${TARGET_GROUP}'..."
  ansible -i "${INVENTORY}" "${TARGET_GROUP}" \
    -m ansible.builtin.shell \
    -a "${TEST_COMMAND}" \
    "${ANSIBLE_ARGS_ARR[@]}"
  echo "[CI][2/2] Tests finished on '${TARGET_GROUP}'."
}

main() {
  require_command ansible
  require_command ansible-playbook
  parse_ansible_args
  validate_inputs
  provision_test_runner
  run_remote_tests
}

main "$@"
