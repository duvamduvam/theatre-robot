# dadou — mono-dépôt du système Didier (CLAUDE.md unique)

Lot L0 en cours (2026-11-02) : les anciens dépôts vivent dans `legacy/`, **tels quels**, avec
leurs propres `CLAUDE.md` qui restent la référence pour travailler dans leur code :
`legacy/dadou_robot_ros/CLAUDE.md` (règles de sécurité roues, commandes sim, priorités).
Ce fichier-ci grossira à mesure que `legacy/` se vide ; il ne doit jamais dupliquer ce que
`README.md` (la carte) et `docs/` disent.

## Règles qui valent dès maintenant pour TOUT le dépôt

- Sécurité roues : celles de `legacy/dadou_robot_ros/CLAUDE.md`, sans exception.
- Toute proposition de déplacement dit ce qu'elle SUPPRIME ; la sim doit marcher en fin de lot.
- Noms de packages : `didier_*` / `<appareil>_*` / `dadou_*` ; noms de topics **relatifs**
  (namespace par robot), jamais absolus.
- Documentation dans le même lot que le code ; état des chantiers dans `docs/chantiers.md`
  (encore dans `legacy/dadou_robot_ros/docs/` pendant L0).
- Dépôt public : aucun secret, jamais (les secrets vivent hors git, voir l'étude architecture).
