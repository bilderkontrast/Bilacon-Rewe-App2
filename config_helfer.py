import json
import os

PFAD_CONFIG = "user_config.json"

def lade_benutzerdaten():
    if os.path.exists(PFAD_CONFIG):
        try:
            with open(PFAD_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None

def speichere_benutzerdaten(ordner_name):
    daten = {"ordner": ordner_name}
    with open(PFAD_CONFIG, "w", encoding="utf-8") as f:
        json.dump(daten, f)

def loesche_benutzerdaten():
    if os.path.exists(PFAD_CONFIG):
        os.remove(PFAD_CONFIG)