"""Aucun lien Markdown relatif mort dans le dépôt (lot L1e-4e, 11/11).

Pourquoi : la doc a déménagé de legacy/dadou_robot_ros/docs/ vers docs/ ; sans garde-fou, chaque
déménagement suivant (L2, L4, L5) casserait des liens sans que personne ne le voie. Le test
parcourt les fichiers .md SUIVIS par git (+ les nouveaux non ignorés), extrait `[texte](cible)`
et `![alt](cible)`, et exige que la cible relative existe. Ignorés : les URL (`http:`, `mailto:`…),
les ancres seules (`#…`), les blocs de code et le code en ligne (exemples, pas des liens).
Les ancres `fichier.md#section` ne sont pas vérifiées : seul le fichier l'est.

Le détecteur est lui-même testé sur de FAUX dépôts (valeurs gravées) : un détecteur qui ne verrait
jamais rien ferait passer le test du dépôt à vide.
"""
import pathlib
import re
import subprocess

MONO = pathlib.Path(__file__).resolve().parents[4]

_LIEN = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_SCHEMA = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


def _liens(texte):
    """Cibles des liens Markdown de `texte`, hors blocs de code et code en ligne."""
    texte = re.sub(r"```.*?```", "", texte, flags=re.S)
    texte = re.sub(r"`[^`\n]*`", "", texte)
    return _LIEN.findall(texte)


def liens_morts(racine, fichiers):
    """[(fichier, cible)] des liens relatifs de `fichiers` (chemins relatifs à `racine`) sans cible."""
    morts = []
    for f in fichiers:
        chemin = racine / f
        if not chemin.is_file():
            continue
        for cible in _liens(chemin.read_text(encoding="utf-8", errors="replace")):
            if _SCHEMA.match(cible) or cible.startswith("#"):
                continue
            cible = cible.split("#")[0].split("?")[0]
            if not cible:
                continue
            # Une cible HORS du dépôt est morte aussi : sur le PC de David, ../../dadou_vision_ros
            # existe (les anciens dépôts archivés à côté) et le test passait — pas sur GitHub
            # (CI rouge du 11/11 au soir).
            vise = (chemin.parent / cible).resolve()
            if not vise.is_relative_to(racine.resolve()) or not vise.exists():
                morts.append((f, cible))
    return morts


def _fichiers_md():
    sortie = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
                            cwd=MONO, capture_output=True, text=True, check=True, timeout=60).stdout
    return [f for f in sortie.splitlines() if f]


def test_le_detecteur_voit_les_liens_morts_et_ignore_le_reste(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "vivant.md").write_text("ok", encoding="utf-8")
    (tmp_path / "docs" / "page.md").write_text(
        "[bon](vivant.md) [bon ancre](vivant.md#x) ![img](vivant.md)\n"
        "[mort](absent.md) [mort ancre](absent2.md#y) ![img morte](pics/absente.png)\n"
        "[web](https://exemple.org/x) [mail](mailto:a@b.c) [ancre seule](#haut)\n"
        "`[code](inexistant-1.md)`\n```\n[bloc](inexistant-2.md)\n```\n", encoding="utf-8")
    assert liens_morts(tmp_path, ["docs/page.md"]) == [
        ("docs/page.md", "absent.md"), ("docs/page.md", "absent2.md"),
        ("docs/page.md", "pics/absente.png")]


def test_le_depot_n_a_aucun_lien_markdown_mort():
    fichiers = _fichiers_md()
    # Garde-fou : un git ls-files vide (mauvais cwd, dépôt sans .git) ferait passer le test à vide.
    assert len(fichiers) > 100
    assert "docs/README.md" in fichiers and "docs/chantiers.md" in fichiers
    assert liens_morts(MONO, fichiers) == []


def test_un_lien_qui_sort_du_depot_est_mort_meme_si_la_cible_existe(tmp_path):
    """Gravé après la CI rouge du 11/11 : la cible existait à côté du dépôt sur le PC, pas sur GitHub."""
    depot = tmp_path / "depot"
    (depot / "docs").mkdir(parents=True)
    (tmp_path / "voisin.md").write_text("x", encoding="utf-8")         # existe, mais HORS du dépôt
    (depot / "docs" / "a.md").write_text("[v](../../voisin.md) [ok](a.md)", encoding="utf-8")
    assert liens_morts(depot, ["docs/a.md"]) == [("docs/a.md", "../../voisin.md")]
