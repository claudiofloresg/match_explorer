"""
fetch_from_api.py
===================
Se conecta directo a la API de Stats Perform, revisa qué partidos hay
disponibles en las competencias configuradas, y descarga a data/raw/ los
que todavía no tengas (Match Stats + Match Events de cada uno).

Después de correr este script, corre build_data.py y build_html.py como
siempre — no cambia nada de ahí en adelante.

CONFIGURACIÓN (una sola vez)
------------------------------
1. Copia el archivo .env.example a .env (en la misma carpeta que este script).
2. Abre .env y llena tus 3 credenciales (las mismas que usas en Postman):
     STATSPERFORM_API_KEY=...
     STATSPERFORM_CLIENT_ID=...
     STATSPERFORM_CLIENT_SECRET=...
3. Corre:  pip install requests python-dotenv --break-system-packages
   (una sola vez, si no los tienes instalados)

USO
----
   python3 fetch_from_api.py

Por default descarga TODOS los partidos ya jugados de las competencias
configuradas en COMPETITIONS más abajo, que todavía no tengas en data/raw/.
Puedes limitarlo con --tmcl si solo quieres una competencia:

   python3 fetch_from_api.py --tmcl 9zum4nxferygj8bb0ldcavxn8

O limitar cuántos partidos nuevos baja en una corrida (para probar primero):

   python3 fetch_from_api.py --limit 3
"""
import argparse
import json
import os
import time
from pathlib import Path
from datetime import date
import requests
from dotenv import load_dotenv

load_dotenv()

# ------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------
TOKEN_URL = "https://api.statsperform.com/realms/apigw/protocol/openid-connect/token"
BASE_URL = "https://api.statsperform.com/sdapi/v1/soccerdata"

RAW_DIR = Path(__file__).parent / "data" / "raw"

# Las 5 competencias que confirmaste: Liga MX, Femenil, U21, U19, U17.
# (Expansión queda fuera a propósito.) Agrega o quita renglones aquí si
# cambia tu contrato de licencia — no hace falta tocar nada más del script.
COMPETITIONS = [
    {"name": "Liga MX",          "tmcl": "9zum4nxferygj8bb0ldcavxn8"},
    #{"name": "Liga MX Femenil",  "tmcl": "4nr8a6o18dpjqc9n6f6he5jx0"},
    #{"name": "U21 League",       "tmcl": "emlv6gh33jv3a61lw7mad9xck"},
    #{"name": "U19 League",       "tmcl": "avp1js728ktn7i45xiy5qhous"},
    #{"name": "U17 League",       "tmcl": "6b4002nj8u6uzdpp8cc7pf6z8"},
]

# Pausa entre llamadas a la API, para no saturarla (segundos).
REQUEST_DELAY = 1.0

# NOTA IMPORTANTE sobre estos dos nombres de parámetro:
# No tengo forma de confirmar desde aquí si Opta espera "fx" o "matchId"
# para filtrar Match Stats / Match Events por partido — es el patrón más
# común en el API de Opta, pero puede variar según tu contrato.
# ANTES DE CORRER EN SERIO: prueba UN partido a mano en Postman con este
# mismo patrón de URL (cambiando matchstats por matchevent) y confirma que
# regresa datos. Si el parámetro es distinto, cámbialo aquí una sola vez:
MATCH_ID_PARAM = "fx"


def get_access_token():
    api_key = os.environ["STATSPERFORM_API_KEY"]
    client_id = os.environ["STATSPERFORM_CLIENT_ID"]
    client_secret = os.environ["STATSPERFORM_CLIENT_SECRET"]

    resp = requests.post(
        TOKEN_URL,
        params={"apikey": api_key},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    return token_data["access_token"]


class OptaClient:
    """Wraps requests, renewing the OAuth token automatically when it's about to expire."""

    def __init__(self):
        self.token = None
        self.token_expires_at = 0

    def _ensure_token(self):
        if self.token is None or time.time() > self.token_expires_at - 30:
            api_key = os.environ["STATSPERFORM_API_KEY"]
            client_id = os.environ["STATSPERFORM_CLIENT_ID"]
            client_secret = os.environ["STATSPERFORM_CLIENT_SECRET"]
            resp = requests.post(
                TOKEN_URL,
                params={"apikey": api_key},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self.token = data["access_token"]
            self.token_expires_at = time.time() + int(data.get("expires_in", 300))
            print("[auth] Token renovado.")

    def get(self, endpoint, params):
        self._ensure_token()
        url = f"{BASE_URL}/{endpoint}/"
        params = {**params, "_fmt": "json"}
        resp = requests.get(url, params=params, headers={"Authorization": f"Bearer {self.token}"})
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return resp.json()


def already_downloaded_match_ids(raw_dir):
    """Scans data/raw/ and returns the set of match ids we already have (by matchInfo.id)."""
    ids = set()
    for path in raw_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            mid = d.get("matchInfo", {}).get("id")
            if mid:
                ids.add(mid)
        except (json.JSONDecodeError, OSError):
            continue
    return ids


def list_played_matches(client, tmcl):
    """
    Devuelve únicamente partidos cuya fecha sea hoy o anterior.
    Evita consultar Match Stats / Match Events de partidos futuros.
    """

    data = client.get("tournamentschedule", {"tmcl": tmcl})

    matches = []
    today = date.today()

    for md in data.get("matchDate", []):
        for m in md.get("match", []):

            local_date = m.get("localDate")

            if not local_date:
                continue

            try:
                match_date = date.fromisoformat(local_date)
            except ValueError:
                print(f"  [warning] Fecha inválida: {local_date}")
                continue

            # Ignorar partidos futuros
            if match_date > today:
                continue

            matches.append(m)

    return matches


def download_match(client, raw_dir, match_id, label):
    stats_path = raw_dir / f"Stats_{match_id}.json"
    events_path = raw_dir / f"Events_{match_id}.json"

    if not stats_path.exists():
        print(f"  -> descargando Match Stats: {label}")
        stats = client.get("matchstats", {MATCH_ID_PARAM: match_id, "detailed": "yes"})
        # Not-yet-played matches / no coverage yet come back without liveData.lineUp —
        # skip saving those so build_data.py's auto-discovery doesn't choke on them.
        if "lineUp" not in stats.get("liveData", {}):
            print(f"     (sin estadísticas todavía, se omite por ahora)")
            return False
        stats_path.write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

    if not events_path.exists():
        print(f"  -> descargando Match Events: {label}")
        events = client.get("matchevent", {MATCH_ID_PARAM: match_id})
        if "event" not in events.get("liveData", {}):
            print(f"     (sin eventos todavía, se omite por ahora)")
            return False
        events_path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")

    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tmcl", help="Solo esta competencia (tournamentCalendarId)")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de partidos nuevos a bajar en esta corrida")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = OptaClient()

    comps = COMPETITIONS
    if args.tmcl:
        comps = [c for c in COMPETITIONS if c["tmcl"] == args.tmcl]
        if not comps:
            comps = [{"name": "(manual)", "tmcl": args.tmcl}]

    have = already_downloaded_match_ids(RAW_DIR)
    print(f"Ya tienes {len(have)} partido(s) en data/raw/.\n")

    downloaded = 0
    for comp in comps:
        print(f"== {comp['name']} ==")
        matches = list_played_matches(client, comp["tmcl"])
        for m in matches:
            mid = m["id"]
            label = f"{m.get('homeContestantName','?')} vs {m.get('awayContestantName','?')} ({m.get('localDate','?')})"
            if mid in have:
                continue
            if args.limit is not None and downloaded >= args.limit:
                print(f"\nLímite de {args.limit} alcanzado, deteniendo aquí por ahora.")
                print("Corre el script de nuevo para seguir con los que faltan.")
                return
            ok = download_match(client, RAW_DIR, mid, label)
            if ok:
                downloaded += 1
                have.add(mid)
        print()

    print(f"Listo. {downloaded} partido(s) nuevo(s) descargados a data/raw/.")
    print("Corre build_data.py y build_html.py para incluirlos en el explorador.")


if __name__ == "__main__":
    main()
