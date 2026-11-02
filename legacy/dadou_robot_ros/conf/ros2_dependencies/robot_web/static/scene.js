"use strict";
/*
 * Page « scène » de Didier -- caméra | visage LED | conversation, plus les
 * commandes de la répétition. Vanilla JS, pas de framework, pas de build.
 * La liaison (WebSocket, auth, heartbeat, envoi des cmd, bandeau, flux MJPEG,
 * bouton catalogue délégué) vient de commun.js : ici, seulement ce qui est
 * propre à la scène.
 *
 * CE QUE LA PAGE N'AFFICHE JAMAIS : les pannes ni les consignes injectées par le
 * régisseur de la répétition -- David ne voit pas le tirage (étude répétition
 * simulée §13.1). Conséquences de code, à ne pas « améliorer » :
 *  - de `state` (toutes les 2 s) on ne lit que chat_state, persona_state,
 *    route_state, chat_audio_chain (branchement du son, 31/10), rehearsal/state
 *    (séance + arrêt vocal, 31/10 : le régisseur n'y met AUCUNE panne) et
 *    camera_state, camera_source_state et camera_sources ; JAMAIS chat_instruction (le régisseur publie sur le même
 *    topic que la consigne posée ici) ni route_speed (une panne « batterie
 *    faible » y passerait) ;
 *  - le curseur de vitesse est une CONSIGNE sans relecture : il ne se recale
 *    pas sur ce que le robot a reçu ;
 *  - le texte soufflé n'est pas affiché à l'envoi : il apparaît dans le fil
 *    quand Didier l'a ENTENDU (chat_transcript, après d'éventuelles pannes de
 *    compréhension) -- c'est précisément ce que David doit voir.
 */

// Reste sur le pont qui sert la page : une cible mémorisée par la console (ex. le
// vrai Didier) ne doit pas rediriger en silence une page ouverte sur la sim.
liaison.suivreCible = false;

// Personnalités proposées : liste GRAVÉE ici, pas lue du catalogue. Les personas
// vivent côté Pi vision (vision.ai.personas) que le pont web ne connaît pas ; en
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

// camera_state (latché côté vision) -> libellé du badge.
const LIBELLE_ETAT_CAMERA = {
  on: "webcam allumée",
  off: "webcam coupée",
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
  document.querySelectorAll(".bouton-catalogue, #scene-form-texte button, "
      + "#scene-form-consigne button, #scene-vitesse, .jeu-bouton, #jeu-cible-va-la")
    .forEach((el) => { el.disabled = !state.isWriter; });
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
  badge.textContent = valeur === null ? "—" : (libelles[valeur] || valeur);
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
  majBadgeEtat("scene-etat-camera", LIBELLE_ETAT_CAMERA, camera, camera === "on");
  surlignerGroupe("groupe-camera", camera);
  // Coupée : texte « caméra coupée » par-dessus, au lieu de la dernière image figée.
  // État inconnu (null) : on ne masque rien, la webcam n'a pas dit qu'elle était coupée.
  $("perception-coupee").hidden = camera !== "off";

  afficherSourceCamera(valeurTopic(msg.topics, "camera_source_state"),
                       valeurTopic(msg.topics, "camera_sources"));
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
  tete.textContent = new Date().toLocaleTimeString() + " · " + h.moteur + duree + " · " + h.verdict;
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
};

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
    $("jeu-verrou").hidden = intention.verrou !== true;
    $("jeu-proposition").hidden = !intention.proposition;
    const stopGo = $("jeu-stop-go");
    stopGo.dataset.jeu = intention.verrou === true ? "go" : "stop";
    stopGo.textContent = intention.verrou === true ? "Go" : "Stop";
    afficherJauges(intention.jauges || {});
  }
  const brutObjets = valeurTopic(msg.topics, "rehearsal/objects");
  if (brutObjets !== null && brutObjets !== jeu.objets) {
    jeu.objets = brutObjets;
    remplirCibles();
  }
}

function afficherJauges(jauges) {
  const boite = $("jeu-jauges");
  boite.replaceChildren();
  for (const [cle, libelle] of JAUGES) {
    const v = typeof jauges[cle] === "number" ? clamp(jauges[cle], 0, 1) : 0;
    const nom = document.createElement("span");
    nom.textContent = libelle;
    const barre = document.createElement("div");
    barre.className = "jeu-jauge";
    const plein = document.createElement("div");
    plein.style.width = Math.round(v * 100) + "%";
    barre.appendChild(plein);
    const val = document.createElement("span");
    val.textContent = v.toFixed(2);
    boite.append(nom, barre, val);
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

// --- Démarrage ------------------------------------------------------------------------

construirePersonas();
// Tout est inerte et la répétition masquée jusqu'au premier hello du serveur.
installerPerception();
installerExterieur();
liaison.surLiaison();
installerVideo();
installerVisage();
connecter();
