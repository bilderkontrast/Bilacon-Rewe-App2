import flet as ft
import os
import shutil
import re
import urllib.parse
import config_helfer
import pdf_helfer
import time
import threading
import platform
from datetime import datetime

# Definieren des Pfads ganz oben, damit ft.app() ihn kennt (verhindert den NameError)
try:
    GLOB_BASIS_ORDNER = os.path.dirname(os.path.abspath(__file__))
except NameError:
    # Fallback, falls __file__ nicht definiert ist
    GLOB_BASIS_ORDNER = os.path.abspath(os.getcwd())

def main(page: ft.Page):
    page.title = "Protokoll Zentrale"
    FARBE_HINTERGRUND = "#061A14"
    FARBE_BUTTON = "#144D3F"
    page.bgcolor = FARBE_HINTERGRUND
    page.theme_mode = "dark" 
    page.padding = 0
    
    BUTTON_STYLE = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=8),
        side=ft.BorderSide(1, "white54"),
        elevation=12,
        shadow_color="black",
        padding=15,
        bgcolor=FARBE_BUTTON
    )
    
    # --- ANDROID-SICHERER PFAD ---
    if platform.system() == "Android" or "ANDROID_ARGUMENT" in os.environ:
        # Auf Android in den internen App-Home-Ordner schreiben
        APP_BASIS_ORDNER = os.environ.get("HOME", os.getcwd())
    else:
        # Am PC nutzen wir den Ordner, in dem die Datei liegt
        APP_BASIS_ORDNER = GLOB_BASIS_ORDNER

    # Arbeitsverzeichnis wechseln, damit config_helfer/pdf_helfer korrekt arbeiten
    os.chdir(APP_BASIS_ORDNER)

    ORDNER_POSTAUSGANG = os.path.join(APP_BASIS_ORDNER, "postausgang")
    ORDNER_VORLAGEN = os.path.join(APP_BASIS_ORDNER, "vorlagen")
    ORDNER_ARCHIV = os.path.join(APP_BASIS_ORDNER, "archiv")
    
    try:
        for ordner in [ORDNER_POSTAUSGANG, ORDNER_VORLAGEN, ORDNER_ARCHIV]:
            if not os.path.exists(ordner):
                os.makedirs(ordner)
    except Exception as e:
        page.add(ft.Text(f"CRITICAL ERROR: Ordner können nicht erstellt werden: {e}", color="red", size=20, weight="bold"))
        return

    app_state = {"markt": None, "update_datei": None}

    def get_markt_ordner():
        if app_state["markt"]:
            pfad = os.path.join(ORDNER_POSTAUSGANG, app_state["markt"])
            if not os.path.exists(pfad): os.makedirs(pfad)
            return pfad
        return None

    # --- DATEI AUSWÄHLER (FILE PICKER FÜR TEAMS/ONEDRIVE) ---
    def on_datei_ausgewaehlt(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            ausgewaehlte_datei = e.files[0]
            ziel_name = app_state.get("update_datei")
            if ziel_name:
                ziel_pfad = os.path.join(ORDNER_VORLAGEN, ziel_name)
                try:
                    shutil.copy2(ausgewaehlte_datei.path, ziel_pfad)
                    text_einstellungen_meldung.value = f"✅ '{ziel_name}' erfolgreich importiert!"
                    text_einstellungen_meldung.color = "#4CAF50"
                except Exception as ex:
                    text_einstellungen_meldung.value = f"❌ Fehler beim Import: {ex}"
                    text_einstellungen_meldung.color = "#FF4C4C"
                
                text_einstellungen_meldung.visible = True
                aktualisiere_einstellungen()
                page.update()

    # HIER IST DER FIX FÜR DEN ROTEN FEHLER AUS DEINEM SCREENSHOT:
    file_picker = ft.FilePicker()
    file_picker.on_result = on_datei_ausgewaehlt
    page.overlay.append(file_picker)

    # --- UI ELEMENTE & BUTTONS ---
    text_titel = ft.Text("", size=22, weight="bold", color="white")
    text_benutzer_info = ft.Text("", color=FARBE_HINTERGRUND, size=12, weight="bold")
    text_postausgang_zaehler = ft.Text("Versand (0)", color="white")
    
    text_status_meldung = ft.Text("", color="red", weight="bold", size=14, visible=False, text_align=ft.TextAlign.CENTER)
    text_dash_meldung = ft.Text("", color="red", weight="bold", size=14, visible=False, text_align=ft.TextAlign.CENTER)
    text_einstellungen_meldung = ft.Text("", color="green", weight="bold", size=14, visible=False, text_align=ft.TextAlign.CENTER)
    
    btn_paket_bauen = ft.ElevatedButton("PAKET BAUEN", icon=ft.Icons.MERGE, bgcolor="blue", color="white", style=BUTTON_STYLE, expand=True)
    btn_abschluss = ft.ElevatedButton("INS ARCHIV VERSCHIEBEN", icon=ft.Icons.ARCHIVE, bgcolor="green", color="white", style=BUTTON_STYLE, expand=True, disabled=True)

    button_touren = ft.TextButton(content=ft.Row([ft.Icon(ft.Icons.MAP, color="white"), ft.Text("Touren", color="white")], spacing=5))
    button_archiv = ft.TextButton(content=ft.Row([ft.Icon(ft.Icons.HISTORY, color="white"), ft.Text("Archiv", color="white")], spacing=5))
    button_dashboard = ft.TextButton(content=ft.Row([ft.Icon(ft.Icons.DASHBOARD, color="white"), ft.Text("Dash", color="white")], spacing=5), visible=False)
    button_postausgang = ft.TextButton(content=ft.Row([ft.Icon(ft.Icons.CLOUD_UPLOAD, color="white"), text_postausgang_zaehler], spacing=5), visible=False)
    button_einstellungen = ft.TextButton(content=ft.Row([ft.Icon(ft.Icons.SETTINGS, color="white54"), ft.Text("Vorlagen", color="white54")], spacing=5))
    button_home = ft.TextButton(content=ft.Row([ft.Icon(ft.Icons.PERSON, color="white54"), ft.Text("Profil", color="white54")], spacing=5))

    bereich_profil = ft.Column(visible=False, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
    bereich_touren = ft.Column(visible=False, spacing=15)
    bereich_dashboard = ft.Column(visible=False, spacing=15)
    bereich_postausgang = ft.Column(visible=False, spacing=15)
    bereich_archiv = ft.Column(visible=False, spacing=15)
    bereich_einstellungen = ft.Column(visible=False, spacing=15)

    def zeige_home():
        bereich_profil.controls.clear()
        try:
            benutzer = config_helfer.lade_benutzerdaten()
        except:
            benutzer = {}

        titel_text = ft.Text(
            spans=[
                ft.TextSpan("REWE\n", style=ft.TextStyle(color="#E23D28", size=32, weight="bold")), 
                ft.TextSpan("Protokollierung", style=ft.TextStyle(color="white", size=24, weight="bold"))
            ], 
            text_align=ft.TextAlign.CENTER
        )

        if benutzer and "ordner" in benutzer:
            name = benutzer["ordner"]
            text_benutzer_info.value = f"Prüfer: {name}"
            willkommen = ft.Text(f"Willkommen zurück, {name}!", color="white", size=18, weight="bold")
            btn_weiter = ft.ElevatedButton("Weiter zu den Touren", icon=ft.Icons.ARROW_FORWARD, on_click=lambda _: wechsle_ansicht("touren"), height=50, width=300, bgcolor=FARBE_BUTTON, color="white", style=BUTTON_STYLE)
            btn_reset = ft.TextButton("Mit anderem Namen anmelden", on_click=lambda _: [config_helfer.loesche_benutzerdaten(), zeige_home()], icon=ft.Icons.SWITCH_ACCOUNT, icon_color="white54")
            bereich_profil.controls.extend([titel_text, ft.Divider(height=20, color="transparent"), willkommen, btn_weiter, btn_reset])
        else:
            text_benutzer_info.value = ""
            feld_name = ft.TextField(hint_text="Dein Name", text_align=ft.TextAlign.CENTER, bgcolor=FARBE_BUTTON, border_color="transparent")
            def save_click(e):
                if feld_name.value.strip():
                    config_helfer.speichere_benutzerdaten(feld_name.value.strip())
                    text_benutzer_info.value = f"Prüfer: {feld_name.value.strip()}"
                    wechsle_ansicht("touren")
            btn_start = ft.ElevatedButton("Profil speichern & Starten", on_click=save_click, height=50, width=300, bgcolor=FARBE_BUTTON, color="white", style=BUTTON_STYLE)
            bereich_profil.controls.extend([titel_text, ft.Divider(height=20, color="transparent"), ft.Container(content=feld_name, width=300, border=ft.border.all(1, "white54"), border_radius=5), btn_start])

        page.update()

    def wechsle_ansicht(ansicht_name):
        text_status_meldung.visible = False 
        text_dash_meldung.visible = False
        text_einstellungen_meldung.visible = False
        
        bereich_profil.visible = (ansicht_name == "profil")
        bereich_touren.visible = (ansicht_name == "touren")
        bereich_dashboard.visible = (ansicht_name == "dashboard")
        bereich_postausgang.visible = (ansicht_name == "postausgang")
        bereich_archiv.visible = (ansicht_name == "archiv")
        bereich_einstellungen.visible = (ansicht_name == "einstellungen")
        
        button_touren.visible = (ansicht_name not in ["profil", "einstellungen"])
        button_archiv.visible = (ansicht_name not in ["profil", "einstellungen"])
        button_dashboard.visible = (ansicht_name in ["dashboard", "postausgang"])
        button_postausgang.visible = (ansicht_name in ["dashboard", "postausgang"])
        button_home.visible = (ansicht_name != "profil")
        button_einstellungen.visible = (ansicht_name != "profil")
        
        if ansicht_name == "profil":
            text_titel.value = ""
            zeige_home()
        elif ansicht_name == "touren":
            text_titel.value = "Meine Touren"
            app_state["markt"] = None
            aktualisiere_touren_liste()
        elif ansicht_name == "dashboard":
            text_titel.value = f"📍 {app_state['markt']}"
            aktualisiere_dashboard()
        elif ansicht_name == "postausgang":
            text_titel.value = "📦 Versand & Archivieren"
            aktualisiere_postausgang()
        elif ansicht_name == "archiv":
            text_titel.value = "🗄️ Archiv (Letzte 7 Tage)"
            aktualisiere_archiv()
        elif ansicht_name == "einstellungen":
            text_titel.value = "⚙️ Vorlagen Import (Teams)"
            aktualisiere_einstellungen()
            
        page.update()

    # --- EINSTELLUNGEN / VORLAGEN IMPORT LOGIK ---
    ansicht_einstellungen_liste = ft.Column(spacing=10, scroll="auto")
    
    def aktualisiere_einstellungen():
        ansicht_einstellungen_liste.controls.clear()
        benoetigte_dateien = [
            ("Firmenlogo (Optional)", "logo.png", ft.Icons.DESCRIPTION),
            ("Stammdaten PDF", "stammdaten.pdf", ft.Icons.HOME_WORK),
            ("Hackfleisch PDF", "HFM.pdf", ft.Icons.LUNCH_DINING),
            ("Obst & Gemüse PDF", "OG.pdf", ft.Icons.ECO),
            ("Trinkwasser PDF", "TW.pdf", ft.Icons.WATER_DROP),
            ("Scherbeneis PDF", "Scherbeneis.pdf", ft.Icons.AC_UNIT)
        ]
        for titel, dateiname, icon in benoetigte_dateien:
            pfad = os.path.join(ORDNER_VORLAGEN, dateiname)
            ist_da = os.path.exists(pfad)
            
            def import_klick(e, name=dateiname):
                app_state["update_datei"] = name
                text_einstellungen_meldung.visible = False
                page.update()
                file_picker.pick_files(allow_multiple=False)
                
            ansicht_einstellungen_liste.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(icon, color="black" if ist_da else "white54"),
                        ft.Text(titel, expand=True, color="black" if ist_da else "white", weight="bold"),
                        ft.ElevatedButton("Import", icon=ft.Icons.DOWNLOAD, bgcolor="blue", color="white", on_click=import_klick)
                    ]),
                    bgcolor="green" if ist_da else "white10", padding=15, border_radius=10
                )
            )
        page.update()

    # --- ARCHIV LOGIK ---
    ansicht_archiv_liste = ft.Column(spacing=5, scroll="auto")
    archiv_info_box = ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.MAIL_OUTLINE, color="white", size=30),
            ft.Text(spans=[ft.TextSpan("Bitte sende die fertigen PDFs an:\n", style=ft.TextStyle(color="white", size=14)), ft.TextSpan("reg.mibi@tentamus.com", style=ft.TextStyle(color="#3498DB", size=18, weight="bold"), url="mailto:reg.mibi@tentamus.com")], text_align=ft.TextAlign.CENTER)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
        bgcolor="white10", padding=15, border_radius=10
    )
    
    def aktualisiere_archiv():
        ansicht_archiv_liste.controls.clear()
        jetzt = time.time()
        for f in os.listdir(ORDNER_ARCHIV):
            pfad = os.path.join(ORDNER_ARCHIV, f)
            if os.path.isfile(pfad):
                if os.path.getmtime(pfad) < jetzt - 604800:
                    try: os.remove(pfad)
                    except: pass
                    
        dateien = [f for f in os.listdir(ORDNER_ARCHIV) if f.endswith(".pdf")]
        dateien.sort(key=lambda x: os.path.getmtime(os.path.join(ORDNER_ARCHIV, x)), reverse=True)
        
        if not dateien:
            ansicht_archiv_liste.controls.append(ft.Text("Dein Archiv ist leer.", color="white54", italic=True))
            
        for d in dateien:
            lokaler_pfad = os.path.join(ORDNER_ARCHIV, d)
            ansicht_archiv_liste.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.PICTURE_AS_PDF, color="red"), 
                        ft.Text(d, color="white", weight="bold", size=12, expand=True), 
                        ft.ElevatedButton("Öffnen / Teilen", icon=ft.Icons.SHARE, bgcolor="blue", color="white", on_click=lambda e, p=lokaler_pfad: oeffne_datei_am_pc(p))
                    ]), bgcolor="white10", padding=10, border_radius=5
                )
            )
        page.update()

    ansicht_kacheln = ft.Column(spacing=10, scroll="auto")
    
    def oeffne_datei_am_pc(pfad):
        try:
            if platform.system() == "Android" or "ANDROID_ARGUMENT" in os.environ:
                page.launch_url(f"file://{pfad}")
            else:
                os.startfile(pfad)
        except Exception as e:
            print(f"Fehler beim Öffnen: {e}")

    def oeffne_pdf_handler(d):
        text_dash_meldung.visible = False
        ordner = get_markt_ordner()
        if not ordner: return
        f_pfad = os.path.join(ordner, f"Fertig_{d}")
        
        if not os.path.exists(f_pfad):
            kp = pdf_helfer.kopiere_protokoll(APP_BASIS_ORDNER, ordner, d)
            if kp: 
                aktualisiere_dashboard()
                f_pfad = kp 
            else: 
                text_dash_meldung.value = f"❌ FEHLER: Vorlage fehlt! Gehe auf Zahnrad ⚙️ und importiere aus Teams."
                text_dash_meldung.color = "#FF4C4C"
                text_dash_meldung.visible = True
                page.update()
                return
        
        oeffne_datei_am_pc(f_pfad)

    def aktualisiere_dashboard():
        ansicht_kacheln.controls.clear()
        ordner = get_markt_ordner()
        if not ordner: return
        protokolle = [("Stammdaten", "stammdaten.pdf", ft.Icons.HOME_WORK), ("Hackfleisch (HFM)", "HFM.pdf", ft.Icons.LUNCH_DINING), ("Obst & Gemüse (OG)", "OG.pdf", ft.Icons.ECO), ("Trinkwasser (TW)", "TW.pdf", ft.Icons.WATER_DROP), ("Scherbeneis", "Scherbeneis.pdf", ft.Icons.AC_UNIT)]
        
        def alle_add_click(e):
            text_dash_meldung.visible = False
            fehler = 0
            fehlt_liste = []
            for t, d, i in protokolle: 
                if not pdf_helfer.kopiere_protokoll(APP_BASIS_ORDNER, ordner, d):
                    fehler += 1
                    fehlt_liste.append(d)
            aktualisiere_dashboard()
            
            if fehler == 0:
                text_dash_meldung.value = "✅ Alle Vorlagen wurden bereitgestellt!"
                text_dash_meldung.color = "#4CAF50"
            else:
                text_dash_meldung.value = f"⚠️ Warnung: {fehler} Vorlage(n) fehlen.\nBitte im Zahnrad-Menü ⚙️ importieren!"
                text_dash_meldung.color = "orange"
            text_dash_meldung.visible = True
            page.update()

        ansicht_kacheln.controls.append(ft.ElevatedButton("ALLE PROTOKOLLE LADEN", icon=ft.Icons.DONE_ALL, bgcolor="#D35400", color="white", on_click=alle_add_click, style=BUTTON_STYLE, width=1000))
        for t, d, i in protokolle:
            ist_da = os.path.exists(os.path.join(ordner, f"Fertig_{d}"))
            ansicht_kacheln.controls.append(ft.Container(content=ft.Row([ft.Icon(i, color="black" if ist_da else "white54"), ft.Text(t, expand=True, color="black" if ist_da else "white", weight="bold"), ft.Icon(ft.Icons.CHECK_CIRCLE, color="black") if ist_da else ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color="white54")]), bgcolor="green" if ist_da else "white10", padding=15, border_radius=10, on_click=lambda e, datei=d: oeffne_pdf_handler(datei)))
        text_postausgang_zaehler.value = f"Versand ({len([f for f in os.listdir(ordner) if f.startswith('Fertig_')])})"
        page.update()

    liste_postausgang = ft.Column(spacing=5, scroll="auto")
    ladebalken = ft.ProgressBar(visible=False, color="blue", bgcolor="white24") 

    def aktualisiere_postausgang():
        liste_postausgang.controls.clear()
        ordner = get_markt_ordner()
        if not ordner: return
        
        paket_vorhanden = False 
        dateien = [f for f in os.listdir(ordner) if f.endswith(".pdf")]
        for d in dateien:
            ist_gesamt = not d.startswith("Fertig_")
            if ist_gesamt:
                paket_vorhanden = True
                
            pfad_zur_datei = os.path.join(get_markt_ordner(), d)
            
            def loesche_datei(e, datei_name=d):
                versuchs_pfad = os.path.join(get_markt_ordner(), datei_name)
                try:
                    os.remove(versuchs_pfad)
                    aktualisiere_postausgang()
                    text_status_meldung.visible = False
                    page.update()
                except Exception as ex:
                    text_status_meldung.value = f"❌ Kann '{datei_name}' nicht löschen."
                    text_status_meldung.color = "orange"
                    text_status_meldung.visible = True
                    page.update()

            row_controls = []
            if not ist_gesamt:
                row_controls.append(ft.IconButton(ft.Icons.REMOVE_RED_EYE, icon_color="blue", tooltip="Öffnen", on_click=lambda e, p=pfad_zur_datei: oeffne_datei_am_pc(p)))
            
            if ist_gesamt:
                row_controls.append(ft.ElevatedButton("ZUM ONEDRIVE/MAIL", icon=ft.Icons.CLOUD_UPLOAD, bgcolor="green", color="white", on_click=lambda e, p=pfad_zur_datei: oeffne_datei_am_pc(p)))
                
            row_controls.append(ft.Text(d, color="white", weight="bold" if ist_gesamt else "normal", size=12, expand=True))
            row_controls.append(ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color="red", on_click=loesche_datei))

            liste_postausgang.controls.append(ft.Container(content=ft.Row(row_controls), bgcolor="white10", padding=5, border_radius=5))
        
        btn_abschluss.disabled = not paket_vorhanden
        page.update()

    def zusammenfuegen_click(e):
        text_status_meldung.visible = False
        ladebalken.visible = True
        page.update()
        
        ordner = get_markt_ordner()
        try:
            res = pdf_helfer.fuege_pdfs_zusammen(ordner, "")
        except Exception as ex:
            res = None
        
        ladebalken.visible = False
        
        if res == "MISSING_MARKET_NUMBER":
            text_status_meldung.value = "⚠️ ABBRUCH: Marktnummer fehlt!\nBitte fülle das Stammdaten-PDF aus."
            text_status_meldung.color = "#FF4C4C"
            text_status_meldung.visible = True
        elif res:
            text_status_meldung.value = f"✅ Paket '{res}' erfolgreich erstellt!"
            text_status_meldung.color = "#4CAF50"
            text_status_meldung.visible = True
        else:
            text_status_meldung.value = "❌ Fehler: Keine fertigen Dateien gefunden."
            text_status_meldung.color = "orange"
            text_status_meldung.visible = True
            
        aktualisiere_postausgang()
        page.update()

    def senden_und_reinigen_click(e):
        ordner_pfad = os.path.join(ORDNER_POSTAUSGANG, app_state["markt"])
        try:
            for d in os.listdir(ordner_pfad):
                if d.startswith("REWE_") and d.endswith(".pdf"):
                    quelle = os.path.join(ordner_pfad, d)
                    ziel = os.path.join(ORDNER_ARCHIV, d)
                    shutil.copy2(quelle, ziel)
            shutil.rmtree(ordner_pfad)
            text_status_meldung.visible = False
            wechsle_ansicht("touren")
        except Exception as ex:
            text_status_meldung.value = f"❌ Fehler beim Archivieren."
            text_status_meldung.color = "#FF4C4C"
            text_status_meldung.visible = True
            page.update()

    btn_paket_bauen.on_click = zusammenfuegen_click
    btn_abschluss.on_click = senden_und_reinigen_click

    ansicht_touren_liste = ft.Column(spacing=10, scroll="auto")
    eingabe_neuer_markt = ft.TextField(hint_text="Neuer Markt", text_align=ft.TextAlign.CENTER, bgcolor=FARBE_BUTTON, border_color="transparent", expand=True)

    def aktualisiere_touren_liste():
        ansicht_touren_liste.controls.clear()
        maerkte = [d for d in os.listdir(ORDNER_POSTAUSGANG) if os.path.isdir(os.path.join(ORDNER_POSTAUSGANG, d))]
        for m in maerkte: ansicht_touren_liste.controls.append(ft.Container(content=ft.Row([ft.Text(m, weight="bold", expand=True, color="white"), ft.ElevatedButton("Öffnen", on_click=lambda e, name=m: [app_state.update({"markt": name}), wechsle_ansicht("dashboard")], style=BUTTON_STYLE)]), bgcolor="white10", padding=15, border_radius=10))
        page.update()

    bereich_touren.controls = [ft.Row([ft.Container(content=eingabe_neuer_markt, expand=True, border=ft.border.all(1, "white54"), border_radius=5), ft.IconButton(ft.Icons.ADD_CIRCLE, on_click=lambda _: [os.makedirs(os.path.join(ORDNER_POSTAUSGANG, re.sub(r'[\\/*?:"<>|]', "", eingabe_neuer_markt.value.strip()))) if eingabe_neuer_markt.value.strip() else None, aktualisiere_touren_liste(), setattr(eingabe_neuer_markt, "value", "")], icon_color="white", icon_size=40)]), ansicht_touren_liste]
    
    bereich_dashboard.controls = [ansicht_kacheln, ft.Divider(color="transparent"), text_dash_meldung]
    bereich_archiv.controls = [archiv_info_box, ft.Divider(color="transparent"), ansicht_archiv_liste]
    bereich_postausgang.controls = [ft.Text("Pakete bauen:"), ladebalken, liste_postausgang, ft.Divider(color="white24"), text_status_meldung, ft.Row([btn_paket_bauen, btn_abschluss])]
    
    bereich_einstellungen.controls = [
        ft.Text("Ziehe hier die neuesten PDFs aus Teams in die App:", color="white", weight="bold"),
        ansicht_einstellungen_liste,
        ft.Divider(color="white24"),
        text_einstellungen_meldung
    ]

    button_touren.on_click = lambda _: wechsle_ansicht("touren")
    button_archiv.on_click = lambda _: wechsle_ansicht("archiv")
    button_dashboard.on_click = lambda _: wechsle_ansicht("dashboard")
    button_postausgang.on_click = lambda _: wechsle_ansicht("postausgang")
    button_einstellungen.on_click = lambda _: wechsle_ansicht("einstellungen")
    button_home.on_click = lambda _: wechsle_ansicht("profil")

    logo_pfad = os.path.join(ORDNER_VORLAGEN, "logo.png")
    
    header_logo = ft.Container(
        content=ft.Stack([
            ft.Row([
                ft.Image(
                    src=logo_pfad, 
                    height=40, 
                    fit="contain", 
                    error_content=ft.Row([
                        ft.Icon(ft.Icons.DESCRIPTION, color="#061A14", size=30),
                        ft.Text("PROTOKOLL", color="#061A14", weight="bold", size=16)
                    ])
                )
            ], alignment=ft.MainAxisAlignment.START), 
            ft.Row([
                ft.Container(content=text_benutzer_info, padding=ft.padding.only(right=10, top=12))
            ], alignment=ft.MainAxisAlignment.END)
        ]), 
        padding=5, 
        bgcolor="white" 
    )
    
    nav_balken = ft.Container(content=ft.Row([button_touren, button_archiv, button_einstellungen, button_dashboard, button_postausgang, button_home], scroll="auto", alignment=ft.MainAxisAlignment.START), padding=5, bgcolor=FARBE_BUTTON)
    
    page.add(ft.Column([header_logo, nav_balken, ft.Container(content=ft.Column([text_titel, bereich_profil, bereich_touren, bereich_dashboard, bereich_postausgang, bereich_archiv, bereich_einstellungen]), padding=15, expand=True)], expand=True, spacing=0))

    def reminder_loop():
        while True:
            time.sleep(3600)

    threading.Thread(target=reminder_loop, daemon=True).start()
    wechsle_ansicht("profil")

ft.app(target=main, assets_dir=GLOB_BASIS_ORDNER)