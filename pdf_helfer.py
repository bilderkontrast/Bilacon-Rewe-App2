import os
import shutil
import re
from pypdf import PdfReader, PdfWriter
from datetime import datetime

def kopiere_protokoll(basis_pfad, ziel_ordner, dateiname):
    quelle = os.path.join(basis_pfad, "vorlagen", dateiname)
    if not os.path.exists(quelle):
        quelle = os.path.join(basis_pfad, dateiname)
        
    ziel = os.path.join(ziel_ordner, f"Fertig_{dateiname}")
    
    if os.path.exists(quelle):
        try:
            shutil.copy(quelle, ziel)
            return ziel
        except Exception as e:
            print(f"Fehler beim Kopieren von {dateiname}: {e}")
            return None
    return ziel if os.path.exists(ziel) else None

def fuege_pdfs_zusammen(markt_ordner, fallback_name):
    writer = PdfWriter()
    dateien = [f for f in os.listdir(markt_ordner) if f.startswith("Fertig_") and f.endswith(".pdf")]
    
    if not dateien:
        return None

    markt_nummer = None
    TARGET_ID = "tf_0000_00_ZS-1408".lower()
    
    stammdaten_pfad = os.path.join(markt_ordner, "Fertig_stammdaten.pdf")
    if os.path.exists(stammdaten_pfad):
        try:
            reader = PdfReader(stammdaten_pfad)
            fields = reader.get_fields()
            
            if not fields:
                fields = {}
                for page in reader.pages:
                    if "/Annots" in page:
                        for annot in page["/Annots"]:
                            obj = annot.get_object()
                            if "/T" in obj:
                                fields[obj["/T"]] = obj

            if fields:
                for key, field_data in fields.items():
                    if TARGET_ID in str(key).lower():
                        if isinstance(field_data, dict) and "/V" in field_data:
                            wert = field_data["/V"]
                        elif isinstance(field_data, dict):
                            wert = field_data.get("/V", "")
                        else:
                            wert = ""
                            
                        finaler_wert = str(wert).strip()
                        
                        if finaler_wert and finaler_wert.lower() != "none" and finaler_wert != "":
                            markt_nummer = finaler_wert.replace("/", "-").replace("\\", "-")
                            break
        except Exception as e:
            print(f"Fehler beim PDF-Scan: {e}")

    # SIGNAL: Marktnummer fehlt
    if not markt_nummer:
        return "MISSING_MARKET_NUMBER"

    for datei in sorted(dateien):
        pfad = os.path.join(markt_ordner, datei)
        try:
            writer.append(pfad)
        except Exception as e:
            pass

    # HIER IST DIE ÄNDERUNG: "%d%m%y" statt "%d.%m.%y"
    datum_heute = datetime.now().strftime("%d%m%y")
    neuer_name = f"REWE_{markt_nummer}_{datum_heute}.pdf"
    sicherer_name = re.sub(r'[\\/*?:"<>|]', "", neuer_name)
    
    ziel_pfad = os.path.join(markt_ordner, sicherer_name)
    
    try:
        with open(ziel_pfad, "wb") as f:
            writer.write(f)
        writer.close()
        return sicherer_name
    except Exception as e:
        return None