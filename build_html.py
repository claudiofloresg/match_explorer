"""
build_html.py
==============
Combina template.html + los JSON generados por build_data.py (en data/build/)
+ el logo (assets/logo.png) en un solo archivo HTML listo para abrir/compartir.

USO
---
1. Corre primero build_data.py (o asegúrate de que data/build/*.json ya existan).
2. Corre:  python3 build_html.py
3. El archivo final queda en output/Explorador_Partido_Pumas.html
"""
import base64
import os

TEMPLATE_FILE = "template.html"
LOGO_FILE = "assets/logo.png"
BUILD_DIR = "data/build"
OUT_DIR = "docs"
OUT_FILE = os.path.join(OUT_DIR, "index.html")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    html = open(TEMPLATE_FILE, encoding='utf-8').read()

    events = open(os.path.join(BUILD_DIR, "events_data.json"), encoding='utf-8').read().strip()
    fullstats = open(os.path.join(BUILD_DIR, "player_full_stats.json"), encoding='utf-8').read().strip()
    summary = open(os.path.join(BUILD_DIR, "team_summary.json"), encoding='utf-8').read().strip()

    html = html.replace('__EVENTS_JSON__', events)
    html = html.replace('__FULLSTATS_JSON__', fullstats)
    html = html.replace('__SUMMARY_JSON__', summary)

    if os.path.exists(LOGO_FILE):
        logo_b64 = base64.b64encode(open(LOGO_FILE, 'rb').read()).decode()
    else:
        logo_b64 = ''
        print(f"[warn] {LOGO_FILE} no encontrado — el escudo saldrá en blanco. "
              f"Coloca tu logo ahí (PNG, se recomienda <300px de ancho) y vuelve a correr este script.")
    html = html.replace('__LOGO_B64__', logo_b64)

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Listo -> {OUT_FILE}  ({len(html)/1024:.1f} KB)")


if __name__ == '__main__':
    main()
