"use strict";
/*
 * Briques COMMUNES aux pages de Didier : console de régie (app.js) et page
 * « scène » (scene.js). Chargé AVANT le script de la page. Vanilla JS, pas de
 * framework, pas de build.
 *
 * Contient tout ce qui touche au contrat protocole de robot_web/web_protocol.py
 * côté navigateur -- connexion + reconnexion, auth, heartbeat/RTT, envoi des cmd,
 * bandeau (mode, connexion, écriture, prise de main, token), journal d'erreurs --
 * plus les flux MJPEG (vidéo, visage) et le bouton « catalogue » (data-topic/data-value).
 * Les constantes numériques ci-dessous sont DUPLIQUÉES volontairement (pas de
 * partage possible entre Python serveur et JS navigateur) -- même choix assumé
 * que robot_drive/wheels_payload.py.
 *
 * CONTRAT avec la page hôte : elle fournit les éléments du bandeau (ids
 * badge-mode, badge-version, badge-connexion, badge-ecriture, rtt, btn-prendre-main, token-box,
 * token-input, btn-token, journal-erreurs) et, pour la vidéo, video,
 * video-placeholder, btn-video-refresh. Ce qui est PROPRE à la page passe par
 * les crochets de `liaison` ci-dessous (tous optionnels), posés AVANT connecter().
 * Aucune page ne redéfinit ces fonctions : une correction de la liaison (auth,
 * reconnexion...) vaut pour toutes.
 */

// Cadence du heartbeat applicatif (alignée sur web_protocol.HEARTBEAT_PERIOD_S).
const HEARTBEAT_PERIOD_S = 1.0;

// Backoff de reconnexion WebSocket : 1 s -> 5 s, doublé à chaque échec.
const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 5000;

// Moyenne glissante du RTT sur les 5 derniers battements.
const RTT_WINDOW = 5;

// --- Réglages et crochets de la page hôte ------------------------------------

const liaison = {
  // true (console de régie) : la cible du pont se choisit et se mémorise
  // (localStorage "cible"). false (page « scène ») : la page reste sur SON
  // origine -- une cible mémorisée par la console (ex. le vrai Didier) ne doit
  // pas rediriger en silence une page ouverte sur la simulation.
  suivreCible: true,
  surLiaison: null,   // () : l'état de liaison a changé (hello, écriture, déconnexion)
  surMode: null,      // (mode) : le badge de mode vient d'être mis à jour
  surEtat: null,      // (msg) : message serveur "state" (toutes les 2 s)
  surFeed: null,      // (msg) : message serveur "feed" (un événement, à chaque message)
};

// --- État global du client --------------------------------------------------

const state = {
  ws: null,
  authSent: false,          // un seul message "auth" envoyé par connexion
  isWriter: false,
  tokenRequired: false,
  driveEnabled: false,      // hello.drive_enabled (WEB_DRIVE=true côté serveur)
  maxLinear: 0,             // plafond serveur affiché (m/s)
  maxAngular: 0,            // plafond serveur affiché (rad/s)
  rehearsal: false,         // hello.rehearsal : topics de répétition acceptés (SIM-ONLY)
  perception: false,        // hello.perception : le serveur sert /perception (lecture seule)
  exterior: false,          // hello.exterior : le serveur sert /exterior (caméra de poursuite sim)
  reconnectDelayMs: RECONNECT_MIN_MS,
  rttSamples: [],           // fenêtre glissante (ms)
  hbTimer: null,
  attenteAck: {},           // topic -> bouton cliqué, flashé à l'ack (pas au clic)
  dernierBouton: null,      // dernier bouton cliqué, flashé rouge sur "err"
};

// --- Utilitaires DOM ---------------------------------------------------------

function $(id) {
  return document.getElementById(id);
}

function clamp(v, lo, hi) {
  return v < lo ? lo : v > hi ? hi : v;
}

function logErreur(message) {
  const ul = $("journal-erreurs");
  const li = document.createElement("li");
  li.textContent = new Date().toLocaleTimeString() + " -- " + message;
  ul.prepend(li);
  while (ul.children.length > 5) {
    ul.lastChild.remove();
  }
}

function flash(element, ok) {
  const classe = ok ? "flash-ok" : "flash-err";
  element.classList.add(classe);
  setTimeout(() => element.classList.remove(classe), 400);
}

// --- Cible : quel pont cette page contrôle ------------------------------------
// La console est UNIQUE (elle peut être servie par n'importe quel pont) et choisit
// sa cible : "" = même origine que la page, sinon une base http://hôte:port.
// Persistée en localStorage pour retrouver sa cible au rechargement. La vérité
// du mode (SIMULATION/ROBOT RÉEL) reste le hello du serveur connecté.

function cibleBase() {
  return liaison.suivreCible ? (localStorage.getItem("cible") || "") : "";
}

function urlHttp(chemin) {
  return cibleBase() + chemin;
}

// --- Connexion WebSocket + reconnexion auto ---------------------------------

function urlWebSocket() {
  const base = cibleBase();
  if (base === "") {
    const protocole = location.protocol === "https:" ? "wss://" : "ws://";
    return protocole + location.host + "/ws";
  }
  return base.replace(/^http/, "ws") + "/ws";
}

function connecter() {
  const ws = new WebSocket(urlWebSocket());
  state.ws = ws;
  state.authSent = false;

  ws.addEventListener("open", () => {
    state.reconnectDelayMs = RECONNECT_MIN_MS; // succès : on repart à 1 s
    majBadgeConnexion(true);
  });

  ws.addEventListener("message", (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch (e) {
      logErreur("message serveur illisible : " + e);
      return;
    }
    traiterMessageServeur(msg);
  });

  ws.addEventListener("close", () => {
    majBadgeConnexion(false);
    arreterHeartbeat();
    planifierReconnexion();
  });

  ws.addEventListener("error", () => {
    // "close" suit toujours "error" sur un WebSocket -- la reconnexion est
    // gérée là-bas, pas besoin de la dupliquer ici.
    logErreur("erreur WebSocket");
  });
}

function planifierReconnexion() {
  setTimeout(connecter, state.reconnectDelayMs);
  state.reconnectDelayMs = Math.min(state.reconnectDelayMs * 2, RECONNECT_MAX_MS);
}

function majBadgeConnexion(connecte) {
  const badge = $("badge-connexion");
  badge.textContent = connecte ? "connecté" : "déconnecté";
  badge.className = "badge " + (connecte ? "badge-on" : "badge-off");
  if (!connecte) {
    state.isWriter = false;
    majBadgeEcriture();
  }
}

// --- Traitement des messages serveur -----------------------------------------

function traiterMessageServeur(msg) {
  switch (msg.type) {
    case "hello":
      traiterHello(msg);
      break;
    case "hb_ack":
      traiterHbAck(msg);
      break;
    case "ack":
      // Le flash arrive à l'ACK serveur, pas au clic : un bouton qui flashe
      // vert = la commande est vraiment partie sur le topic ROS.
      flash(state.attenteAck[msg.topic] || $("badge-ecriture"), true);
      delete state.attenteAck[msg.topic];
      break;
    case "err":
      logErreur(msg.reason);
      flash(state.dernierBouton || $("badge-ecriture"), false);
      break;
    case "state":
      $("badge-connexion").title = msg.clients + " client(s) connecté(s), écriture "
          + (msg.writer_present ? "détenue" : "libre");
      majBadgeVersion(msg.topics?.deploy_sha?.msg);
      liaison.surEtat?.(msg);
      break;
    case "feed":
      // Un événement de flux (ex. chat_transcript). Une page qui ne s'y intéresse
      // pas (la console de régie) l'ignore en silence : ce n'est pas une erreur,
      // le serveur le diffuse à TOUS les clients.
      liaison.surFeed?.(msg);
      break;
    default:
      logErreur("type de message serveur inconnu : " + msg.type);
  }
}

function traiterHello(msg) {
  majBadgeMode(msg.mode, msg.domain_id);
  state.tokenRequired = msg.token_required;
  state.isWriter = msg.writer;
  // Plafonds + autorisation pilotage : l'UI verrouille/déverrouille le pad et
  // affiche les limites (le plafond DUR reste appliqué serveur).
  state.driveEnabled = !!msg.drive_enabled;
  state.maxLinear = msg.max_linear ?? 0;
  state.maxAngular = msg.max_angular ?? 0;
  // Topics de répétition acceptés par CE serveur (absent = ancien serveur = non).
  state.rehearsal = !!msg.rehearsal;
  // Second flux vidéo (ce que voit la perception) : absent = ancien serveur = non.
  state.perception = !!msg.perception;
  state.exterior = !!msg.exterior;  // absent = ancien serveur = non
  majBadgeEcriture();
  demarrerHeartbeatSiWriter();

  if (!state.authSent) {
    state.authSent = true;
    $("token-box").hidden = !msg.token_required;
    if (!msg.token_required) {
      envoyerAuth(null);
    }
    // Si un token est requis, on attend que l'opérateur le saisisse
    // (bouton #btn-token) -- pas d'auto-tentative avec un token vide.
  }
}

function envoyerAuth(token) {
  envoyer({ type: "auth", token: token });
}

function traiterHbAck(msg) {
  const rtt = Date.now() - msg.t;
  state.rttSamples.push(rtt);
  if (state.rttSamples.length > RTT_WINDOW) {
    state.rttSamples.shift();
  }
  const moyenne = state.rttSamples.reduce((a, b) => a + b, 0) / state.rttSamples.length;
  $("rtt").textContent = "RTT " + Math.round(moyenne) + " ms";
}

const CLASSE_BADGE_PAR_MODE = {
  "SIMULATION": "badge-simulation",
  "ROBOT RÉEL": "badge-robot-reel",
};

function majBadgeMode(mode, domainId) {
  const badge = $("badge-mode");
  badge.textContent = mode + " (domain " + domainId + ")";
  // Parenthèse indispensable : "+" est plus prioritaire que "||" en JS, sans
  // elle "badge " + undefined donne "badge undefined" (chaîne TRUTHY) et le
  // fallback badge-inconnu ne se déclenche jamais.
  badge.className = "badge " + (CLASSE_BADGE_PAR_MODE[mode] || "badge-inconnu");
  // Propre à la page (ex. la console prévient qu'en sim les sons sont muets).
  liaison.surMode?.(mode);
}

// Version déployée (topic deploy_sha, lot L1c) : "dev" en sim, sinon les 7
// premiers caractères du sha. Le suffixe "-dirty" (arbre non commité au rsync)
// est CONSERVÉ et passe le badge en alerte : un sha propre mentirait sur ce qui
// tourne vraiment. Masqué tant que le robot n'a rien publié.
function majBadgeVersion(sha) {
  const badge = $("badge-version");
  if (typeof sha !== "string" || sha === "") {
    badge.hidden = true;
    return;
  }
  const sale = sha.endsWith("-dirty");
  const court = sha === "dev" ? "dev" : sha.replace(/-dirty$/, "").slice(0, 7) + (sale ? "-dirty" : "");
  badge.textContent = court;
  badge.title = "version déployée : " + sha;
  badge.className = "badge " + (sale ? "badge-alerte" : "badge-off");
  badge.hidden = false;
}

function majBadgeEcriture() {
  const badge = $("badge-ecriture");
  badge.textContent = state.isWriter ? "écriture" : "lecture seule";
  badge.className = "badge " + (state.isWriter ? "badge-on" : "badge-off");
  // Les boutons d'action sont inertes en lecture seule -- l'UI le reflète (le
  // serveur refuse déjà côté écriture). La liste des boutons dépend de la page :
  // c'est son crochet qui les (dés)active.
  liaison.surLiaison?.();
}

// --- Heartbeat + RTT (tant que la page a l'écriture, spec §5) ---------------

function demarrerHeartbeatSiWriter() {
  arreterHeartbeat();
  if (!state.isWriter) {
    return;
  }
  state.hbTimer = setInterval(() => {
    envoyer({ type: "hb", t: Date.now() });
  }, HEARTBEAT_PERIOD_S * 1000);
}

function arreterHeartbeat() {
  if (state.hbTimer !== null) {
    clearInterval(state.hbTimer);
    state.hbTimer = null;
  }
}

// --- Envoi de commandes -------------------------------------------------------

function envoyer(objet) {
  if (state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify(objet));
  }
}

function envoyerCmd(topic, value, timeMs) {
  envoyer({ type: "cmd", topic: topic, value: value, time: timeMs || 0 });
}

// --- Bandeau : prise de main --------------------------------------------------

$("btn-prendre-main").addEventListener("click", () => {
  if (!confirm("Prendre la main écriture ? Un autre opérateur éventuellement "
      + "connecté repassera en lecture seule.")) {
    return;
  }
  envoyer({ type: "take_control" });
  // La confirmation de prise de main arrive via le prochain "hello".
});

$("btn-token").addEventListener("click", () => {
  envoyerAuth($("token-input").value);
});

// --- Boutons catalogue + gaze : écouteur délégué (data-topic/data-value) -----

function creerBoutonCatalogue(topic, value, libelle) {
  const btn = document.createElement("button");
  btn.className = "bouton-catalogue";
  btn.type = "button";
  btn.dataset.topic = topic;
  btn.dataset.value = value;
  btn.textContent = libelle;
  return btn;
}

document.addEventListener("click", (event) => {
  const btn = event.target.closest(".bouton-catalogue");
  if (btn) {
    envoyerCmd(btn.dataset.topic, btn.dataset.value);
    // Pas de flash ici : il vient de l'ack serveur (sinon un clic "réussi"
    // visuellement peut n'avoir rien publié du tout).
    state.attenteAck[btn.dataset.topic] = btn;
    state.dernierBouton = btn;
  }
});

// --- Flux MJPEG : retour vidéo de la caméra ET visage LED --------------------
// Un <img> sur un flux multipart/x-mixed-replace, son placeholder « pas de
// vidéo » et son ré-essai. Fabrique plutôt que globales : la page « scène »
// porte DEUX flux (caméra + visage) qui ont chacun leurs minuteurs.

// Ré-essai automatique quand le flux est en erreur : sans lui, une page
// ouverte AVANT que la caméra publie (ou pendant un redémarrage de la sim)
// restait sur « pas de vidéo » jusqu'à un clic manuel sur ⟳ -- vécu, pas clair.
const FLUX_RETRY_MS = 5000;
// Sondage de la première frame (cf. PIÈGE Chrome dans surveiller()).
const FLUX_WATCH_MS = 500;

// urlFlux : () -> URL à charger (avec cache-buster : le flux précédent peut être
// en 503 depuis, ou figé ; le serveur répond 503 si aucune frame -> onerror).
function creerFluxMjpeg(idImg, idPlaceholder, urlFlux) {
  const img = $(idImg);
  const placeholder = $(idPlaceholder);
  let retryTimer = null;
  let watchTimer = null;

  function enMarche() {
    // Première frame visible : placeholder masqué, timers de détection/ré-essai
    // arrêtés (le prochain charger() -- ⟳, changement de cible, erreur -- les
    // réarmera).
    placeholder.hidden = true;
    if (watchTimer !== null) {
      clearInterval(watchTimer);
      watchTimer = null;
    }
    if (retryTimer !== null) {
      clearInterval(retryTimer);
      retryTimer = null;
    }
  }

  function surveiller() {
    // PIÈGE Chrome (vécu console « Didier réel », 2026-07-11) : sur un flux
    // multipart/x-mixed-replace, l'événement 'load' de <img> ne se déclenche
    // qu'à la FIN de la réponse — or un MJPEG en marche ne se termine jamais.
    // Résultat : la vidéo tournait DERRIÈRE le placeholder jamais masqué. On
    // détecte donc la première frame décodée par naturalWidth > 0 (remis à 0
    // par le navigateur à chaque changement de src), en sondant à 2 Hz.
    // Firefox, lui, déclenche 'load' par frame : le handler 'load' ci-dessous
    // est conservé (il fait la même chose, juste plus tôt).
    if (watchTimer !== null) {
      clearInterval(watchTimer);
    }
    watchTimer = setInterval(() => {
      if (img.naturalWidth > 0) {
        enMarche();
      }
    }, FLUX_WATCH_MS);
  }

  function charger() {
    img.src = urlFlux();
    surveiller();
  }

  img.addEventListener("load", () => {
    // Firefox : 'load' par frame -> chemin nominal. Chrome : ne se déclenche
    // qu'à la fermeture du flux (cf. surveiller) -- une frame a alors été
    // décodée (naturalWidth > 0), masquer le placeholder reste correct, et le
    // flux fermé sera relancé par ⟳ ou un changement de cible.
    if (img.naturalWidth > 0) {
      enMarche();
    }
  });
  img.addEventListener("error", () => {
    placeholder.hidden = false;
    if (retryTimer === null) {
      retryTimer = setInterval(charger, FLUX_RETRY_MS);
    }
  });

  return { charger };
}

// --- Vidéo (flux MJPEG /video) -----------------------------------------------

let fluxVideo = null;

function chargerVideo() {
  fluxVideo.charger();
}

function installerVideo() {
  fluxVideo = creerFluxMjpeg("video", "video-placeholder",
                             () => urlHttp("/video?ts=" + Date.now()));
  $("btn-video-refresh").addEventListener("click", chargerVideo);
  chargerVideo();
}
