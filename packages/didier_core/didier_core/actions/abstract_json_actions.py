import json
import logging
import os
import random

from dadou_utils_ros.files.files_utils import FilesUtils
from dadou_utils_ros.utils.time_utils import TimeUtils
from didier_core.robot_static import RANDOM_ANIMATION_LOW, RANDOM_ANIMATION_HIGH, LOOP_DURATION, TYPES
from dadou_utils_ros.utils_static import KEY, KEYS, NAME, LOOP, DURATION, BASE_PATH, TYPE, \
    JSON_DIRECTORY
from didier_core.actions.action import Action


class AbstractJsonActions(Action):

    def __init__(self, config, json_manager, json_file=None, action_type=None, sequence_dir=None):
        # État par instance (était au niveau classe = partagé entre toutes les
        # actions filles Face/Lights/... piège Python).
        self.global_duration = 0
        self.start_global_lime = 0
        self.loop = False
        self.config = config
        self.sequences_key = {}
        self.sequences_name = {}
        self.json_file = json_file
        if not sequence_dir:
            self.load_keys_and_names_sequences(json_manager)
        else:
            self.load_multi_files_sequences(sequence_dir)
        self.action_type = action_type
        self.msg_time = 0

    def load_keys_and_names_sequences(self, json_manager):
        self.sequences_key, self.sequences_name = self._indexer(json_manager.open_json(self.json_file))

    @staticmethod
    def _indexer(sequences):
        """(par touche, par nom) d'un fichier à plusieurs entrées ; NAME injecté depuis la clé."""
        par_touche, par_nom = {}, {}
        for seq_key in sequences:
            if KEYS in sequences[seq_key].keys():
                for key in sequences[seq_key][KEYS]:
                    par_touche[key] = sequences[seq_key]
            par_nom[seq_key] = sequences[seq_key]
            par_nom[seq_key][NAME] = seq_key
        return par_touche, par_nom

    def relire_entrees(self):
        """Lot L1d (rechargement à chaud) : relit self.json_file SUR LE DISQUE après une
        écriture du robot (data_edit_result). Illisible = ERROR, anciennes entrées gardées.
        L'échange des deux index est atomique : une commande en cours garde son entrée."""
        chemin = os.path.join(self.config[JSON_DIRECTORY], self.json_file)
        try:
            with open(chemin, encoding="utf-8") as f:
                sequences = json.load(f)
            index = self._indexer(sequences)
        except (OSError, ValueError, TypeError, AttributeError) as e:
            logging.error("rechargement de %s impossible, ancienne version gardée : %s", chemin, e)
            return False
        self.sequences_key, self.sequences_name = index
        logging.info("rechargé : %s (%d entrées)", chemin, len(self.sequences_name))
        return True

    def load_multi_files_sequences(self, sequence_dir):
        # chemins_sequences : nom nu -> "<dossier>/<nom>" du fichier RETENU (le dernier lu pour
        # un nom donné, comme sequences_name) ; le registre des validations sim est indexé par
        # chemin (lot L1d-2) : la barrière roues doit savoir quel fichier joue.
        self.chemins_sequences = {}
        sequences_files = FilesUtils.get_folder_files(sequence_dir)
        for sequence_file in sequences_files:
            json_sequence = FilesUtils.open_json(sequence_file, 'r')
            json_sequence[NAME] = os.path.basename(sequence_file).replace(".json", "")
            self.sequences_key[json_sequence[KEYS]] = json_sequence
            self.sequences_name[json_sequence[NAME]] = json_sequence
            relatif = os.path.relpath(sequence_file, sequence_dir)[:-len(".json")]
            self.chemins_sequences[json_sequence[NAME]] = relatif.replace(os.sep, "/")

    def get_sequence(self, msg, animation_loop):

        if not msg or (KEY not in msg and self.action_type not in msg):
            return

        sequence = None
        if self.action_type in msg and msg[self.action_type] in self.sequences_name:
            sequence = self.sequences_name[msg[self.action_type]]
        elif KEY in msg and msg[KEY] in self.sequences_key:
            sequence = self.sequences_key[msg[KEY]]

        if sequence:
            if animation_loop and DURATION in msg.keys():
                self.global_duration = msg[DURATION]
                self.start_global_lime = TimeUtils.current_milli_time()
            return sequence
        else:
           logging.debug("no sequence with key {}".format(self.json_file))

    def get_random_sequence(self, type):
        random_sequences = []
        for sequence in self.sequences_name:
            if TYPES in self.sequences_name[sequence] and type in self.sequences_name[sequence][TYPES]:
                random_sequences.append(sequence)
        if len(random_sequences) > 0:
            rand_sequence = random_sequences[random.randint(0, len(random_sequences)-1)]
            logging.info("random sequence: {}".format(rand_sequence))
            return rand_sequence