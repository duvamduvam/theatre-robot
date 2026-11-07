#!/usr/bin/env python3
"""Imprime des étiquettes sur l'étiqueteuse Bluetooth Marklife P15 de l'atelier.

Pourquoi un script maison : bleak échoue avec cette imprimante (BlueZ tente le
Bluetooth classique), alors que gatttool en BLE public marche. Protocole « L11 »
(dépôt GitHub tomLadder/thermoprint), calage mesuré le 2026-10-04 :

- tête de 384 points, rouleau 40 × 12 mm ; l'étiquette est CENTRÉE sur la tête ;
- on dessine 320 × 96 points, on tourne de 90°, on pose aux colonnes 144-239 ;
- envoi par paquets de 95 octets, au rythme des crédits notifiés sur ff03
  (« 01 NN » ajoute NN crédits : 01 04 à la connexion, puis 01 01 par paquet) ;
- négocier le MTU (« mtu 247 ») : sinon gatttool tronque chaque paquet à 20 octets ;
- enchaîner les étiquettes cale l'imprimante : une connexion neuve et 15 s de
  pause par étiquette.

Usage :
    etiqueteuse_p15.py "Pi 4 · 4 Go" "n° 365ba865"     # une étiquette, 1 à 3 lignes
    etiqueteuse_p15.py --apercu essai.png "TEST"       # image seule, rien n'est imprimé
"""

from __future__ import annotations

import argparse
import queue
import re
import subprocess
import sys
import threading
import time

from PIL import Image, ImageDraw, ImageFont

ADRESSE = "03:17:63:2A:22:3C"  # P15_223B_BLE
POIGNEE_ECRITURE = 0x0011  # caractéristique ff02
POIGNEE_OK = 0x000E  # notifications ff01 : « OK » en fin d'impression
POIGNEE_CREDITS = 0x0013  # notifications ff03 : « 01 NN » = NN crédits
LARGEUR_TETE = 384
LONGUEUR, HAUTEUR = 320, 96  # étiquette 40 × 12 mm à 8 points/mm
COLONNE_DEBUT = 144
TAILLE_PAQUET = 95
POLICE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
PAUSE_ENTRE_ETIQUETTES_S = 15
TRACE = False  # --trace : affiche tout ce que répond gatttool


def dessiner(lignes: list[str]) -> Image.Image:
    """Dessine 1 à 3 lignes centrées, à la plus grande taille qui tient."""
    image = Image.new("1", (LONGUEUR, HAUTEUR), 1)
    dessin = ImageDraw.Draw(image)
    marge = 4
    hauteur_ligne = (HAUTEUR - 2 * marge) // len(lignes)
    for taille in range(hauteur_ligne, 8, -1):
        police = ImageFont.truetype(POLICE, taille)
        largeurs = [dessin.textlength(l, font=police) for l in lignes]
        if max(largeurs) <= LONGUEUR - 2 * marge:
            break
    for i, ligne in enumerate(lignes):
        boite = dessin.textbbox((0, 0), ligne, font=police)
        x = (LONGUEUR - (boite[2] - boite[0])) / 2 - boite[0]
        y = marge + i * hauteur_ligne + (hauteur_ligne - (boite[3] - boite[1])) / 2 - boite[1]
        dessin.text((x, y), ligne, font=police, fill=0)
    return image


def raster(image: Image.Image) -> bytes:
    """Tourne l'étiquette et la pose sur la tête : 1 bit par point, 1 = noir, MSB d'abord."""
    tournee = image.rotate(90, expand=True)  # 96 de large × 320 lignes
    pleine = Image.new("1", (LARGEUR_TETE, tournee.height), 1)
    pleine.paste(tournee, (COLONNE_DEBUT, 0))
    octets = bytearray()
    for y in range(pleine.height):
        for x0 in range(0, LARGEUR_TETE, 8):
            octet = 0
            for b in range(8):
                if pleine.getpixel((x0 + b, y)) == 0:
                    octet |= 0x80 >> b
            octets.append(octet)
    return bytes(octets)


def trames(image: Image.Image) -> tuple[bytes, bytes]:
    """Préparation puis image, dans l'ordre de thermoprint (profil P15, protocole L11).

    La préparation (épaisseur, réveil, mise en route) part seule ; on attend que
    l'imprimante rende des crédits avant d'envoyer l'image et la fin.
    """
    donnees = raster(image)
    largeur_octets = LARGEUR_TETE // 8
    lignes = len(donnees) // largeur_octets
    preparation = bytes.fromhex("10FF100002") + bytes(15) + bytes.fromhex("10FFF102")
    image_et_fin = (
        bytes([0x1D, 0x76, 0x30, 0x00, largeur_octets & 0xFF, largeur_octets >> 8,
               lignes & 0xFF, lignes >> 8])
        + donnees
        + bytes.fromhex("1D0C")  # avance jusqu'à l'espace entre étiquettes
        + bytes.fromhex("10FFF145")  # fin de session
    )
    return preparation, image_et_fin


class Gatttool:
    """Session gatttool interactive : écrit des commandes, lit les notifications."""

    def __init__(self, adresse: str) -> None:
        self.proc = subprocess.Popen(
            ["gatttool", "-b", adresse, "-t", "public", "-I"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        self.lignes: queue.Queue[str] = queue.Queue()
        self.credits = 0
        self.dernier_credit = time.monotonic()
        threading.Thread(target=self._lire, daemon=True).start()

    def _lire(self) -> None:
        for ligne in self.proc.stdout:  # type: ignore[union-attr]
            if TRACE:
                print("<", ligne.rstrip()[-80:], file=sys.stderr)
            # « 01 NN » sur ff03 ajoute NN crédits (01 04 à la connexion, puis 01 01 par paquet)
            credit = re.search(rf"handle = 0x{POIGNEE_CREDITS:04x} value: 01 ([0-9a-f]{{2}})", ligne)
            if credit:
                self.credits += int(credit.group(1), 16)
                self.dernier_credit = time.monotonic()
            self.lignes.put(ligne)

    def envoyer(self, texte: str) -> None:
        self.proc.stdin.write(texte + "\n")  # type: ignore[union-attr]
        self.proc.stdin.flush()  # type: ignore[union-attr]

    def attendre(self, motif: str, delai_s: float) -> str | None:
        fin = time.monotonic() + delai_s
        while time.monotonic() < fin:
            try:
                ligne = self.lignes.get(timeout=0.05)
            except queue.Empty:
                continue
            if re.search(motif, ligne):
                return ligne
        return None

    def fermer(self) -> None:
        try:
            self.envoyer("disconnect")
            self.envoyer("exit")
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


def envoyer_au_credit(session: Gatttool, donnees: bytes) -> None:
    """Un paquet toutes les 30 ms s'il reste un crédit ; après 2 s sans crédit, on en force un
    (reprise de l'application officielle, reprise par thermoprint)."""
    for debut in range(0, len(donnees), TAILLE_PAQUET):
        while session.credits <= 0:
            if time.monotonic() - session.dernier_credit > 2:
                session.credits, session.dernier_credit = 1, time.monotonic()
            time.sleep(0.01)
        paquet = donnees[debut:debut + TAILLE_PAQUET]
        session.envoyer(f"char-write-cmd 0x{POIGNEE_ECRITURE:04x} {paquet.hex()}")
        session.credits -= 1
        time.sleep(0.03)


def imprimer(image: Image.Image) -> bool:
    """Envoie une étiquette sur une connexion neuve ; vrai si l'imprimante répond « OK »."""
    session = Gatttool(ADRESSE)
    try:
        session.envoyer("connect")
        if session.attendre(r"Connection successful", 20) is None:
            print("Connexion BLE impossible (imprimante éteinte ou en veille ?)", file=sys.stderr)
            return False
        # Sans négociation, gatttool reste à l'ATT MTU de 23 et TRONQUE en silence chaque
        # écriture à 20 octets : les requêtes courtes passent, l'image arrive en miettes et
        # rien ne s'imprime (vécu le 07/11). L'imprimante annonce 220 (« 02 dc 00 »).
        session.envoyer("mtu 247")
        if session.attendre(r"MTU was exchanged successfully", 5) is None:
            print("Négociation MTU refusée : les paquets de 95 octets seraient tronqués",
                  file=sys.stderr)
            return False
        for poignee in (POIGNEE_OK, POIGNEE_CREDITS):  # active les notifications (CCCD = +1)
            session.envoyer(f"char-write-req 0x{poignee + 1:04x} 0100")
            session.attendre(r"written successfully", 3)
        preparation, image_et_fin = trames(image)
        envoyer_au_credit(session, preparation)
        fin = time.monotonic() + 1  # comme thermoprint : jusqu'à 1 s pour retrouver 3 crédits
        while session.credits < 3 and time.monotonic() < fin:
            time.sleep(0.01)
        envoyer_au_credit(session, image_et_fin)
        ok = session.attendre(rf"handle = 0x{POIGNEE_OK:04x} value: .*4f 4b", 20)
        if ok is None:
            print("Trame envoyée mais pas de « OK » de l'imprimante", file=sys.stderr)
        return ok is not None
    finally:
        session.fermer()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("lignes", nargs="+", help="1 à 3 lignes de texte (une étiquette)")
    parser.add_argument("--apercu", metavar="PNG", help="écrit l'image au lieu d'imprimer")
    parser.add_argument("--copies", type=int, default=1)
    parser.add_argument("--trace", action="store_true", help="affiche les réponses BLE")
    args = parser.parse_args()
    global TRACE
    TRACE = args.trace
    if not 1 <= len(args.lignes) <= 3:
        parser.error("1 à 3 lignes par étiquette")
    image = dessiner(args.lignes)
    if args.apercu:
        image.save(args.apercu)
        print(f"Aperçu écrit : {args.apercu}")
        return 0
    for n in range(args.copies):
        if n:
            time.sleep(PAUSE_ENTRE_ETIQUETTES_S)
        if not imprimer(image):
            return 1
        print(f"Étiquette {n + 1}/{args.copies} imprimée")
    return 0


if __name__ == "__main__":
    sys.exit(main())
