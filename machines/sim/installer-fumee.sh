#!/bin/bash
# Installe (ou retire, avec --desinstaller) la minuterie systemd UTILISATEUR de la fumée
# nocturne (lot F). Sans sudo : tout vit dans ~/.config/systemd/user/.
#   ./installer-fumee.sh                 copie les unités, active la minuterie
#   ./installer-fumee.sh --desinstaller  arrête, désactive et supprime les unités
# Le chemin de fumee.sh est celui du checkout d'où l'on lance l'installeur : relancer
# l'installeur depuis le checkout de main une fois le lot fusionné (un worktree peut disparaître).
# Ne modifie rien d'autre ; l'état et le journal restent dans ~/.local/state/didier-fumee/.
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# L1e-4c (11/11) : fumee.sh et ce script vivent côte à côte dans machines/sim/.
FUMEE_SH="$ICI/fumee.sh"
DEST="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [ "${1:-}" = "--desinstaller" ]; then
  systemctl --user disable --now didier-fumee.timer 2>/dev/null || true
  rm -f "$DEST/didier-fumee.service" "$DEST/didier-fumee.timer"
  systemctl --user daemon-reload
  echo "minuterie didier-fumee désinstallée (journal conservé dans ~/.local/state/didier-fumee/)"
  exit 0
fi
[ -x "$FUMEE_SH" ] || { echo "fumee.sh introuvable ou non exécutable : $FUMEE_SH" >&2; exit 2; }

mkdir -p "$DEST"
sed "s|@FUMEE_SH@|$FUMEE_SH|g" "$ICI/didier-fumee.service" >"$DEST/didier-fumee.service"
cp "$ICI/didier-fumee.timer" "$DEST/didier-fumee.timer"
systemctl --user daemon-reload
systemctl --user enable --now didier-fumee.timer
echo "installé : ExecStart=$FUMEE_SH --si-due, toutes les 30 min"
systemctl --user list-timers didier-fumee.timer --no-pager
