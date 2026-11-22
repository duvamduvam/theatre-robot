"use strict";
/*
 * Aperçu des BANDES LED (lot I0, 22/11) : dessin des pixels d'une brique de lumière.
 *
 * Le pont (didier_web/apercu_lumieres.py) dit QUELLE brique le ruban du robot afficherait
 * (méthode, couleur, depuis combien de ms) ; ce fichier dit À QUOI ELLE RESSEMBLE, pixel par
 * pixel, d'après les paramètres de didier_core/visual/lights_animations.py (Adafruit LED
 * Animation) : chase 3 allumées / 6 éteintes au pas de 0,1 s, blink 0,5 s, pulse 1 s,
 * color_cycle magenta / orange / turquoise toutes les 0,5 s, rainbow sur 2 s, etc.
 * Approximation assumée : reconnaître l'animation, pas la reproduire au pixel (le ruban virtuel
 * fidèle est au lot L2c).
 *
 * PUR : aucune lecture du DOM ni de l'horloge, tout est passé en paramètre — testé hors
 * navigateur par packages/didier_core/test/unit/test_apercu_lumieres.py (node).
 * Noms préfixés « lum » : ce script partage la portée globale de commun.js et scene.js.
 */

// Couleurs fixes de ColorCycle dans lights_animations.py (adafruit_led_animation.color).
const LUM_COULEURS_CYCLE = [[255, 0, 20], [255, 40, 0], [0, 255, 40]];
const LUM_NOIR = [0, 0, 0];

// Pseudo-aléa déterministe (étincelles) : même pas de temps, même pixel -> même tirage.
function lumHasard(a, b) {
  let x = (a * 374761393 + b * 668265263) >>> 0;
  x = Math.imul(x ^ (x >>> 13), 1274126177) >>> 0;
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
}

function lumEchelle(rgb, facteur) {
  const f = Math.max(0, Math.min(1, facteur));
  return rgb.map((c) => Math.round(c * f));
}

// Roue de couleurs (rainbowio.colorwheel) : 0..255 -> rouge, vert, bleu, rouge.
function lumRoue(pos) {
  const p = ((Math.floor(pos) % 256) + 256) % 256;
  if (p < 85) {
    return [255 - p * 3, p * 3, 0];
  }
  if (p < 170) {
    return [0, 255 - (p - 85) * 3, (p - 85) * 3];
  }
  return [(p - 170) * 3, 0, 255 - (p - 170) * 3];
}

// Pixels [r, g, b] (0..255) d'une brique au temps t_ms (depuis son début), sur n LED.
// methode inconnue ou absente : tout noir (la légende dit « inconnue »).
function lumPixels(methode, rgb, tMs, n) {
  const base = rgb || LUM_NOIR;
  const pas = (ms) => Math.floor(tMs / ms);
  const tout = (c) => Array.from({ length: n }, () => c);
  switch (methode) {
    case "solid":
    case "fade_red":
      return tout(methode === "fade_red" ? [255, 0, 0] : base);
    case "chase":
    case "default": {
      // size 3, spacing 6, speed 0.1 : 3 allumées, 6 éteintes, une LED de plus à chaque pas.
      const decal = pas(100);
      return Array.from({ length: n }, (_, i) => (((i - decal) % 9 + 9) % 9 < 3 ? base : LUM_NOIR));
    }
    case "blink":
      return tout(pas(500) % 2 === 0 ? base : LUM_NOIR);
    case "pulse": {
      // period 1 s : respiration noir -> couleur -> noir.
      const phase = (tMs % 1000) / 1000;
      return tout(lumEchelle(base, (1 - Math.cos(2 * Math.PI * phase)) / 2));
    }
    case "color_cycle":
      return tout(LUM_COULEURS_CYCLE[pas(500) % LUM_COULEURS_CYCLE.length]);
    case "comet": {
      // speed 0.1, queue = n/4 (défaut Adafruit), sans rebond.
      const queue = Math.max(1, Math.floor(n / 4));
      const tete = pas(100) % (n + queue);
      return Array.from({ length: n }, (_, i) => {
        const d = tete - i;
        return d >= 0 && d < queue ? lumEchelle(base, 1 - d / queue) : LUM_NOIR;
      });
    }
    case "rainbow":
      // period 2 s : l'arc-en-ciel déroulé sur la bande, qui tourne.
      return Array.from({ length: n }, (_, i) => lumRoue(256 * (i / n + tMs / 2000)));
    case "rainbow_chase": {
      // size 5, spacing 3, speed 0.1 : des paquets de 5 aux couleurs de l'arc-en-ciel.
      const decal = pas(100);
      return Array.from({ length: n }, (_, i) => (((i - decal) % 8 + 8) % 8 < 5
        ? lumRoue(256 * ((i - decal) / n)) : LUM_NOIR));
    }
    case "rainbow_comet": {
      // tail_length 30, bounce : la comète arc-en-ciel fait l'aller-retour.
      const queue = Math.min(30, n);
      const course = Math.max(1, n - 1);
      const k = pas(100) % (2 * course);
      const tete = k <= course ? k : 2 * course - k;
      const sens = k <= course ? 1 : -1;
      return Array.from({ length: n }, (_, i) => {
        const d = (tete - i) * sens;
        return d >= 0 && d < queue ? lumEchelle(lumRoue(256 * d / queue), 1 - d / queue) : LUM_NOIR;
      });
    }
    case "sparkle":
    case "rainbow_sparkle":
    case "sparkle_pulse":
    case "random": {
      // Étincelles : sparkle 10 (pas 0,05 s), rainbow_sparkle 15 (0,1 s), sparkle_pulse sur
      // une pulsation de 3 s ; random = des LED au hasard.
      const vitesse = methode === "sparkle" ? 50 : 100;
      const nb = methode === "rainbow_sparkle" ? 15 : 10;
      const p = pas(vitesse);
      const fond = methode === "sparkle_pulse"
        ? (1 - Math.cos(2 * Math.PI * ((tMs % 3000) / 3000))) / 2 * 0.6 : 0.15;
      return Array.from({ length: n }, (_, i) => {
        const couleur = methode === "rainbow_sparkle" ? lumRoue(256 * i / n)
          : methode === "random" ? lumRoue(256 * lumHasard(p, i + 7)) : base;
        return lumHasard(p, i) < nb / n ? couleur : lumEchelle(couleur, methode === "random" ? 0 : fond);
      });
    }
    default:
      return tout(LUM_NOIR);
  }
}
