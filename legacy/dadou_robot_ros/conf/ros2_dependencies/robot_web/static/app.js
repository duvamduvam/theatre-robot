"use strict";
/*
 * Console de régie de Didier -- logique front, vanilla JS (pas de framework,
 * pas de build). Le contrat protocole est celui de robot_web/web_protocol.py
 * côté serveur. La LIAISON (WebSocket, auth, heartbeat, envoi des cmd, bandeau,
 * vidéo MJPEG, bouton catalogue) vit dans commun.js, partagée avec la page
 * « scène » (scene.js) : ce fichier-ci ne garde que ce qui est propre à la
 * console (pilotage roues, catalogue, panneau technique, état, cible).
 *
 * SÉCURITÉ pilotage : aucun message "drive" n'est émis si l'on n'a pas
 * l'écriture (isWriter) OU si le serveur ne l'autorise pas (driveEnabled,
 * WEB_DRIVE=true). Le plafond de vitesse reste appliqué SERVEUR ; le facteur
 * "vitesse %" de l'UI ne fait que réduire davantage, jamais dépasser.
 */

// Émission des consignes de pilotage : ~15 Hz (66 ms) tant que le pad ou la
// manette sont actifs. Aligné sur la cadence gamepad -> WebSocket du plan
// (etude-interface-web.md §5 : "gamepad -> WebSocket ~20 Hz").
const DRIVE_PERIOD_MS = 66;

// Zone morte du stick gauche de la manette (bruit du repos).
const GAMEPAD_DEADZONE = 0.15;

// État du flux de pilotage (pad + manette). Une seule boucle 15 Hz lit la
// source active et émet ; à l'inactivité, elle envoie UN zéro puis se tait.
const drive = {
  padActive: false,         // pointeur enfoncé dans le pad
  padX: 0, padZ: 0,         // consigne normalisée [-1,1] issue du pad
  gamepadIndex: null,       // index de la manette connectée, ou null
  lastSentZero: true,       // dernier envoi était-il un zéro ? (anti-spam côté UI)
};

// --- Liaison : état et crochets propres à la console ---------------------------
// `state` et `liaison` sont définis dans commun.js ; la console y ajoute son
// catalogue et branche ce qui dépend de ses boutons.

state.catalog = null;

liaison.surLiaison = () => {
  // Les boutons d'action (catalogue + panneau technique) sont inertes en
  // lecture seule -- l'UI le reflète (le serveur refuse déjà côté écriture).
  document.querySelectorAll(".bouton-catalogue, .servo-ligne button, #btn-stop-contenus, "
      + "#btn-system-restart, #btn-system-shutdown")
    .forEach((btn) => { btn.disabled = !state.isWriter; });
  majPilotageUI();
};

// En sim, prévenir que les sons sont muets (pas d'audio_node dans le
// conteneur) : sans ça, un clic "Sons" semble juste ne rien faire.
liaison.surMode = (mode) => {
  $("note-sim").hidden = (mode !== "SIMULATION");
};

liaison.surEtat = (msg) => afficherEtat(msg);

// --- Onglets (colonne CONTENUS) -----------------------------------------------

document.querySelectorAll(".onglet-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".onglet-btn").forEach((b) => b.classList.remove("actif"));
    document.querySelectorAll(".onglet").forEach((s) => s.classList.remove("actif"));
    btn.classList.add("actif");
    $("onglet-" + btn.dataset.onglet).classList.add("actif");
  });
});

// --- STOP -----------------------------------------------------------------------

$("btn-stop-contenus").addEventListener("click", () => {
  // STOP contenus ET mouvement : le serveur coupe aussi cmd_vel_web (Twist nul).
  envoyer({ type: "stop_all" });
  arreterPilotage(true);
});

// --- Système (double confirmation, spec §5) ---------------------------------

function confirmerDouble(message) {
  return confirm(message) && confirm("Confirmer une seconde fois : " + message);
}

$("btn-system-restart").addEventListener("click", () => {
  if (confirmerDouble("Redémarrer le robot ?")) {
    envoyerCmd("system", "restart");
  }
});

$("btn-system-shutdown").addEventListener("click", () => {
  if (confirmerDouble("Éteindre le robot ?")) {
    envoyerCmd("system", "shutdown");
  }
});

// ============================================================================
//  PILOTAGE ROUES (SIM-ONLY) : pad tactile/souris + manette -> message "drive"
// ============================================================================

function peutPiloter() {
  return state.isWriter && state.driveEnabled;
}

function facteurVitesse() {
  // Réduit la consigne côté UI (10-100 %). N'augmente JAMAIS au-delà de 1 :
  // le plafond dur reste serveur.
  return clamp(Number($("vitesse").value) / 100, 0.1, 1.0);
}

function majPilotageUI() {
  const pad = $("pad");
  const ok = peutPiloter();
  pad.classList.toggle("disabled", !ok);

  let txt;
  if (!state.driveEnabled) {
    txt = "Pilotage désactivé (WEB_DRIVE=false)";
  } else if (!state.isWriter) {
    txt = "Prends la main pour piloter";
  } else {
    txt = "Prêt — glisse dans le pad";
  }
  $("pilotage-etat").textContent = txt;
  $("pilotage-limites").textContent = state.driveEnabled
    ? "plafond " + state.maxLinear + " m/s · " + state.maxAngular + " rad/s"
    : "plafond -- · --";

  if (!ok) {
    // Perte d'autorisation en cours de mouvement : on stoppe et on rentre le
    // curseur du pad (pas de zéro réseau si on ne peut de toute façon rien
    // émettre -- mais on nettoie l'état local).
    drive.padActive = false;
    majCurseurPad(0, 0);
    drive.lastSentZero = true;
  }
}

// Consigne active courante : pad si un pointeur est enfoncé, sinon manette si
// hors zone morte, sinon null (repos).
function consignePilotage() {
  if (drive.padActive) {
    return { x: drive.padX, z: drive.padZ };
  }
  return lireManette();
}

function lireManette() {
  if (drive.gamepadIndex === null || !navigator.getGamepads) {
    return null;
  }
  const gp = navigator.getGamepads()[drive.gamepadIndex];
  if (!gp) {
    return null;
  }
  const ax = gp.axes[0] || 0;   // stick gauche X : droite positif
  const ay = gp.axes[1] || 0;   // stick gauche Y : bas positif
  if (Math.hypot(ax, ay) < GAMEPAD_DEADZONE) {
    return null;                // repos : pas de consigne
  }
  // Haut = avant (x = -ay) ; gauche = rotation à gauche (z = -ax).
  return { x: clamp(-ay, -1, 1), z: clamp(-ax, -1, 1) };
}

// Boucle unique 15 Hz : lit la source active et émet. À l'inactivité, envoie
// UN zéro puis se tait (motif anti-spam de DriveFlow côté serveur).
function bouclePilotage() {
  if (!peutPiloter()) {
    return;
  }
  const src = consignePilotage();
  if (src === null) {
    arreterPilotage(false);
    return;
  }
  const f = facteurVitesse();
  const x = clamp(src.x * f, -1, 1);
  const z = clamp(src.z * f, -1, 1);
  envoyer({ type: "drive", x: x, z: z });
  drive.lastSentZero = false;
  majDriveReadout(x, z);
}

// Arrêt du flux : envoie un zéro une seule fois (sauf si déjà au repos). Le
// paramètre `force` (STOP) émet le zéro même si l'UI se croyait au repos.
function arreterPilotage(force) {
  if (drive.lastSentZero && !force) {
    return;
  }
  if (peutPiloter() || force) {
    envoyer({ type: "drive", x: 0, z: 0 });
  }
  drive.lastSentZero = true;
  majDriveReadout(0, 0);
}

function majDriveReadout(x, z) {
  const lin = (x * state.maxLinear).toFixed(2);
  const ang = (z * state.maxAngular).toFixed(2);
  $("drive-readout").textContent = "lin " + lin + " m/s · ang " + ang + " rad/s";
}

// --- Pad : pointeur (tactile + souris unifiés via Pointer Events) ------------

function majCurseurPad(nx, nz) {
  // nx = avant (+ = haut), nz = gauche (+ = gauche). Position en % du pad :
  // centre 50%/50% au repos, course max ±40 % pour rester dans le cadre. Le
  // curseur est centré sur ce point par transform: translate(-50%,-50%) (CSS).
  const curseur = $("pad-curseur");
  curseur.style.left = (50 - nz * 40) + "%";
  curseur.style.top = (50 - nx * 40) + "%";
}

function padVersConsigne(event) {
  const pad = $("pad");
  const r = pad.getBoundingClientRect();
  // Position du pointeur dans le pad, ramenée en [-1,1] sur chaque axe.
  const nx = clamp((event.clientX - r.left) / r.width * 2 - 1, -1, 1);   // droite positif
  const ny = clamp((event.clientY - r.top) / r.height * 2 - 1, -1, 1);   // bas positif
  drive.padX = -ny;   // haut = avant
  drive.padZ = -nx;   // gauche = rotation à gauche
  majCurseurPad(drive.padX, drive.padZ);
}

function installerPad() {
  const pad = $("pad");

  pad.addEventListener("pointerdown", (event) => {
    if (!peutPiloter()) {
      return;
    }
    drive.padActive = true;
    pad.setPointerCapture(event.pointerId);
    padVersConsigne(event);
    event.preventDefault();
  });

  pad.addEventListener("pointermove", (event) => {
    if (drive.padActive) {
      padVersConsigne(event);
    }
  });

  const relacher = () => {
    if (!drive.padActive) {
      return;
    }
    drive.padActive = false;
    majCurseurPad(0, 0);
    arreterPilotage(false);   // zéro immédiat au relâchement
  };
  pad.addEventListener("pointerup", relacher);
  pad.addEventListener("pointercancel", relacher);
  pad.addEventListener("lostpointercapture", relacher);
}

// --- Manette (Gamepad API) ----------------------------------------------------

window.addEventListener("gamepadconnected", (event) => {
  drive.gamepadIndex = event.gamepad.index;
  $("gamepad-indic").hidden = false;
});

window.addEventListener("gamepaddisconnected", (event) => {
  if (drive.gamepadIndex === event.gamepad.index) {
    drive.gamepadIndex = null;
    $("gamepad-indic").hidden = true;
    arreterPilotage(false);
  }
});

// --- Vitesse : libellé synchronisé -------------------------------------------

$("vitesse").addEventListener("input", () => {
  $("vitesse-val").textContent = $("vitesse").value + " %";
});

// --- Recherche : filtre en direct la colonne CONTENUS ------------------------

$("recherche").addEventListener("input", () => {
  const q = $("recherche").value.trim().toLowerCase();
  document.querySelectorAll(".colonne-contenus .groupe").forEach((groupe) => {
    let visibles = 0;
    groupe.querySelectorAll(".bouton-catalogue, .servo-ligne").forEach((el) => {
      const match = q === "" || el.textContent.toLowerCase().includes(q);
      el.classList.toggle("filtre-cache", !match);
      if (match) {
        visibles += 1;
      }
    });
    // Masque toute la section si rien n'y correspond (seulement en recherche).
    groupe.classList.toggle("filtre-cache", q !== "" && visibles === 0);
  });
});

// --- Catalogue (GET /api/catalog) : grilles spectacle + technique ------------

function remplirGrille(id, topic, entrees) {
  const grille = $(id);
  grille.innerHTML = "";
  entrees.forEach((entree) => {
    // "audios" porte {label, value} ; les autres catalogues sont de simples
    // listes de noms (le nom sert de libellé ET de valeur publiée).
    const libelle = typeof entree === "string" ? entree : entree.label;
    const valeur = typeof entree === "string" ? entree : entree.value;
    grille.appendChild(creerBoutonCatalogue(topic, valeur, libelle));
  });
}

// Servos du panneau technique : mêmes 5 topics que le contrat StringTime,
// chacun avec un champ 0-99 + Envoyer/Stop.
const SERVOS = [
  ["neck", "Cou"],
  ["left_eye", "Œil gauche"],
  ["right_eye", "Œil droit"],
  ["left_arm", "Bras gauche"],
  ["right_arm", "Bras droit"],
];

function construireServos() {
  const conteneur = $("servos");
  conteneur.innerHTML = "";
  SERVOS.forEach(([topic, libelle]) => {
    const ligne = document.createElement("div");
    ligne.className = "servo-ligne";

    const label = document.createElement("label");
    label.textContent = libelle;

    const input = document.createElement("input");
    input.type = "number";
    input.min = "0";
    input.max = "99";
    input.value = "50";

    const btnEnvoyer = document.createElement("button");
    btnEnvoyer.type = "button";
    btnEnvoyer.textContent = "Envoyer";
    btnEnvoyer.addEventListener("click", () => {
      const valeur = Math.max(0, Math.min(99, Number(input.value) || 0));
      envoyerCmd(topic, valeur);
    });

    const btnStop = document.createElement("button");
    btnStop.type = "button";
    btnStop.textContent = "Stop";
    btnStop.addEventListener("click", () => envoyerCmd(topic, "stop"));

    ligne.append(label, input, btnEnvoyer, btnStop);
    conteneur.appendChild(ligne);
  });
  // Les boutons viennent d'être (re)créés (naissent "enabled") : il faut leur
  // ré-appliquer l'état écriture/lecture seule courant.
  majBadgeEcriture();
}

function chargerCatalogue() {
  fetch(urlHttp("/api/catalog"))
    .then((r) => r.json())
    .then((catalogue) => {
      state.catalog = catalogue;
      // Les visages "calib*" (mires d'étalonnage LED) NE vont PAS en Spectacle :
      // ils partent dans le panneau Technique (cf. CLAUDE.md, calibration à l'œil
      // humain, jamais pendant le jeu).
      const faces = catalogue.faces.filter((f) => !f.startsWith("calib"));
      const calibs = catalogue.faces.filter((f) => f.startsWith("calib"));
      remplirGrille("grille-animations", "animation", catalogue.animations);
      remplirGrille("grille-faces", "face", faces);
      remplirGrille("grille-calib", "face", calibs);
      remplirGrille("grille-audios", "audio", catalogue.audios);
      remplirGrille("grille-robot-lights", "robot_lights", catalogue.robot_lights);
      remplirGrille("grille-relais", "relay", catalogue.relays);
      majBadgeEcriture();
    })
    .catch((e) => logErreur("catalogue indisponible : " + e));
}

// --- Panneau « reçu par le robot » + état (dernier message "state") ----------

const STATUT_DIRECT = [
  ["animation", "Animation", "grille-animations"],
  ["face", "Visage", "grille-faces"],
  ["audio", "Son", "grille-audios"],
  ["robot_lights", "Lumières", "grille-robot-lights"],
];

// --- Options actives (2026-07-13) : surbrillance verte `en-cours` des
// toggles du panneau Technique, pilotée par les topics d'ÉTAT quand ils
// existent. [topic source, id du groupe de boutons, payload -> data-value
// attendu]. chat_state/persona_state : latchés par chat_node (Pi vision) —
// pas de chat_node en route = AUCUN bouton vert (honnête : un « Parole ON »
// vert sans node derrière est exactement la confusion vécue le 13/07).
// gaze : pas d'état publié par gaze_follower, on retombe sur le dernier
// ORDRE vu passer (approximation documentée dans interfaces.md).
const STATUT_TOGGLES = [
  ["persona_state", "groupe-persona", (v) => v],
  ["chat_state", "groupe-chat", (v) => (v === "off" ? "off" : "on")],
  ["gaze", "groupe-gaze", (v) => v],
];

function majToggles(topics) {
  STATUT_TOGGLES.forEach(([topic, groupeId, versValeur]) => {
    const info = topics[topic];
    // Comparaison en chaîne : dataset.* est toujours une chaîne côté DOM.
    const attendu = info ? versValeur(String(info.msg)) : null;
    document.querySelectorAll("#" + groupeId + " .bouton-catalogue").forEach((btn) => {
      btn.classList.toggle("en-cours", attendu !== null && btn.dataset.value === attendu);
    });
  });
}

function libelleValeur(valeur) {
  if (valeur === false) {
    return "arrêtée";           // animation: false = stop d'animation
  }
  return typeof valeur === "string" ? valeur : JSON.stringify(valeur);
}

function majStatutDirect(topics) {
  const conteneur = $("statut-direct");
  conteneur.replaceChildren();
  STATUT_DIRECT.forEach(([topic, libelle, grilleId]) => {
    const info = topics[topic];

    const item = document.createElement("span");
    item.className = "statut-item";
    const nom = document.createElement("span");
    nom.className = "statut-nom";
    nom.textContent = libelle;
    const valeur = document.createElement("span");
    valeur.className = "statut-valeur" + (info ? "" : " statut-vide");
    valeur.textContent = info ? libelleValeur(info.msg) + " · " + info.age_s + " s" : "—";
    item.append(nom, valeur);
    conteneur.appendChild(item);

    // Surbrillance du contenu actif dans sa grille (comparaison en chaîne :
    // dataset.* est toujours une chaîne côté DOM).
    const attendu = info ? String(info.msg) : null;
    document.querySelectorAll("#" + grilleId + " .bouton-catalogue").forEach((btn) => {
      btn.classList.toggle("en-cours", attendu !== null && btn.dataset.value === attendu);
    });
  });
}

function afficherEtat(msg) {
  majStatutDirect(msg.topics);
  majToggles(msg.topics);
  // Construction en DOM + textContent (jamais innerHTML avec les payloads) :
  // le contenu vient des topics ROS, donc de n'importe quel publieur -- un
  // payload contenant du HTML ne doit pas pouvoir s'injecter dans la page.
  const topicsDiv = $("etat-topics");
  const table = document.createElement("table");
  const entete = document.createElement("tr");
  ["Topic", "Dernier payload", "Âge"].forEach((titre) => {
    const th = document.createElement("th");
    th.textContent = titre;
    entete.appendChild(th);
  });
  table.appendChild(entete);
  Object.entries(msg.topics).forEach(([topic, info]) => {
    const tr = document.createElement("tr");
    [topic, JSON.stringify(info.msg), info.age_s + " s"].forEach((texte) => {
      const td = document.createElement("td");
      td.textContent = texte;
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  topicsDiv.replaceChildren(table);

  $("etat-nodes").textContent = "Nodes vivants (" + msg.nodes.length + ") : " + msg.nodes.join(", ");
}

// --- Sélecteur de cible --------------------------------------------------------

function installerCible() {
  const select = $("cible");
  const base = cibleBase();
  // Cible mémorisée hors presets (saisie « Autre adresse… ») : on l'ajoute
  // au menu pour qu'elle soit affichable/re-sélectionnable.
  if (base && !Array.from(select.options).some((o) => o.value === base)) {
    const opt = document.createElement("option");
    opt.value = base;
    opt.textContent = base.replace(/^https?:\/\//, "");
    select.insertBefore(opt, select.querySelector('option[value="autre"]'));
  }
  select.value = base;

  select.addEventListener("change", () => {
    let nouvelle = select.value;
    if (nouvelle === "autre") {
      nouvelle = (prompt("Adresse du pont à contrôler (http://hôte:port)", "http://") || "").trim();
      if (!/^https?:\/\/.+/.test(nouvelle)) {
        select.value = cibleBase(); // saisie annulée/invalide : on ne bouge pas
        return;
      }
    }
    // Garde-fou : basculer vers le VRAI Didier se confirme. Le badge rouge du
    // hello reste la seule vérité, mais on évite le clic réflexe.
    // didier.local = alias mDNS du même Pi robot (cf. sélecteur) : même garde.
    if ((nouvelle.includes("192.168.1.2") || nouvelle.includes("didier.local"))
        && !confirm("Basculer cette console sur le VRAI Didier ?")) {
      select.value = cibleBase();
      return;
    }
    localStorage.setItem("cible", nouvelle);
    basculerCible();
  });
}

function basculerCible() {
  // Repart à neuf sur la nouvelle cible : badges neutres tant que le hello de
  // la nouvelle machine n'est pas arrivé, catalogue + vidéo rechargés, socket
  // fermée (son close déclenche la reconnexion auto, qui lit la nouvelle
  // base). Côté ancienne cible, la déconnexion libère l'écriture et publie le
  // zéro drive (comportements serveur déjà en place).
  majBadgeMode("INCONNU", "?");
  state.isWriter = false;
  majBadgeEcriture();
  chargerCatalogue();
  chargerVideo();
  if (state.ws && state.ws.readyState !== WebSocket.CLOSED) {
    state.ws.close();
  }
  // Socket déjà fermée : le timer de reconnexion en cours utilisera la
  // nouvelle base tout seul (urlWebSocket() la lit à chaque tentative).
}

// --- Démarrage ------------------------------------------------------------------

construireServos();
installerCible();
chargerCatalogue();
installerPad();
installerVideo();
setInterval(bouclePilotage, DRIVE_PERIOD_MS);
connecter();
