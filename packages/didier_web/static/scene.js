"use strict";
/*
 * Page « scène » de Didier -- caméra | visage LED | conversation, plus les
 * commandes de la répétition. Vanilla JS, pas de framework, pas de build.
 * La liaison (WebSocket, auth, heartbeat, envoi des cmd, bandeau, flux MJPEG,
 * bouton catalogue délégué) vient de commun.js : ici, seulement ce qui est
 * propre à la scène.
 *
 * COULISSES VISIBLES depuis le 18/11 (re-décision de David ; l'étude répétition
 * simulée §13.1 disait « David ne voit pas le tirage ») : le panneau « Coulisses »
 * montre le metteur en scène (chat_situation, chat_prompt en flux ; mission_state
 * dans `state`) et, en sim, le journal du régisseur (rehearsal/journal, flux),
 * pannes et lubies comprises. Repliable, état mémorisé : le replier = s'entraîner
 * à l'aveugle. Conséquences de code, à ne pas « améliorer » :
 *  - de `state` (toutes les 2 s) on ne lit que chat_state, persona_state,
 *    route_state, chat_audio_chain (branchement du son, 31/10), rehearsal/state
 *    (séance + arrêt vocal, 31/10 : le régisseur n'y met AUCUNE panne),
 *    camera_state, camera_source_state, camera_sources et mission_state ; JAMAIS
 *    chat_instruction ni route_speed (masqués par le pont, TOPICS_MASQUES : les
 *    coulisses passent par les topics dédiés, pas en levant ce masque) ;
 *  - le curseur de vitesse est une CONSIGNE sans relecture : il ne se recale
 *    pas sur ce que le robot a reçu ;
 *  - le texte soufflé n'est pas affiché à l'envoi : il apparaît dans le fil
 *    quand Didier l'a ENTENDU (chat_transcript, après d'éventuelles pannes de
 *    compréhension) -- c'est précisément ce que David doit voir.
 *
 * Éditeur des données (lot L1d-3, section en fin de fichier) : présent seulement
 * si hello.data_edit ; écrit par les types WebSocket data_edit / valider_roues,
 * lit GET /api/data et les flux data_edit_result, validation_sim, roues_refusees.
 */

// Reste sur le pont qui sert la page : une cible mémorisée par la console (ex. le
// vrai Didier) ne doit pas rediriger en silence une page ouverte sur la sim.
liaison.suivreCible = false;

// Personnalités proposées : liste GRAVÉE ici, pas lue du catalogue. Les personas
// vivent côté Pi vision (didier_vision.ai.personas) que le pont web ne connaît pas ; en
// ajouter une = l'ajouter là-bas ET ici (persona inconnue du node = ignorée).
const PERSONAS = [
  ["bougon", "Bougon"],
  ["naif", "Naïf"],
  ["vantard", "Vantard"],
  ["mauvaisefoi", "Mauvaise foi"],
];

// chat_state (latché par chat_node) -> libellé du badge.
const LIBELLE_ETAT_CHAT = {
  off: "off",
  listening: "écoute",
  thinking: "réfléchit",
  speaking: "parle",
};

// route_state (latché par le cheminement) -> libellé du badge.
const LIBELLE_ETAT_ROUTE = {
  on: "route en marche",
  off: "route arrêtée",
};

// rehearsal/state.seance (latché par le régisseur) -> libellé du badge.
const LIBELLE_ETAT_SEANCE = {
  attente: "séance : en attente",
  en_cours: "séance : en cours",
  terminee: "séance : terminée",
};

// camera_state (latché côté vision) -> libellé du badge, SELON LA SOURCE
// (camera_source_state) : l'état dit si l'entrée de la perception produit des
// images. En source Gazebo, la webcam est FERMÉE — afficher « webcam allumée »
// était faux (18/11) ; « on » Gazebo = des images arrivent vraiment.
const LIBELLE_ETAT_CAMERA = {
  webcam: { on: "webcam allumée", off: "webcam coupée" },
  gazebo: { on: "caméra Gazebo : images reçues", off: "caméra Gazebo : aucune image" },
};

// camera_source_state (latché côté vision) -> mot affiché dans le titre du panneau.
const LIBELLE_SOURCE = {
  webcam: "(webcam)",
  gazebo: "(Gazebo)",
};

// Qui parle dans chat_transcript : david = le texte que Didier a ENTENDU,
// didier = chacune de ses phrases.
const ROLES = { david: "David", didier: "Didier" };

// Messages gardés dans le fil (les plus anciens sont retirés).
const FIL_MAX = 300;
// Le fil suit les nouveaux messages tant que le lecteur est à moins de cette
// distance (px) du bas ; au-delà il relit l'historique, on ne le déplace pas.
const FIL_BAS_PX = 40;

// Curseur de vitesse : pas de 0,05 (le fader de la télécommande est aussi fin).
const VITESSE_PAR_UNITE = 20;

// Flux du visage : face_sim sert son MJPEG sur SON port, pas via le pont.
const PORT_VISAGE = 8766;
const CLE_URL_VISAGE = "sceneUrlVisage";

// --- Personnalités ---------------------------------------------------------------

function construirePersonas() {
  const groupe = $("groupe-persona");
  PERSONAS.forEach(([nom, libelle]) => {
    groupe.appendChild(creerBoutonCatalogue("persona", nom, libelle));
  });
}

// --- Liaison : ce qui dépend de l'écriture et du mode ----------------------------

liaison.surLiaison = () => {
  // Boutons d'action inertes en lecture seule (le serveur refuse déjà). Le champ
  // visage et le ⟳ restent actifs : regarder ne demande pas l'écriture.
  // Éditeur : « Charger » reste actif (lire ne demande pas l'écriture), pas les envois.
  document.querySelectorAll(".bouton-catalogue, #scene-form-texte button, "
      + "#scene-form-consigne button, #scene-vitesse, .jeu-bouton, #jeu-cible-va-la, "
      + "#editeur-envoyer, #editeur-rejouer, #editeur-valider-roues, #editeur-image-envoyer, #bugs-couper, "
      + "#audio-tester, #audio-redetecter")
    .forEach((el) => { el.disabled = !state.isWriter; });
  majEditeurVisible();
  majAudioVisible();
  majBoutonRearmer();
  // Route / vitesse / séance : seulement si le serveur les accepte (hello.rehearsal).
  document.querySelectorAll(".scene-repetition").forEach((el) => {
    el.hidden = !state.rehearsal;
  });
  // Panneau « Ce que Didier voit » : seulement si le serveur sert /perception.
  // Le flux n'est chargé qu'à la première annonce (puis relancé par ⟳).
  // Idem pour « Didier vu de l'extérieur » (/exterior, caméra de poursuite sim).
  $("scene-exterieur").hidden = !state.exterior;
  if (state.exterior && !fluxExterieur.charge) {
    fluxExterieur.charge = true;
    fluxExterieur.charger();
  }
  perceptionAnnoncee = Boolean(state.perception);
  majVisibilitePerception();
  if (state.perception && !fluxPerception.charge) {
    fluxPerception.charge = true;
    fluxPerception.charger();
  }
};

// --- État (message "state", toutes les 2 s) ---------------------------------------

function valeurTopic(topics, nom) {
  const info = topics[nom];
  if (!info) {
    return null;
  }
  // Le pont DÉCODE les payloads JSON (chat_audio_chain arrive en objet) :
  // on le resérialise plutôt que d'obtenir « [object Object] » (vécu le 31/10).
  return typeof info.msg === "object" && info.msg !== null ? JSON.stringify(info.msg) : String(info.msg);
}

// Surbrillance verte du bouton dont la valeur est l'état RÉEL (pas le dernier
// clic) ; attendu = null -> aucun bouton vert (pas de node derrière).
function surlignerGroupe(groupeId, attendu) {
  document.querySelectorAll("#" + groupeId + " .bouton-catalogue").forEach((btn) => {
    btn.classList.toggle("en-cours", attendu !== null && btn.dataset.value === attendu);
  });
}

function majBadgeEtat(id, libelles, valeur, actif) {
  const badge = $(id);
  // Vide quand on ne sait rien : le CSS masque le badge (pas de « — » orphelin).
  badge.textContent = valeur === null ? "" : (libelles[valeur] || valeur);
  badge.className = "badge " + (actif ? "badge-on" : "badge-off");
}

function afficherEtatScene(msg) {
  const chat = valeurTopic(msg.topics, "chat_state");
  const persona = valeurTopic(msg.topics, "persona_state");
  const route = valeurTopic(msg.topics, "route_state");

  majBadgeEtat("scene-etat-chat", LIBELLE_ETAT_CHAT, chat, chat !== null && chat !== "off");
  // Parole ON/OFF : comme la console, tout état hors "off" vaut « ON ».
  surlignerGroupe("groupe-chat", chat === null ? null : (chat === "off" ? "off" : "on"));
  surlignerGroupe("groupe-persona", persona);

  majBadgeEtat("scene-etat-route", LIBELLE_ETAT_ROUTE, route, route === "on");
  surlignerGroupe("groupe-route", route);

  afficherEtatRegisseur(valeurTopic(msg.topics, "rehearsal/state"));

  const camera = valeurTopic(msg.topics, "camera_state");
  const source = valeurTopic(msg.topics, "camera_source_state");
  // Source inconnue : libellés webcam (historique, la vision n'a rien dit d'autre).
  majBadgeEtat("scene-etat-camera", LIBELLE_ETAT_CAMERA[source] || LIBELLE_ETAT_CAMERA.webcam,
               camera, camera === "on");
  surlignerGroupe("groupe-camera", camera);
  // Coupée : texte « caméra coupée » par-dessus, au lieu de la dernière image figée.
  // État inconnu (null) : on ne masque rien, la webcam n'a pas dit qu'elle était coupée.
  $("perception-coupee").hidden = camera !== "off";

  afficherSourceCamera(source, valeurTopic(msg.topics, "camera_sources"));
}

// Source des images de la perception : surbrillance d'après l'état RÉEL, titre du panneau,
// et bouton Gazebo visible seulement si la vision annonce "gazebo". Liste absente ou
// illisible = webcam seule (on ne propose jamais une source que personne n'a annoncée).
// Panneau perception masqué en source Gazebo : il répéterait exactement la caméra
// Gazebo du dessus (remarque de David, 31/10) ; il ne sert qu'en source webcam.
let perceptionAnnoncee = false;
let sourceCourante = null;

function majVisibilitePerception() {
  $("scene-perception").hidden = !perceptionAnnoncee || sourceCourante === "gazebo";
  majVuePrincipale();
}

function afficherSourceCamera(source, brutSources) {
  sourceCourante = source;
  majVisibilitePerception();
  let sources = [];
  try {
    const lue = brutSources === null ? [] : JSON.parse(brutSources);
    sources = Array.isArray(lue) ? lue : [];
  } catch (e) {
    logErreur("sources de caméra illisibles");
  }
  $("bouton-source-gazebo").hidden = !sources.includes("gazebo");
  surlignerGroupe("groupe-source", source);
  // Source inconnue (null) : titre historique « (webcam) », la vision n'a rien dit d'autre.
  $("perception-source").textContent = LIBELLE_SOURCE[source] || LIBELLE_SOURCE.webcam;
}

// rehearsal/state : JSON {"seance", "arret_vocal"} du régisseur. Illisible ou absent
// = badges « inconnu » (régisseur pas lancé), jamais un état inventé.
function afficherEtatRegisseur(brut) {
  let etat = null;
  try {
    etat = brut === null ? null : JSON.parse(brut);
  } catch (e) {
    logErreur("état de séance illisible");
  }
  const seance = etat !== null && typeof etat === "object" ? etat.seance : null;
  majBadgeEtat("scene-etat-seance", LIBELLE_ETAT_SEANCE, typeof seance === "string" ? seance : null,
               seance === "en_cours");
  $("scene-arret-vocal").hidden = !(etat !== null && typeof etat === "object" && etat.arret_vocal === true);
}

// --- Oreille de Didier : branchement (chat_audio_chain) + entendu (chat_hearing) ---

// Ordre = chemin du son ; libellés lisibles. Une clé absente du message est sautée.
const CHAINE = [
  ["micro", "Micro"], ["attenuation_micro", "Atténuation micro"],
  ["detection_parole", "Détection de parole"], ["transcription", "Transcription"],
  ["repli", "Repli"], ["reponse", "Réponse"], ["voix", "Voix"], ["sortie", "Sortie"],
];
const ENTENDU_MAX = 8;
let derniereChaine = null;

function afficherChaine(brut) {
  if (brut === null || brut === derniereChaine) {
    return;
  }
  derniereChaine = brut;
  let chaine;
  try {
    chaine = JSON.parse(brut);
  } catch (e) {
    logErreur("branchement illisible");
    return;
  }
  const corps = $("scene-chaine");
  corps.replaceChildren();
  for (const [cle, libelle] of CHAINE) {
    if (chaine[cle] === null || chaine[cle] === undefined) {
      continue;
    }
    const tr = document.createElement("tr");
    const a = document.createElement("td");
    a.className = "label";
    a.textContent = libelle;
    const b = document.createElement("td");
    b.textContent = cle === "attenuation_micro" ? "× " + chaine[cle] : String(chaine[cle]);
    tr.append(a, b);
    corps.appendChild(tr);
  }
}

function ajouterEntendu(h) {
  if (h === null || typeof h !== "object" || typeof h.entendu !== "string") {
    logErreur("tour d'écoute illisible");
    return;
  }
  const garde = h.verdict === "gardé";
  const li = document.createElement("li");
  li.className = "scene-entendu-" + (garde ? "garde" : "jete");
  const tete = document.createElement("span");
  tete.className = "scene-msg-role";
  const duree = h.stt_ms === null || h.stt_ms === undefined ? "" : " · " + h.stt_ms + " ms";
  // S0 (25/11) : pour un énoncé jeté, sa durée et sa crête (silence, bruit ou voix incomprise).
  const niveau = typeof h.crete === "number"
    ? " · énoncé " + (h.duree_ms / 1000).toFixed(1) + " s, crête " + h.crete
      + (h.jetes_de_suite > 1 ? " · " + h.jetes_de_suite + " de suite" : "")
    : "";
  tete.textContent = new Date().toLocaleTimeString() + " · " + h.moteur + duree + " · " + h.verdict + niveau;
  const texte = document.createElement("span");
  // textContent : le texte vient du micro, jamais interprété comme du HTML.
  texte.textContent = h.entendu === "" ? "(rien)" : "« " + h.entendu + " »";
  li.append(tete, texte);
  const liste = $("scene-entendu");
  liste.prepend(li);   // le plus récent en haut
  while (liste.children.length > ENTENDU_MAX) {
    liste.lastChild.remove();
  }
  const badge = $("scene-oreille-moteur");
  badge.textContent = h.moteur;
  badge.className = "badge " + (h.moteur === "distant" ? "badge-on" : "badge-off");
}

liaison.surEtat = (msg) => {
  afficherEtatScene(msg);
  afficherChaine(valeurTopic(msg.topics, "chat_audio_chain"));
  afficherJeu(msg);
  afficherMission(msg);
  afficherCorpsSur(msg);
  // Bandes LED (lot I0) : le `state` resynchronise (page ouverte en cours de jeu) ; les
  // changements arrivent aussitôt par le message `lumieres`.
  if (msg.lumieres) {
    recevoirLumieres(msg.lumieres);
  }
};

// --- Onglet « Audio » (22/11, banc PC en simulation) --------------------------------
// Tout le jugement est côté pont (didier_web/panneau_audio.py, testé) : la page AFFICHE le
// verdict de GET /api/audio, rien n'est déduit ici. Sondage 4 fois/s onglet ouvert (vumètre),
// toutes les 2 s replié (le verdict du résumé reste frais), jamais page cachée.
const AUDIO_PERIODE_OUVERT_MS = 250;
const AUDIO_PERIODE_REPLIE_MS = 2000;
const AUDIO_PASTILLE = { ok: "🟢", attention: "🟠", ko: "🔴", attente: "⏳" };
let audioMinuterie = null;
let audioDemarre = false;   // une seule chaîne de sondage, quel que soit le nombre de hello

function majAudioVisible() {
  $("scene-audio").hidden = !state.audioBanc;
  $("audio-bandeau").hidden = !state.audioBanc;
  if (state.audioBanc && !audioDemarre) {
    audioDemarre = true;
    sonderAudio();
  }
}

function planifierAudio() {
  const delai = $("scene-audio").open ? AUDIO_PERIODE_OUVERT_MS : AUDIO_PERIODE_REPLIE_MS;
  audioMinuterie = setTimeout(sonderAudio, delai);
}

async function sonderAudio() {
  audioMinuterie = null;
  if (!state.audioBanc) {
    audioDemarre = false;
    return;
  }
  if (document.visibilityState === "visible") {
    try {
      const reponse = await fetch(urlHttp("/api/audio"), { cache: "no-store" });
      if (!reponse.ok) {
        throw new Error("HTTP " + reponse.status);
      }
      afficherAudio(await reponse.json());
    } catch (e) {
      afficherAudio({ verdict: "ko", message: "pont web injoignable pour l'audio (" + e.message + ")",
                      action: "", autres: [] });
    }
  }
  planifierAudio();
}

function badgeCote(id, cote) {
  const el = $(id);
  if (!cote) {
    el.textContent = "—";
    el.className = "badge badge-off";
    return;
  }
  const ok = cote.present && cote.muet !== true;
  el.textContent = !cote.present ? (cote.casque_connecte === false ? "casque éteint" : "absent")
      : (cote.muet ? "coupé (muet)" : "présent");
  el.className = "badge " + (ok ? "badge-on" : "badge-ko");
}

function nomCote(cote) {
  if (!cote) {
    return "—";
  }
  const casque = cote.casque ? " · casque " + cote.casque : "";
  return (cote.nom || "?") + casque + (cote.suit_ubuntu ? " (réglage son d'Ubuntu)" : "");
}

function afficherVumetre(entree) {
  const pct = (v) => (v === null || v === undefined ? 0 : v) + "%";
  $("audio-vumetre-barre").style.width = pct(entree ? entree.pct : null);
  $("audio-vumetre-pic").style.left = pct(entree ? entree.pct_3s : null);
  $("audio-vumetre-seuil").style.left = pct(entree ? entree.seuil_pct : null);
}

function afficherAudio(a) {
  $("audio-verdict").textContent = AUDIO_PASTILLE[a.verdict] || "⏳";
  $("audio-bandeau").textContent = (AUDIO_PASTILLE[a.verdict] || "⏳") + " Audio";
  $("audio-bandeau").title = a.message || "";
  $("audio-verdict-texte").textContent = a.message || "";
  $("audio-action").textContent = a.action ? "→ " + a.action : "";
  const autres = $("audio-autres");
  autres.replaceChildren();
  for (const texte of a.autres || []) {
    const li = document.createElement("li");
    li.textContent = texte;
    autres.appendChild(li);
  }
  $("audio-micro-nom").textContent = nomCote(a.entree);
  badgeCote("audio-micro-etat", a.entree);
  $("audio-sortie-nom").textContent = nomCote(a.sortie);
  badgeCote("audio-sortie-etat", a.sortie);
  afficherVumetre(a.entree);
  const t = a.temoins || {};
  const entend = $("audio-temoin-entend");
  entend.textContent = t.entend === "jete" ? "Didier a entendu… et jeté" : "Didier m'entend";
  entend.className = "badge " + (t.entend === "oui" ? "badge-on" : (t.entend === "jete" ? "badge-ko" : "badge-off"));
  // textContent : le texte vient du micro, jamais interprété comme du HTML.
  $("audio-entendu").textContent = t.entendu ? "« " + t.entendu + " »" : "";
  $("audio-temoin-parle").className = "badge " + (t.parle ? "badge-on" : "badge-off");
  $("audio-resultat").textContent = resultatAudio(a);
  $("audio-redetecter").textContent = a.redetection && a.redetection.en_cours ? "Re-détection…" : "Re-détecter";
}

// Dernier geste (bip, re-détection) et son résultat, tant qu'il date de moins d'une minute.
function resultatAudio(a) {
  const lignes = [];
  const act = a.derniere_action;
  if (act && act.il_y_a_s < 60) {
    lignes.push((act.ok ? "✓ " : "✗ ") + act.message);
  }
  const r = a.redetection;
  if (r && !r.en_cours && r.il_y_a_s !== null && r.il_y_a_s < 60) {
    lignes.push("re-détection (code " + r.code + ") :\n" + (r.resume || ""));
  }
  return lignes.join("\n");
}

function installerAudio() {
  for (const [id, action] of [["audio-tester", "tester"], ["audio-redetecter", "redetecter"]]) {
    $(id).addEventListener("click", (event) => {
      if (!state.isWriter) {
        return;
      }
      state.attenteAck.audio_banc = event.currentTarget;
      state.dernierBouton = event.currentTarget;
      envoyer({ type: "audio_banc", action: action });
    });
  }
  $("audio-bandeau").addEventListener("click", () => {
    $("scene-audio").open = true;
    $("scene-audio").scrollIntoView({ block: "nearest" });
  });
  // Ouvert : le vumètre passe tout de suite à 4 Hz (sans attendre la prochaine sonde lente).
  $("scene-audio").addEventListener("toggle", () => {
    if (state.audioBanc && $("scene-audio").open && audioMinuterie !== null) {
      clearTimeout(audioMinuterie);
      sonderAudio();
    }
  });
}

// --- Bandes LED (lot I0) : ce que le ruban afficherait ---------------------------------
// Le pont tient le MODÈLE (didier_web/apercu_lumieres.py : quelle brique, depuis quand) ;
// lumieres.js dit à quoi ressemble la brique. Ici : recaler l'horloge et peindre ~30 i/s,
// seulement onglet visible. La luminosité réelle du ruban (0,05 au repos) n'est PAS appliquée
// à l'écran (tout serait noir) : la légende la donne si un message l'a changée.
const LUMIERES_PERIODE_MS = 33;
const lumieres = { instant: null, recuA: 0, toiles: [], dernierePeinture: 0 };

function recevoirLumieres(instant) {
  lumieres.instant = instant;
  lumieres.recuA = performance.now();
  const bandes = instant.bandes || [];
  const conteneur = $("scene-lumieres-bandes");
  if (lumieres.toiles.length !== bandes.length) {
    conteneur.replaceChildren();
    lumieres.toiles = bandes.map((bande) => {
      const toile = document.createElement("canvas");
      toile.width = bande.leds;
      toile.height = 1;
      toile.title = "bande " + bande.nom + " (" + bande.leds + " LED)";
      conteneur.appendChild(toile);
      return toile;
    });
  }
  const morceaux = [instant.sequence || "inconnue"];
  if (instant.brique) {
    morceaux.push(instant.brique + " (" + (instant.methode || "méthode inconnue") + ")");
  }
  if (instant.luminosite !== null && instant.luminosite !== undefined) {
    morceaux.push("luminosité " + instant.luminosite);
  }
  $("scene-lumieres-legende").textContent = "lumières : " + morceaux.join(" · ");
}

function peindreLumieres(maintenant) {
  requestAnimationFrame(peindreLumieres);
  const instant = lumieres.instant;
  if (!instant || document.hidden || maintenant - lumieres.dernierePeinture < LUMIERES_PERIODE_MS) {
    return;
  }
  lumieres.dernierePeinture = maintenant;
  const tMs = instant.depuis_ms + (maintenant - lumieres.recuA);
  (instant.bandes || []).forEach((bande, k) => {
    const toile = lumieres.toiles[k];
    if (!toile) {
      return;
    }
    const pixels = lumPixels(instant.methode, instant.rgb, tMs, bande.leds);
    const ctx = toile.getContext("2d");
    const image = ctx.createImageData(bande.leds, 1);
    pixels.forEach(([r, g, b], i) => {
      image.data.set([r, g, b, 255], 4 * i);
    });
    ctx.putImageData(image, 0, 0);
  });
}

liaison.surLumieres = recevoirLumieres;

// --- Bugs joués (lot I0) : jeu manuel pour le visuel de David ----------------------------
// Liste lue sur GET /api/bugs-joues (bugs ACCEPTÉS par le contrat, refusés avec raisons) ;
// chaque bouton publie `animation` <id> (bouton catalogue). Aucun sélecteur ici (lot I1).

async function installerBugs() {
  $("bugs-couper").addEventListener("click", () => {
    if (state.isWriter) {
      envoyerSaisie("animation", false, $("bugs-couper"));
    }
  });
  let inventaire;
  try {
    const reponse = await fetch(urlHttp("/api/bugs-joues"), { cache: "no-store" });
    if (!reponse.ok) {
      throw new Error("HTTP " + reponse.status);
    }
    inventaire = await reponse.json();
  } catch (e) {
    logErreur("liste des bugs joués illisible : " + e.message);
    return;
  }
  const groupe = $("groupe-bugs");
  inventaire.acceptes.forEach((bug) => {
    const btn = creerBoutonCatalogue("animation", bug.id, bug.id.replaceAll("_", " "));
    btn.title = bug.desc + " — " + bug.duree_s + " s, classe " + bug.classe
        + (bug.direction ? " ; ensuite : « " + bug.direction + " »" : "");
    btn.disabled = !state.isWriter;
    groupe.appendChild(btn);
  });
  const refus = $("bugs-refuses");
  refus.hidden = inventaire.refuses.length === 0;
  refus.textContent = inventaire.refuses.map((r) => "refusé : " + r.chemin + " — " + r.erreurs.join(" ; ")).join("\n");
}

// --- Conversation : flux chat_transcript ------------------------------------------

function ajouterReplique(replique) {
  // Contrat : {"role": "david"|"didier", "text": …, "t_ms": …}. Autre chose =
  // bug du publieur : on le dit dans le journal d'erreurs au lieu de l'avaler.
  // On ne recopie JAMAIS le texte d'une réplique refusée : ce qui n'est pas
  // une réplique de David ou de Didier n'a rien à faire à l'écran.
  if (replique === null || typeof replique !== "object"
      || !Object.hasOwn(ROLES, replique.role) || typeof replique.text !== "string") {
    logErreur("réplique ignorée (rôle : "
        + JSON.stringify(replique === null || typeof replique !== "object" ? null : replique.role) + ")");
    return;
  }
  const role = document.createElement("span");
  role.className = "scene-msg-role";
  // Heure de RÉCEPTION (le serveur ne porte pas d'horloge murale fiable).
  role.textContent = ROLES[replique.role] + " · " + new Date().toLocaleTimeString();
  // textContent, jamais innerHTML : le texte vient du LLM / du micro, un payload
  // contenant du HTML ne doit pas pouvoir s'injecter dans la page.
  const texte = document.createElement("span");
  texte.textContent = replique.text;
  const li = document.createElement("li");
  li.className = "scene-msg scene-msg-" + replique.role;
  li.append(role, texte);

  const fil = $("scene-fil");
  // Mesuré AVANT l'ajout : après, la hauteur a déjà grandi.
  const alaFin = fil.scrollHeight - fil.scrollTop - fil.clientHeight < FIL_BAS_PX;
  fil.appendChild(li);
  while (fil.children.length > FIL_MAX) {
    fil.firstChild.remove();
  }
  if (alaFin) {
    fil.scrollTop = fil.scrollHeight;
  }
}

liaison.surFeed = (msg) => {
  if (msg.topic === "chat_transcript") {
    ajouterReplique(msg.msg);
  } else if (msg.topic === "chat_hearing") {
    ajouterEntendu(msg.msg);
  } else if (msg.topic === "jeu/journal") {
    ajouterLigneJeu(msg.msg);
  } else if (msg.topic === "chat_situation") {
    afficherSituation(msg.msg);
  } else if (msg.topic === "chat_prompt") {
    afficherPrompt(msg.msg);
  } else if (msg.topic === "rehearsal/journal") {
    ajouterEvenementRegisseur(msg.msg);
  } else if (msg.topic === "data_edit_result") {
    surVerdictEdition(msg.msg);
  } else if (msg.topic === "validation_sim") {
    surVerdictPorte(msg.msg);
  } else if (msg.topic === "roues_refusees") {
    surRouesRefusees(msg.msg);
  }
};

// --- Saisies : texte soufflé, consigne de jeu --------------------------------------

// Même mécanique que le bouton catalogue : le flash vient de l'ack serveur.
function envoyerSaisie(topic, valeur, bouton) {
  envoyerCmd(topic, valeur);
  state.attenteAck[topic] = bouton;
  state.dernierBouton = bouton;
}

$("scene-form-texte").addEventListener("submit", (event) => {
  event.preventDefault();
  const champ = $("scene-texte");
  const texte = champ.value.trim();
  if (!state.isWriter || texte === "") {
    return;
  }
  envoyerSaisie("chat_text", texte, event.currentTarget.querySelector("button"));
  champ.value = "";
});

$("scene-form-consigne").addEventListener("submit", (event) => {
  event.preventDefault();
  const texte = $("scene-consigne").value.trim();
  if (!state.isWriter || texte === "") {
    return;
  }
  // Le champ GARDE le texte posé : c'est la seule mémoire de la consigne active
  // (la page ne la relit pas, cf. l'en-tête).
  envoyerSaisie("chat_instruction", texte, event.currentTarget.querySelector("button"));
});

$("scene-consigne-lever").addEventListener("click", () => {
  if (!state.isWriter) {
    return;
  }
  // "" = consigne levée (contrat chat_instruction).
  envoyerSaisie("chat_instruction", "", $("scene-consigne-lever"));
  $("scene-consigne").value = "";
});

// --- Ticket « Noter un problème » (08/11) ------------------------------------------
// Hors whitelist et SANS la main : pas de garde isWriter ici, volontairement. Le champ
// n'est vidé qu'à l'ack (fichier réellement écrit) : sur un err, le texte reste pour
// réessayer au lieu d'être perdu.
let ticketEnAttente = false;
$("form-ticket").addEventListener("submit", (event) => {
  event.preventDefault();
  const texte = $("ticket-texte").value.trim();
  if (texte === "") {
    return;
  }
  const bouton = event.currentTarget.querySelector("button");
  state.attenteAck.ticket = bouton;
  state.dernierBouton = bouton;
  ticketEnAttente = true;
  envoyer({ type: "ticket", texte: texte });
});

function viderTicketSiAcquitte(msg) {
  if (ticketEnAttente && msg.type === "ack" && msg.topic === "ticket") {
    $("ticket-texte").value = "";
    ticketEnAttente = false;
  } else if (ticketEnAttente && msg.type === "err") {
    ticketEnAttente = false;
  }
}

// Un seul crochet ack/err pour la page : le ticket, puis l'éditeur (L1d-3).
liaison.surReponse = (msg) => {
  viderTicketSiAcquitte(msg);
  surReponseEditeur(msg);
  surReponseRearmer(msg);
};

// --- Corps sûr (lot A0-5, 24/11) : état + « Réarmer » ---------------------------------
// corps_sur/etat (latché, JSON du nœud, publié à CHAQUE CHANGEMENT seulement : la page montre
// le dernier état publié, elle ne sait pas si le nœud est mort depuis) :
// {"etat", "cause", "zone", "d_min_m", "vue", "superviseur", "temoin", "terrain"}.
// Libellés : spec A0 §5.5-5.6 (garde.py). Le bouton n'est actif qu'en VERROU et avec la main.

const CORPS_SUR_ETATS = {
  ARME: ["armé", "badge-on"],
  DEMARRAGE: ["démarrage", "badge-off"],
  VERROU: ["VERROU", "badge-alerte"],
  PAUSE_DUREE: ["pause (durée bornée)", "badge-alerte"],
};
const CORPS_SUR_CAUSES = {
  e_stop: "arrêt d'urgence",
  capteur_absent: "lidar absent",
  capteur_perdu: "lidar perdu",
  superviseur_absent: "superviseur absent",
  superviseur_perdu: "superviseur perdu",
  sante_en_cours: "lidar en vérification",
};
// Après un « Réarmer », l'état doit passer ARME : sinon le nœud a refusé (cause encore là).
const CORPS_SUR_VERDICT_MS = 2500;
const corpsSur = { etat: null, demande: null };

function texteCorpsSur(e) {
  const zone = e.zone ? "zone " + e.zone : "";
  const dMin = typeof e.d_min_m === "number" ? "obstacle le plus proche " + e.d_min_m.toFixed(2) + " m" : "rien vu";
  const vues = e.vue && typeof e.vue === "object"
    ? Object.keys(e.vue).filter((k) => e.vue[k] === true) : [];
  return [zone, dMin, "vu : " + (vues.length ? vues.join(", ") : "rien")].filter(Boolean).join(" · ");
}

function afficherCorpsSur(msg) {
  const e = lireJson(valeurTopic(msg.topics, "corps_sur/etat"));
  if (e === null || typeof e !== "object") {
    return;
  }
  corpsSur.etat = e;
  const [libelle, classe] = CORPS_SUR_ETATS[e.etat] || [String(e.etat), "badge-off"];
  const cause = e.cause ? " — " + (CORPS_SUR_CAUSES[e.cause] || e.cause) : "";
  const badge = $("corps-sur-etat");
  badge.textContent = libelle + cause;
  badge.className = "badge " + classe;
  if (corpsSur.demande === null) {
    $("corps-sur-detail").textContent = texteCorpsSur(e);
  }
  majBoutonRearmer();
}

// Un err du PONT pendant la demande (main perdue…) est le verdict : ne pas laisser croire, 2,5 s
// plus tard, que le nœud a refusé pour sa cause. (Un err n'a pas de topic : attribué à la
// demande en cours, comme pour l'éditeur.)
function surReponseRearmer(msg) {
  if (corpsSur.demande === null || msg.type !== "err") {
    return;
  }
  clearTimeout(corpsSur.demande);
  corpsSur.demande = null;
  $("corps-sur-detail").textContent = "réarmement refusé par le pont : " + msg.reason;
  majBoutonRearmer();
}

// Pourquoi « Réarmer » est inactif (lot S3, 28/11) : un bouton grisé muet laissait croire à une
// panne (séance du 24/11). Fonction PURE (jouée par node dans test_web_protocol.py) : "" = actif.
// Elle ne décide RIEN : la règle reste la ligne `disabled` de majBoutonRearmer, et le pont
// refuse de toute façon sans la main, le nœud sans VERROU ni cause disparue.
function raisonRearmerInactif(ecrivain, etat, demandeEnCours) {
  if (!ecrivain) {
    return "prends la main d'abord pour réarmer";
  }
  if (demandeEnCours) {
    return "";  // la ligne de détail dit déjà « réarmement demandé… »
  }
  if (etat === null) {
    return "rien à réarmer : aucun état reçu du corps sûr";
  }
  if (etat === "VERROU") {
    return "";
  }
  if (etat === "ARME") {
    return "rien à réarmer : le corps sûr est armé";
  }
  if (etat === "DEMARRAGE") {
    return "rien à réarmer : au démarrage, il s'arme seul dès que la cause disparaît";
  }
  return "rien à réarmer : Réarmer ne sert qu'en VERROU";
}

const TITRE_REARMER = "lève un VERROU si sa cause a disparu (lidar sain, pas d'arrêt d'urgence)";

function majBoutonRearmer() {
  const verrou = corpsSur.etat !== null && corpsSur.etat.etat === "VERROU";
  $("corps-sur-rearmer").disabled = !(state.isWriter && verrou && corpsSur.demande === null);
  const raison = raisonRearmerInactif(state.isWriter, corpsSur.etat === null ? null : corpsSur.etat.etat,
                                      corpsSur.demande !== null);
  $("corps-sur-raison").textContent = raison;
  $("corps-sur-rearmer").title = raison ? "inactif : " + raison : TITRE_REARMER;
}

$("corps-sur-rearmer").addEventListener("click", (event) => {
  if (!state.isWriter) {
    return;
  }
  state.attenteAck.corps_sur_rearmer = event.currentTarget;
  state.dernierBouton = event.currentTarget;
  $("corps-sur-detail").textContent = "réarmement demandé…";
  corpsSur.demande = setTimeout(() => {
    corpsSur.demande = null;
    const e = corpsSur.etat || {};
    $("corps-sur-detail").textContent = e.etat === "ARME" ? "réarmé · " + texteCorpsSur(e)
      : "réarmement refusé : cause encore là (" + (CORPS_SUR_CAUSES[e.cause] || e.cause || "?") + ")";
    majBoutonRearmer();
  }, CORPS_SUR_VERDICT_MS);
  majBoutonRearmer();
  envoyer({ type: "corps_sur_rearmer" });
});

// --- Vitesse de la route (SIM-ONLY, visible si hello.rehearsal) ---------------------

function vitesseChoisie() {
  // Arrondi au pas ET borné : la valeur du curseur est une chaîne, et 0.15 peut
  // sortir en 0.15000000000000002 selon le calcul -- on envoie un nombre propre.
  const brute = Number($("scene-vitesse").value);
  return Math.round(clamp(brute, 0, 1) * VITESSE_PAR_UNITE) / VITESSE_PAR_UNITE;
}

// Pendant le glissé : libellé seulement, RIEN n'est envoyé.
$("scene-vitesse").addEventListener("input", () => {
  $("scene-vitesse-val").textContent = Math.round(vitesseChoisie() * 100) + " %";
});

// Au relâchement ("change") : une seule consigne, nombre JSON (0..1).
$("scene-vitesse").addEventListener("change", () => {
  if (!state.isWriter) {
    return;
  }
  envoyerSaisie("route_speed", vitesseChoisie(), $("scene-vitesse"));
});

// --- Visage LED (flux MJPEG de face_sim) --------------------------------------------

function urlVisageParDefaut() {
  return "http://" + location.hostname + ":" + PORT_VISAGE + "/stream";
}

function urlVisage() {
  return localStorage.getItem(CLE_URL_VISAGE) || urlVisageParDefaut();
}

// http(s) seulement : une adresse mémorisée part telle quelle dans <img src>.
function urlVisageValide(texte) {
  try {
    const url = new URL(texte);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch (e) {
    return false;
  }
}

let fluxVisage = null;

// Flux perception (lecture seule) : créé ici, chargé par surLiaison à l'annonce.
let fluxPerception = null;

// Flux « vu de l'extérieur » (lecture seule) : même mécanique que la perception.
let fluxExterieur = null;

function installerExterieur() {
  fluxExterieur = creerFluxMjpeg("exterieur", "exterieur-placeholder",
                                 () => urlHttp("/exterior?ts=" + Date.now()));
  fluxExterieur.charge = false;
  $("btn-exterieur-refresh").addEventListener("click", () => fluxExterieur.charger());
}

function installerPerception() {
  fluxPerception = creerFluxMjpeg("perception", "perception-placeholder",
                                  () => urlHttp("/perception?ts=" + Date.now()));
  fluxPerception.charge = false;
  $("btn-perception-refresh").addEventListener("click", () => fluxPerception.charger());
}

function installerVisage() {
  const champ = $("scene-visage-url");
  champ.value = urlVisage();
  // Cache-buster comme la vidéo : relancer un flux tombé. L'adresse mémorisée est
  // toujours validée à la saisie (ci-dessous), donc new URL() n'échoue pas.
  fluxVisage = creerFluxMjpeg("scene-visage", "scene-visage-placeholder", () => {
    const url = new URL(urlVisage());
    url.searchParams.set("ts", Date.now());
    return url.toString();
  });
  $("scene-visage-refresh").addEventListener("click", () => fluxVisage.charger());
  // L'adresse ne sert qu'une fois : rangée derrière ⚙ (spec refonte, D7).
  $("scene-visage-reglage").addEventListener("click", (event) => {
    event.stopPropagation();   // ne pas promouvoir la vignette au passage
    $("scene-form-visage").hidden = !$("scene-form-visage").hidden;
  });

  $("scene-form-visage").addEventListener("submit", (event) => {
    event.preventDefault();
    const saisie = champ.value.trim();
    if (saisie === "") {
      // Champ vidé = retour à l'adresse par défaut.
      localStorage.removeItem(CLE_URL_VISAGE);
      champ.value = urlVisageParDefaut();
    } else if (urlVisageValide(saisie)) {
      localStorage.setItem(CLE_URL_VISAGE, saisie);
    } else {
      logErreur("adresse du flux visage invalide (http://hôte:port/chemin) : " + saisie);
      return;
    }
    $("scene-form-visage").hidden = true;
    fluxVisage.charger();
  });
  fluxVisage.charger();
}

// --- Panneau « Jeu » : le sélecteur de jeu (lot A1, SIM-ONLY) ------------------------
// Contrat : theatre-robot/packages/didier_jeu/README.md. L'intention arrive par `state`
// (toutes les 2 s, latchée côté sélecteur) : la barre de temps se décompte ICI entre
// deux états, sur reste_ms. Le journal arrive par le flux (une ligne par message).

const JEU_JOURNAL_MAX = 20;
const JEU_PRESENCE_MS = 500;   // battement « presence » : 2 Hz (spec A1 §4)
const JAUGES = [["ennui", "ennui"], ["curiosite", "curiosité"], ["lubie", "lubie"],
                ["fatigue", "fatigue"], ["pression_route", "pression de route"]];
// Témoin hors DOM : l'ack d'un battement flashe CET élément, pas le badge
// d'écriture (sinon il clignoterait deux fois par seconde).
const temoinPresence = document.createElement("span");
// total : premier reste_ms vu pour une échéance (fin_prevue_ms) = durée de la
// barre ; l'intention ne porte pas la durée totale de l'action.
const jeu = { intention: null, recuA: 0, piste: null, objets: "", fin: null, total: 1 };
// État du corps (lot S2a, 27/11) : corps/etat, latché, republié par le sélecteur au plus tard
// toutes les 2 s, et son `t_ms` change à chaque publication. Le `state` du pont arrive toutes
// les 2 s : un brut inchangé depuis CORPS_MUET_MS (péremption de 3 s du contrat + une période du
// state) veut dire un écrivain mort -> la phrase du contrat pour l'état inconnu, jamais l'ancienne.
const CORPS_MUET_MS = 5000;
const CORPS_INCONNU = "Tu ne sais pas où en est ton corps.";
const corps = { brut: null, vuA: 0 };

function lireJson(brut) {
  try {
    return brut === null ? null : JSON.parse(brut);
  } catch (e) {
    return null;
  }
}

function afficherJeu(msg) {
  const intention = lireJson(valeurTopic(msg.topics, "jeu/intention"));
  if (intention !== null && typeof intention === "object") {
    jeu.intention = intention;
    jeu.recuA = Date.now();
    if (intention.fin_prevue_ms !== jeu.fin) {
      jeu.fin = intention.fin_prevue_ms;
      jeu.total = Math.max(1, intention.reste_ms || 1);
    }
    $("jeu-action").textContent = intention.action || "—";
    $("jeu-cible").textContent = intention.cible ? "→ " + intention.cible : "";
    $("jeu-pourquoi").textContent = intention.pourquoi || "";
    $("jeu-pourquoi").title = intention.pourquoi || "";   // la ligne est tronquée
    $("jeu-verrou").hidden = intention.verrou !== true;
    $("jeu-proposition").hidden = !intention.proposition;
    afficherJauges(intention.jauges || {});
  }
  afficherCorps(valeurTopic(msg.topics, "corps/etat"));
  const brutObjets = valeurTopic(msg.topics, "rehearsal/objects");
  if (brutObjets !== null && brutObjets !== jeu.objets) {
    jeu.objets = brutObjets;
    remplirCibles();
  }
}

function afficherCorps(brut) {
  // « Corps : <phrase> » (spec S2 §2) : la phrase telle quelle, par textContent. Jamais reçu, ou
  // muet : l'état inconnu (une page ouverte avant le sélecteur ne doit rien inventer).
  if (brut !== null && brut !== corps.brut) {
    corps.brut = brut;
    corps.vuA = Date.now();
  }
  const e = lireJson(corps.brut);
  const frais = e !== null && typeof e === "object" && typeof e.phrase === "string"
    && Date.now() - corps.vuA <= CORPS_MUET_MS;
  const ligne = $("jeu-corps");
  ligne.textContent = "Corps : " + (frais ? e.phrase : CORPS_INCONNU);
  ligne.title = frais ? (e.marche || "") + " · " + (e.cause || "") : "corps/etat muet ou jamais reçu";
}

function afficherJauges(jauges) {
  // Une rangée de mini-barres : libellé au-dessus, valeur exacte en infobulle.
  const boite = $("jeu-jauges");
  boite.replaceChildren();
  for (const [cle, libelle] of JAUGES) {
    const v = typeof jauges[cle] === "number" ? clamp(jauges[cle], 0, 1) : 0;
    const cas = document.createElement("div");
    cas.className = "jeu-jauge-case";
    cas.title = libelle + " : " + v.toFixed(2);
    const nom = document.createElement("span");
    nom.textContent = libelle;
    const barre = document.createElement("div");
    barre.className = "jeu-jauge";
    const plein = document.createElement("div");
    plein.style.width = Math.round(v * 100) + "%";
    barre.appendChild(plein);
    cas.append(nom, barre);
    boite.appendChild(cas);
  }
}

// Cibles de « va là » : la dernière piste née (journal) puis les objets du régisseur.
function remplirCibles() {
  const choix = $("jeu-cible-va-la");
  const garde = choix.value;
  choix.replaceChildren();
  const ajouter = (valeur, libelle) => {
    const o = document.createElement("option");
    o.value = valeur;
    o.textContent = libelle;
    choix.appendChild(o);
  };
  if (jeu.piste) {
    ajouter(jeu.piste, "piste " + jeu.piste);
  }
  const objets = lireJson(jeu.objets);
  (Array.isArray(objets) ? objets : []).forEach((o) => {
    if (o && typeof o.name === "string") {
      ajouter(o.name, o.name + (o.desc && o.desc !== o.name ? " (" + o.desc + ")" : ""));
    }
  });
  if ([...choix.options].some((o) => o.value === garde)) {
    choix.value = garde;
  }
}

function ajouterLigneJeu(ligne) {
  // Contrat : ligne du journal boîte noire {t_mono_ms, type, payload{pourquoi…}}.
  if (ligne === null || typeof ligne !== "object" || typeof ligne.type !== "string"
      || ligne.payload === null || typeof ligne.payload !== "object") {
    logErreur("ligne de journal du jeu illisible");
    return;
  }
  const p = ligne.payload;
  if (ligne.type === "naissance_piste" && typeof p.piste === "string") {
    jeu.piste = p.piste;
    remplirCibles();
  }
  const li = document.createElement("li");
  li.className = "jeu-" + ligne.type;
  const quoi = [ligne.type, p.action, p.cible].filter((x) => typeof x === "string" && x).join(" ");
  li.textContent = quoi + " — " + (p.pourquoi || "");
  const liste = $("jeu-journal");
  liste.prepend(li);
  while (liste.children.length > JEU_JOURNAL_MAX) {
    liste.lastChild.remove();
  }
}

// --- Coulisses (18/11) : metteur en scène + régisseur, LECTURE SEULE -------------------
// Décision de David du 18/11 : il voit ce que produisent le metteur en scène
// intérieur (chat_situation, chat_prompt en flux ; mission_state latché dans
// `state`) et le régisseur de la répétition (rehearsal/journal, SIM-ONLY, flux).
// Le panneau est ouvert par défaut ; l'état ouvert/fermé est mémorisé : le replier
// permet de s'entraîner à l'aveugle. Tout passe par textContent (les textes
// viennent d'un LLM) ; rien ici n'écrit vers le robot.

const CLE_COULISSES_OUVERT = "sceneCoulissesOuvert";
const COULISSES_JOURNAL_MAX = 30;
const COULISSES_SILENCE_MS = 5000;   // tableau republié à 1 Hz : au-delà, le metteur en scène est muet
const COULISSES_COMPACT_MAX = 120;   // longueur d'un payload sans libellé dédié
// Critères de mission (didier_vision.ai.mission.CRITERIA) -> libellé affiché.
const LIBELLE_CRITERES = { love: "amour", tenderness: "tendresse", friendship: "amitié",
                           speed: "vitesse", strong: "force" };
// texte/changeA : dernier tableau et heure de son dernier CHANGEMENT ; recuA : heure
// de la dernière réception (même sans changement) ; missionBrut : dernier payload rendu.
const coulisses = { texte: null, changeA: 0, recuA: 0, missionBrut: null };

function installerCoulisses() {
  const boite = $("scene-coulisses");
  if (localStorage.getItem(CLE_COULISSES_OUVERT) === "0") {
    boite.open = false;
  }
  boite.addEventListener("toggle", () => {
    localStorage.setItem(CLE_COULISSES_OUVERT, boite.open ? "1" : "0");
  });
  setInterval(majAgeSituation, 1000);
}

// « [Titre] contenu » -> <div><strong>[Titre]</strong> contenu</div> ; une ligne sans
// titre reste du texte simple.
function ligneSection(ligne) {
  const div = document.createElement("div");
  const m = /^(\[[^\]]+\])\s*(.*)$/.exec(ligne);
  if (m === null) {
    div.textContent = ligne;
    return div;
  }
  const titre = document.createElement("strong");
  titre.textContent = m[1];
  div.append(titre, " " + m[2]);
  return div;
}

// Contrat chat_situation : {"text": sections séparées par des retours ligne, "t_ms"}.
// Republié à 1 Hz sans changement : on ne reconstruit le DOM que si le texte change.
function afficherSituation(sit) {
  if (sit === null || typeof sit !== "object" || typeof sit.text !== "string") {
    logErreur("tableau de situation illisible");
    return;
  }
  const maintenant = Date.now();
  coulisses.recuA = maintenant;
  if (sit.text !== coulisses.texte) {
    coulisses.texte = sit.text;
    coulisses.changeA = maintenant;
    const lignes = sit.text.split("\n").filter((l) => l.trim() !== "");
    const zone = $("coulisses-situation");
    if (lignes.length === 0) {
      zone.textContent = "tableau de situation vide";
    } else {
      zone.replaceChildren(...lignes.map(ligneSection));
    }
  }
  majAgeSituation();
}

// L'âge est celui du dernier CHANGEMENT ; si plus rien n'arrive, on le dit (un
// tableau figé ne doit pas passer pour un tableau frais).
function majAgeSituation() {
  if (coulisses.texte === null) {
    return;
  }
  const maintenant = Date.now();
  let texte = "tableau modifié il y a " + Math.floor((maintenant - coulisses.changeA) / 1000) + " s";
  if (maintenant - coulisses.recuA > COULISSES_SILENCE_MS) {
    texte += " — plus de nouvelles du metteur en scène depuis "
        + Math.floor((maintenant - coulisses.recuA) / 1000) + " s";
  }
  $("coulisses-age").textContent = texte;
}

// Contrat chat_prompt : {"direction", "raison"} (tour spontané). Horodaté à la réception.
function afficherPrompt(prompt) {
  if (prompt === null || typeof prompt !== "object" || typeof prompt.direction !== "string") {
    logErreur("prise de parole spontanée illisible");
    return;
  }
  $("coulisses-prompt").textContent = "prise de parole spontanée à " + new Date().toLocaleTimeString()
      + " : " + prompt.direction + (prompt.raison ? " — raison : " + prompt.raison : "");
}

// mission_state (latché, lu dans `state` toutes les 2 s) : {"destination",
// "criteres": {nom: {"valeur","par","guide"} | null}, "guides": [{"nom",
// "signalement","guide"}], "indication"} (MissionState.to_dict). Reconstruit
// seulement si le payload change.
function afficherMission(msg) {
  const brut = valeurTopic(msg.topics, "mission_state");
  if (brut === null || brut === coulisses.missionBrut) {
    return;
  }
  const m = lireJson(brut);
  if (m === null || typeof m !== "object") {
    return;
  }
  coulisses.missionBrut = brut;
  const lignes = ["Mission : trouver " + (m.destination || "?")];
  Object.entries(m.criteres || {}).forEach(([nom, v]) => {
    const libelle = LIBELLE_CRITERES[nom] || nom;
    lignes.push(v && typeof v === "object"
      ? "✔ " + libelle + " : « " + v.valeur + " » (par " + v.par + ", guide n°" + v.guide + ")"
      : "· " + libelle + " : à trouver");
  });
  if (Array.isArray(m.guides) && m.guides.length > 0) {
    lignes.push("Guides : " + m.guides.map((g) => g.nom + (g.signalement ? " (" + g.signalement + ")" : "")).join(", "));
  }
  if (m.indication) {
    lignes.push("Dernière indication : " + m.indication);
  }
  $("coulisses-mission").replaceChildren(...lignes.map((l, i) => {
    const div = document.createElement("div");
    div.textContent = l;
    if (i === 0) {
      div.className = "coulisses-mission-titre";
    }
    return div;
  }));
}

function compact(payload) {
  const texte = JSON.stringify(payload);
  return texte.length > COULISSES_COMPACT_MAX ? texte.slice(0, COULISSES_COMPACT_MAX) + "…" : texte;
}

// Types fréquents du journal du régisseur -> phrase française ; les autres : type
// brut + payload compact. Les champs viennent de director_node.py (log(...)).
function libelleEvenement(type, p) {
  const bug = (p.id || "?") + " (" + (p.type || "?") + ")";
  const avec = (base, suite) => (suite ? base + " — " + suite : base);
  switch (type) {
    case "fault_start":
      return "BUG " + bug + (typeof p.text === "string" ? " : « " + p.text + " »" : "");
    case "fault_stop":
      return avec("fin du bug " + bug, p.closed_by ? "fermé par " + p.closed_by : "");
    case "fault_skip":
      return "bug " + bug + " sauté";
    case "fault_error":
      return avec("ERREUR sur le bug " + bug, p.error);
    case "poi_enter":
      return "arrive à « " + p.poi + " »";
    case "poi_exit":
      return "quitte « " + p.poi + " »";
    case "poi_enter_ignored":
      return avec("arrivée à « " + p.poi + " » ignorée", p.reason);
    case "lubie_skipped":
      return avec("lubie sautée à « " + p.poi + " »", p.reason);
    case "scenario_start":
      return "scénario « " + p.name + " » démarré (graine " + p.seed + ")";
    case "scenario_end":
      return "scénario terminé" + (p.status === undefined ? "" : " : " + compact(p.status));
    case "scenario_abort":
      return avec("scénario interrompu", p.cmd);
    case "voice_move":
      return avec("à la voix : " + p.cmd + " → " + p.effect, p.reason);
    case "aller_voir":
      return avec("aller voir « " + p.objet + " » → " + p.effect, p.reason);
    case "goto_result":
      return avec("manœuvre « " + (p.name || "?") + " » : " + p.result, p.reason);
    default:
      return type + " " + compact(p);
  }
}

// Contrat rehearsal/journal : {"type", "payload", "t_ms"}. Plus récent EN BAS ; on
// suit le bas seulement si l'on y était (comme le fil de conversation).
function ajouterEvenementRegisseur(ev) {
  if (ev === null || typeof ev !== "object" || typeof ev.type !== "string") {
    logErreur("événement du régisseur illisible");
    return;
  }
  const p = ev.payload !== null && typeof ev.payload === "object" ? ev.payload : {};
  const heure = new Date(Number.isFinite(ev.t_ms) ? ev.t_ms : Date.now()).toLocaleTimeString();
  const li = document.createElement("li");
  // Classes tirées d'une liste fermée, jamais du type reçu.
  if (ev.type === "fault_start") {
    li.className = "coulisses-bug";
  } else if (ev.type === "fault_error") {
    li.className = "coulisses-erreur";
  }
  li.textContent = heure + " · " + libelleEvenement(ev.type, p);
  const liste = $("coulisses-journal");
  const alaFin = liste.scrollHeight - liste.scrollTop - liste.clientHeight < FIL_BAS_PX;
  liste.appendChild(li);
  while (liste.children.length > COULISSES_JOURNAL_MAX) {
    liste.firstChild.remove();
  }
  if (alaFin) {
    liste.scrollTop = liste.scrollHeight;
  }
}

function envoyerJeu(cmd, bouton) {
  if (!state.isWriter) {
    return;
  }
  const ordre = { cmd: cmd, presence: true };
  if (cmd === "va_la") {
    ordre.cible = $("jeu-cible-va-la").value;
    if (!ordre.cible) {
      logErreur("va là : aucune cible (ni piste vue ni objet connu)");
      return;
    }
  } else if (cmd === "ignore" && jeu.intention && jeu.intention.cible) {
    ordre.cible = jeu.intention.cible;
  }
  envoyerSaisie("jeu/console", ordre, bouton);
}

document.querySelectorAll(".jeu-bouton").forEach((bouton) => {
  bouton.addEventListener("click", () => envoyerJeu(bouton.dataset.jeu, bouton));
});

// Battement : seulement si on a la main, si la répétition est annoncée et si
// l'onglet est VISIBLE (un onglet caché ne surveille rien — spec A1 §5).
setInterval(() => {
  if (!state.isWriter || !state.rehearsal || document.visibilityState !== "visible") {
    return;
  }
  if (!state.attenteAck["jeu/console"]) {
    state.attenteAck["jeu/console"] = temoinPresence;
  }
  envoyerCmd("jeu/console", { presence: true });
}, JEU_PRESENCE_MS);

// Barre de temps : décompte local de reste_ms entre deux `state`.
setInterval(() => {
  const i = jeu.intention;
  const barre = $("jeu-barre-temps");
  if (!i || typeof i.reste_ms !== "number") {
    barre.style.width = "0";
    return;
  }
  const reste = Math.max(0, i.reste_ms - (Date.now() - jeu.recuA));
  barre.style.width = Math.round(clamp(reste / jeu.total, 0, 1) * 100) + "%";
}, 200);

afficherJauges({});

// --- Éditeur des données (lot L1d-3, spec L1 « L1d » décisions 11 et 12) -------------
// L'outil de RÉGLAGE : texte JSON + Envoyer + verdict, envoi d'image, Rejouer. Une seule
// voie d'écriture : le type WebSocket data_edit, relayé par le pont sur le topic data_edit,
// jugé et écrit par le robot (data_edit_node), verdict par le flux data_edit_result. La
// page ne juge RIEN (ni contrat, ni taille d'image) hormis un JSON illisible : erreur
// locale, rien n'est envoyé. Un futur éditeur en pistes passera par le même protocole.
// Lecture : GET /api/data (liste avec états de la porte sim, contenu + sha256).

const EDITEUR_ATTENTE_MS = 5000;   // pas de verdict du même id en 5 s = « pas de réponse du robot »
// Le topic qui JOUE chaque famille (bouton Rejouer, par le cmd existant) ; rien pour une brique.
const EDITEUR_REJOUER = { sequence: "animation", expression: "face", lumiere: "robot_lights" };
const LIBELLE_REJEU = { a_jour: "rejouée", a_faire: "à rejouer" };
const LIBELLE_ROUES = { a_faire: "roues à valider", heritee: "roues héritées" };
const LIBELLE_AVERTISSEMENT = {
  a_rejouer_en_sim: "à rejouer en sim",
  roues_a_valider_en_sim: "roues à valider en sim",
};

// charge : ce que « Charger » a lu ({kind, name, sha256}) -> Envoyer fait un replace avec
// ce sha si le nom n'a pas changé, sinon un create. attentes : id -> minuterie des 5 s.
// enAttenteAck : l'id envoyé que le pont n'a pas encore acquitté (un err lui revient).
const editeur = { elements: {}, charge: null, attentes: {}, enAttenteAck: null, image: null };

function familleEditeur() {
  return $("editeur-famille").value;
}

function nomEditeur() {
  return $("editeur-nom").value.trim();
}

function nouvelIdEdition() {
  // Contrat du robot : 1 à 64 caractères [A-Za-z0-9_-].
  return "page-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
}

function afficherVerdictEditeur(texte, ok) {
  const ligne = $("editeur-verdict");
  ligne.textContent = texte;
  ligne.className = "scene-editeur-verdict " + (ok ? "ok" : "ko");
}

function majEditeurVisible() {
  const panneau = $("scene-editeur");
  const montrer = Boolean(state.dataEdit);
  if (montrer && panneau.hidden && panneau.open) {
    rafraichirListe();
  }
  panneau.hidden = !montrer;
  majBoutonValiderRoues();
}

// --- Lecture (GET /api/data) ---

async function lireApi(kind, name) {
  let chemin = "/api/data?kind=" + encodeURIComponent(kind);
  if (name !== undefined) {
    chemin += "&name=" + encodeURIComponent(name);
  }
  const reponse = await fetch(urlHttp(chemin), { cache: "no-store" });
  if (reponse.status === 404) {
    return null;
  }
  if (!reponse.ok) {
    throw new Error("HTTP " + reponse.status + " : " + (await reponse.text()));
  }
  return reponse.json();
}

function libelleElement(element) {
  const etats = [];
  if (state.validationSim) {
    if (LIBELLE_REJEU[element.rejeu]) {
      etats.push(LIBELLE_REJEU[element.rejeu]);
    }
    if (LIBELLE_ROUES[element.roues]) {
      etats.push(LIBELLE_ROUES[element.roues]);
    }
  }
  return etats.length ? element.name + " — " + etats.join(", ") : element.name;
}

async function rafraichirListe() {
  const kind = familleEditeur();
  let elements;
  try {
    elements = (await lireApi(kind)) || [];
  } catch (e) {
    logErreur("éditeur : liste illisible (" + e.message + ")");
    return;
  }
  if (kind !== familleEditeur()) {
    return;   // la famille a changé pendant la lecture : la réponse suivante gagne
  }
  const liste = $("editeur-liste");
  const choisi = liste.value;
  editeur.elements = {};
  liste.replaceChildren();
  for (const element of elements) {
    editeur.elements[element.name] = element;
    const option = document.createElement("option");
    option.value = element.name;
    option.textContent = libelleElement(element);   // textContent : jamais d'HTML injecté
    liste.appendChild(option);
  }
  if (Object.hasOwn(editeur.elements, choisi)) {
    liste.value = choisi;
  }
  majBoutonValiderRoues();
}

async function chargerElement() {
  const kind = familleEditeur();
  const name = $("editeur-liste").value;
  if (!name) {
    return;
  }
  let element;
  try {
    element = await lireApi(kind, name);
  } catch (e) {
    afficherVerdictEditeur("lecture impossible : " + e.message, false);
    return;
  }
  if (element === null) {
    afficherVerdictEditeur(name + " : absent du robot", false);
    return;
  }
  editeur.charge = { kind: kind, name: element.name, sha256: element.sha256 };
  $("editeur-nom").value = element.name;
  $("editeur-texte").value = JSON.stringify(element.content, null, 4);
  $("editeur-verdict").textContent = "";
  majBoutonValiderRoues();
}

// --- Envoi (type WebSocket data_edit) ---

function envoyerEdition(demande, bouton) {
  state.attenteAck.data_edit = bouton;
  state.dernierBouton = bouton;
  editeur.enAttenteAck = demande.id;
  editeur.attentes[demande.id] = setTimeout(() => {
    delete editeur.attentes[demande.id];
    afficherVerdictEditeur(demande.name + " : pas de réponse du robot (" + EDITEUR_ATTENTE_MS / 1000 + " s)", false);
  }, EDITEUR_ATTENTE_MS);
  envoyer({ type: "data_edit", demande: demande });
}

function envoyerTexte() {
  if (!state.isWriter) {
    return;
  }
  const kind = familleEditeur();
  const name = nomEditeur();
  let contenu;
  try {
    contenu = JSON.parse($("editeur-texte").value);
  } catch (e) {
    afficherVerdictEditeur("JSON illisible, rien n'est envoyé : " + e.message, false);
    return;
  }
  const demande = { id: nouvelIdEdition(), kind: kind, mode: "create", name: name, content: contenu };
  const c = editeur.charge;
  if (c && c.kind === kind && c.name === name) {
    demande.mode = "replace";
    demande.base_sha256 = c.sha256;
  }
  afficherVerdictEditeur(name + " : envoyé, en attente du robot…", true);
  envoyerEdition(demande, $("editeur-envoyer"));
}

function texteVerdict(v) {
  let texte = v.code + " — " + v.kind + " " + v.name;
  if (Array.isArray(v.avertissements) && v.avertissements.length) {
    texte += " · " + v.avertissements.map((a) => LIBELLE_AVERTISSEMENT[a] || a).join(", ");
  }
  if (Array.isArray(v.detail) && v.detail.length) {
    texte += "\n" + v.detail.join("\n");
  }
  return texte;
}

function surVerdictEdition(v) {
  if (v === null || typeof v !== "object") {
    return;
  }
  if (Object.hasOwn(editeur.attentes, v.id)) {
    clearTimeout(editeur.attentes[v.id]);
    delete editeur.attentes[v.id];
    afficherVerdictEditeur(texteVerdict(v), v.ok === true);
    // Écrit (ou inchangé) : la base des retouches suivantes est la version du robot.
    if (v.ok === true && typeof v.sha256 === "string" && v.kind !== "image") {
      editeur.charge = { kind: v.kind, name: v.name, sha256: v.sha256 };
    }
  }
  // Une retouche venue d'ailleurs (autre onglet, script) change aussi la liste.
  if (v.ok === true && v.kind === familleEditeur() && !$("scene-editeur").hidden) {
    rafraichirListe();
  }
}

// Ack/err du pont pour une demande de l'éditeur : l'ack dit « publiée », le verdict
// suivra ; un err (lecture seule, trop gros, édition désactivée) est le verdict.
function surReponseEditeur(msg) {
  const id = editeur.enAttenteAck;
  if (id === null) {
    return;
  }
  if (msg.type === "ack" && (msg.topic === "data_edit" || msg.topic === "valider_roues")) {
    editeur.enAttenteAck = null;
  } else if (msg.type === "err") {
    editeur.enAttenteAck = null;
    if (Object.hasOwn(editeur.attentes, id)) {
      clearTimeout(editeur.attentes[id]);
      delete editeur.attentes[id];
    }
    afficherVerdictEditeur("refusé par le pont : " + msg.reason, false);
  }
}

// --- Rejouer (cmd existant : animation, face, robot_lights) ---

function rejouer() {
  if (!state.isWriter) {
    return;
  }
  const kind = familleEditeur();
  const name = nomEditeur();
  const bouton = $("editeur-rejouer");
  if (!name || !EDITEUR_REJOUER[kind]) {
    afficherVerdictEditeur(kind === "brique" ? "une brique ne se joue pas seule : rejouer une lumière qui la chaîne"
        : "aucun nom à rejouer", false);
    return;
  }
  // Littéraux par topic (gardes de test_web_protocol.py) ; une séquence se joue par son nom nu.
  if (kind === "sequence") {
    envoyerSaisie("animation", name.split("/").pop(), bouton);
  } else if (kind === "expression") {
    envoyerSaisie("face", name, bouton);
  } else {
    envoyerSaisie("robot_lights", name, bouton);
  }
}

// --- Porte sim : états, validation des roues, refus de jeu ---

function majBoutonValiderRoues() {
  const element = editeur.elements[nomEditeur()];
  $("editeur-valider-roues").hidden = !(state.validationSim && familleEditeur() === "sequence"
      && element && element.rejeu === "a_jour" && element.roues === "a_faire");
}

function validerRoues() {
  if (!state.isWriter) {
    return;
  }
  const id = nouvelIdEdition();
  const name = nomEditeur();
  const bouton = $("editeur-valider-roues");
  state.attenteAck.valider_roues = bouton;
  state.dernierBouton = bouton;
  editeur.enAttenteAck = id;
  editeur.attentes[id] = setTimeout(() => {
    delete editeur.attentes[id];
    afficherVerdictEditeur(name + " : pas de réponse de la porte sim (" + EDITEUR_ATTENTE_MS / 1000 + " s)", false);
  }, EDITEUR_ATTENTE_MS);
  envoyer({ type: "valider_roues", id: id, name: name });
}

function surVerdictPorte(v) {
  if (v === null || typeof v !== "object") {
    return;
  }
  const texte = "porte sim : " + v.code + " — " + v.kind + " " + v.name
      + (Array.isArray(v.detail) && v.detail.length ? "\n" + v.detail.join("\n") : "");
  if (typeof v.id === "string" && Object.hasOwn(editeur.attentes, v.id)) {
    clearTimeout(editeur.attentes[v.id]);
    delete editeur.attentes[v.id];
    afficherVerdictEditeur(texte, v.ok === true);
  } else if (v.kind === familleEditeur() && v.name === nomEditeur()) {
    // Tampon de rejeu de l'élément affiché (posé par l'observateur après Rejouer).
    afficherVerdictEditeur(texte, v.ok === true);
  }
  if (v.kind === familleEditeur() && !$("scene-editeur").hidden) {
    rafraichirListe();
  }
}

function surRouesRefusees(r) {
  // Barrière de jeu (robot) : la piste roues d'une séquence non validée en sim n'a pas joué.
  const nom = r && typeof r === "object" ? r.name : r;
  logErreur("roues non jouées : " + JSON.stringify(nom) + " (" + (r && r.raison || "?") + ")");
}

// --- Envoi d'une image PNG du visage ---

function octetsEnBase64(octets) {
  let binaire = "";
  for (let i = 0; i < octets.length; i += 0x8000) {   // par tranches : pas de pile géante
    binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000));
  }
  return btoa(binaire);
}

async function choisirImage() {
  const fichier = $("editeur-image-fichier").files[0];
  const apercu = $("editeur-image-apercu");
  if (editeur.image && editeur.image.url) {
    URL.revokeObjectURL(editeur.image.url);
  }
  editeur.image = null;
  apercu.hidden = true;
  if (!fichier) {
    return;
  }
  const octets = new Uint8Array(await fichier.arrayBuffer());
  editeur.image = { base64: octetsEnBase64(octets), url: URL.createObjectURL(fichier) };
  apercu.src = editeur.image.url;
  apercu.hidden = false;
  if (!$("editeur-image-nom").value.trim()) {
    $("editeur-image-nom").value = fichier.name.replace(/\.png$/i, "");
  }
}

async function envoyerImage() {
  if (!state.isWriter) {
    return;
  }
  if (!editeur.image) {
    afficherVerdictEditeur("aucun fichier PNG choisi", false);
    return;
  }
  const name = $("editeur-image-zone").value + "/" + $("editeur-image-nom").value.trim();
  const demande = { id: nouvelIdEdition(), kind: "image", mode: "create", name: name,
                    content: editeur.image.base64 };
  // Une image du même nom existe : on la remplace, avec le sha de ce que le robot a.
  try {
    const existante = await lireApi("image", name);
    if (existante !== null) {
      demande.mode = "replace";
      demande.base_sha256 = existante.sha256;
    }
  } catch (e) {
    afficherVerdictEditeur("lecture impossible : " + e.message, false);
    return;
  }
  afficherVerdictEditeur(name + " : image envoyée, en attente du robot…", true);
  envoyerEdition(demande, $("editeur-image-envoyer"));
}

function installerEditeur() {
  $("scene-editeur").addEventListener("toggle", () => {
    if ($("scene-editeur").open) {
      rafraichirListe();
    }
  });
  $("editeur-famille").addEventListener("change", () => {
    editeur.charge = null;
    rafraichirListe();
  });
  $("editeur-charger").addEventListener("click", chargerElement);
  $("editeur-nom").addEventListener("input", majBoutonValiderRoues);
  $("editeur-envoyer").addEventListener("click", envoyerTexte);
  $("editeur-rejouer").addEventListener("click", rejouer);
  $("editeur-valider-roues").addEventListener("click", validerRoues);
  $("editeur-image-fichier").addEventListener("change", choisirImage);
  $("editeur-image-envoyer").addEventListener("click", envoyerImage);
}

// --- Démarrage ------------------------------------------------------------------------

// --- Vue principale et vignettes (spec refonte, D2) ---------------------------
// Quatre tuiles (extérieur, caméra, perception, visage) : une seule est
// « principale » (grande), les autres sont des vignettes. Promouvoir = changer
// une classe CSS, jamais recharger un flux. Le choix est mémorisé ; s'il porte
// sur une tuile que le serveur masque (pas d'extérieur sur le vrai robot,
// perception non annoncée), on retombe sur l'extérieur puis la caméra.
const CLE_VUE_PRINCIPALE = "sceneVuePrincipale";
const VUES_PAR_DEFAUT = ["exterieur", "camera"];

function majVuePrincipale() {
  const tuiles = [...document.querySelectorAll("#scene-media .scene-tuile")];
  const tuile = (vue) => tuiles.find((t) => t.dataset.vue === vue && !t.hidden);
  const voulue = localStorage.getItem(CLE_VUE_PRINCIPALE);
  const choisie = [voulue, ...VUES_PAR_DEFAUT].map(tuile).find(Boolean);
  tuiles.forEach((t) => t.classList.toggle("principale", t === choisie));
}

function installerVues() {
  $("scene-media").addEventListener("click", (event) => {
    // Les boutons (⟳, ⚙) et le formulaire du visage gardent leur propre rôle.
    if (event.target.closest("button, form, input")) {
      return;
    }
    const t = event.target.closest(".scene-tuile");
    if (!t || t.classList.contains("principale")) {
      return;
    }
    localStorage.setItem(CLE_VUE_PRINCIPALE, t.dataset.vue);
    majVuePrincipale();
  });
}

// --- Erreurs récentes dans le bandeau (spec refonte, D8) -----------------------
// logErreur (commun.js, partagé avec la régie) remplit #journal-erreurs ; on ne
// touche pas commun.js : un observateur tient le compteur à jour.
function installerErreurs() {
  const liste = $("journal-erreurs");
  const majCompteur = () => {
    const nb = liste.children.length;
    $("scene-erreurs-nb").textContent = String(nb);
    $("scene-erreurs").hidden = nb === 0;
    if (nb === 0) {
      $("scene-erreurs").open = false;
    }
  };
  new MutationObserver(majCompteur).observe(liste, { childList: true });
  $("scene-erreurs-vider").addEventListener("click", () => liste.replaceChildren());
  majCompteur();
}

// Écran étroit (même seuil que scene.css) : « Préparer » part replié en bas de page.
if (window.matchMedia("(max-width: 899px)").matches) {
  $("scene-preparer").open = false;
}
construirePersonas();
installerErreurs();
installerVues();
installerEditeur();
installerCoulisses();
installerAudio();
// Tout est inerte et la répétition masquée jusqu'au premier hello du serveur.
installerPerception();
installerExterieur();
liaison.surLiaison();
installerVideo();
installerVisage();
installerBugs();
requestAnimationFrame(peindreLumieres);
connecter();
