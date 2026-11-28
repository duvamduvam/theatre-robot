# appareil_gabarit_core — README-contrat

Généré par `tools/nouvel_appareil.py appareil_gabarit` (gabarit : `packages/theatre_gabarit/README.md`).
Les 8 titres ci-dessous sont vérifiés par `theatre_gabarit.essais.verifier_appareil` : n'en
retirer aucun, remplir chaque trou APPAREIL.

## Rôle

APPAREIL : une phrase — ce que fait l'appareil pendant le spectacle.

## Machine

APPAREIL : où il tourne (hôte Ansible), lien vers [`machines/appareil_gabarit/`](../../machines/appareil_gabarit/).

## Topics

Relatifs, sous `/<ROBOT_NAME>/`, préfixés par `appareil_gabarit/`.

| Topic | Type | Sens | QoS | Constante de `theatre_contrats` |
|---|---|---|---|---|
| `appareil_gabarit/etat` | `StringTime` | sortie | latché | APPAREIL |
| `diagnostics` | `DiagnosticArray` | sortie, 1 Hz | fiable, 10 | — |

## Comportement

APPAREIL : règles numérotées (logique pure `logique.py`, horloge en argument).

## Pilotes

APPAREIL : ce que fait le pilote `sim`, ce que fait le pilote `materiel` (matériel, câblage).

## Simuler

APPAREIL : commande, ce qu'on voit sur la page scène (tuile « Appareils »).

## Tester

```bash
cd packages/appareil_gabarit_core && ../../.venv/bin/python -m pytest -q -o addopts=
```

APPAREIL : ce qui est gravé.

## Déployer

APPAREIL : commande Ansible, contrôle (`./ecart-pi.sh <groupe>`).
