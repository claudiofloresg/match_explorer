"""
build_data.py
==============
Convierte pares de archivos Opta (MA2 "Match Stats" + MA3 "Match Events") en los
3 JSON que consume el Explorador de Partido (events_data.json, player_full_stats.json,
team_summary.json).

CÓMO AGREGAR UN PARTIDO NUEVO (ahora automático)
--------------------------------------------------
1. Copia los dos JSON que te da el SDAPI a data/raw/, con el nombre que sea:
   - El de MA2 "Match Stats" detallado
   - El de MA3 "Match Events"
2. Corre:  python3 build_data.py

Eso es todo. El script:
  - Detecta solo, por el CONTENIDO del archivo (no por el nombre), cuál es el
    de Stats y cuál el de Events.
  - Empareja automáticamente los dos archivos de un mismo partido usando el ID
    interno que Opta les pone (matchInfo.id), así que no importa cómo se
    llamen los archivos ni el orden en que los copies.
  - Genera solo la etiqueta del partido (competencia, jornada, equipos, fecha)
    leyéndolo directamente del JSON — no hace falta escribir nada a mano.
  - Funciona igual para Liga MX, Liga MX Femenil, Liga Expansión, o cualquier
    otra categoría/torneo: cada partido se etiqueta con el nombre de su propia
    competencia, tal como viene en el archivo.
  - Si agregas partidos que ya habías cargado antes (mismo ID), simplemente
    los vuelve a procesar sin duplicarlos.

Sigue funcionando el modo manual si alguna vez lo necesitas (ver MANUAL_MATCHES
más abajo) — por ejemplo si quieres forzar una etiqueta o un orden específico.

TRACKED_TEAM_NAME solo se usa para decidir qué equipo se selecciona por default
al abrir un partido — si ninguno de los dos equipos del partido coincide, el
explorador simplemente selecciona el equipo local.
"""
import json
import os
import glob
from dataclasses import dataclass

RAW_DIR = "data/raw"
OUT_DIR = "data/build"

# Nombre del equipo que se selecciona por default al abrir un partido, si está
# presente. Cámbialo si quieres que otro equipo sea el "equipo de seguimiento"
# (por ejemplo si vas a cargar partidos de la categoría femenil o de otro club).
TRACKED_TEAM_NAME = "Pumas UNAM"

# ------------------------------------------------------------------
# Modo manual (opcional): si quieres forzar la etiqueta o el orden de
# un partido en vez de que se genere solo, agrégalo aquí. La mayoría
# de las veces puedes dejar esta lista vacía y usar el modo automático.
# ------------------------------------------------------------------
@dataclass
class MatchConfig:
    id: str
    label: str
    stats_file: str
    events_file: str

MANUAL_MATCHES = [
    # MatchConfig(id="J4", label="J4 · Pumas UNAM vs León",
    #             stats_file="data/raw/Match_Stats_J4_vs_Leon.json",
    #             events_file="data/raw/Match_Events_J4_vs_Leon.json"),
]


# ------------------------------------------------------------------

SHOT_TYPES = {13: 'miss', 14: 'post', 15: 'saved', 16: 'goal'}
DEF_TYPES = {7: 'tackle', 8: 'interception', 12: 'clearance', 44: 'aerial', 49: 'recovery', 50: 'dispossessed'}

# Lista COMPLETA de estadísticas de equipo — esto alimenta la pestaña "Resumen"
# en pantalla, que debe mostrar todo el detalle disponible. El recorte a "las
# más importantes" para que la Página 1 del PDF quepa en una hoja se hace por
# separado, del lado del navegador (ver REPORT_KEY_WHITELIST en template.html),
# así que esta lista NO se recorta aquí.
TEAM_STAT_CATEGORIES = [
    ("Posesion y pase", [
        ('possessionPercentage', 'Posesión (%)'), ('totalPass', 'Pases intentados'), ('accuratePass', 'Pases completados'),
        ('totalFwdZonePass', 'Pases en campo rival'), ('totalBackZonePass', 'Pases en campo propio'),
        ('totalLongBalls', 'Balones largos'), ('accurateLongBalls', 'Balones largos completados'),
        ('totalCross', 'Centros intentados'), ('accurateCross', 'Centros completados'),
        ('totalChippedPass', 'Pases elevados'), ('totalThroughBall', 'Pases al hueco'),
        ('touches', 'Toques de balón'), ('carries', 'Conducciones'), ('progressiveCarries', 'Conducciones progresivas'),
    ]),
    ("Produccion ofensiva", [
        ('totalScoringAtt', 'Disparos totales'), ('ontargetScoringAtt', 'Disparos a puerta'),
        ('attemptsIbox', 'Disparos dentro del área'), ('attemptsObox', 'Disparos fuera del área'),
        ('blockedScoringAtt', 'Disparos bloqueados'), ('shotOffTarget', 'Disparos fuera'),
        ('wonCorners', 'Tiros de esquina'), ('totalCornersIntobox', 'Córners al área'),
        ('penAreaEntries', 'Entradas al área'), ('successfulPenAreaEntries', 'Entradas al área exitosas'),
        ('finalThirdEntries', 'Entradas al último tercio'), ('touchesInOppBox', 'Toques en área rival'),
        ('shotCreated', 'Ocasiones creadas'), ('totalAttAssist', 'Pases clave'),
    ]),
    ("Fase defensiva", [
        ('ballRecovery', 'Recuperaciones de balón'), ('interceptionWon', 'Intercepciones'),
        ('totalTackle', 'Entradas intentadas'), ('wonTackle', 'Entradas ganadas'),
        ('effectiveClearance', 'Despejes'), ('blockedPass', 'Pases bloqueados'),
        ('possWonDef3rd', 'Recuperaciones en tercio propio'), ('possWonMid3rd', 'Recuperaciones en tercio medio'),
        ('possWonAtt3rd', 'Recuperaciones en tercio rival'), ('ppda', 'PPDA (intensidad de presión)'),
    ]),
    ("Duelos", [
        ('duelWon', 'Duelos ganados'), ('duelLost', 'Duelos perdidos'),
        ('aerialWon', 'Duelos aéreos ganados'), ('aerialLost', 'Duelos aéreos perdidos'),
        ('totalContest', 'Regates intentados'), ('wonContest', 'Regates ganados'),
        ('dispossessed', 'Pérdidas por presión rival'),
    ]),
    ("Disciplina", [
        ('fkFoulWon', 'Faltas recibidas'), ('fkFoulLost', 'Faltas cometidas'),
        ('totalYellowCard', 'Tarjetas amarillas'), ('staffRed', 'Tarjetas rojas'),
        ('totalOffside', 'Fueras de lugar'), ('handBall', 'Manos'),
        ('errorLeadToShot', 'Errores que derivan en disparo'), ('errorLeadToGoal', 'Errores que derivan en gol'),
    ]),
    ("Portero", [
        ('saves', 'Atajadas'), ('goalsConceded', 'Goles recibidos'),
        ('totalHighClaim', 'Salidas por arriba'), ('goodHighClaim', 'Salidas por arriba exitosas'),
        ('goalKicks', 'Saques de meta'), ('accurateGoalKicks', 'Saques de meta completados'),
    ]),
]

PLAYER_STAT_GROUPS = [
    ("Participacion y pase", [
        ('minsPlayed', 'Minutos jugados'), ('touches', 'Toques de balón'),
        ('totalPass', 'Pases intentados'), ('accuratePass', 'Pases completados'),
        ('totalChippedPass', 'Pases elevados'), ('totalThroughBall', 'Pases al hueco'),
        ('successfulFinalThirdPasses', 'Pases en último tercio'),
    ]),
    ("Produccion ofensiva", [
        ('totalScoringAtt', 'Disparos totales'), ('ontargetScoringAtt', 'Disparos a puerta'),
        ('penAreaEntries', 'Entradas al área'), ('progressiveCarries', 'Conducciones progresivas'),
        ('wonContest', 'Regates ganados'), ('totalContest', 'Regates intentados'),
    ]),
    ("Fase defensiva", [
        ('duelWon', 'Duelos ganados'), ('duelLost', 'Duelos perdidos'), ('aerialWon', 'Duelos aéreos ganados'),
        ('ballRecovery', 'Recuperaciones'), ('interceptionWon', 'Intercepciones'),
        ('totalTackle', 'Entradas intentadas'), ('wonTackle', 'Entradas ganadas'),
        ('effectiveClearance', 'Despejes'), ('fkFoulWon', 'Faltas recibidas'), ('fkFoulLost', 'Faltas cometidas'),
    ]),
]


def qual(event, qualifier_id):
    for q in event.get('qualifier', []):
        if q.get('qualifierId') == qualifier_id:
            return q.get('value')
    return None


# ------------------------------------------------------------------
# Auto-descubrimiento de partidos en data/raw/
# ------------------------------------------------------------------
def _classify_raw_file(path):
    """Returns 'stats', 'events', or None if the file isn't a recognised Opta file."""
    try:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None, None
    live = d.get('liveData', {})
    match_id = d.get('matchInfo', {}).get('id')
    if 'lineUp' in live:
        return 'stats', match_id
    if 'event' in live:
        return 'events', match_id
    return None, match_id


def _auto_label(stats_json):
    mi = stats_json['matchInfo']
    comp = mi.get('competition', {}).get('name', '')
    week = mi.get('week')
    contestants = mi['contestant']
    names = [c['name'] for c in contestants]
    date = mi.get('localDate') or mi.get('date', '')
    date = date.replace('Z', '')
    parts = [p for p in [comp, f"J{week}" if week else None] if p]
    prefix = ' · '.join(parts)
    matchup = f"{names[0]} vs {names[1]}"
    return f"{prefix} · {matchup}" if prefix else matchup, date


def discover_matches(raw_dir):
    """Scans raw_dir, pairs Stats+Events files by Opta's own match id, and builds
    a MatchConfig list automatically. No filenames or manual config required."""
    stats_by_id, events_by_id = {}, {}
    for path in sorted(glob.glob(os.path.join(raw_dir, '*.json'))):
        kind, match_id = _classify_raw_file(path)
        if not match_id:
            continue
        if kind == 'stats':
            stats_by_id[match_id] = path
        elif kind == 'events':
            events_by_id[match_id] = path

    matches = []
    for match_id, stats_path in stats_by_id.items():
        events_path = events_by_id.get(match_id)
        if not events_path:
            print(f"[warn] {stats_path} no tiene su archivo de Events correspondiente (mismo match id) — se omite.")
            continue
        stats_json = json.load(open(stats_path, encoding='utf-8'))
        label, date = _auto_label(stats_json)
        matches.append(MatchConfig(id=match_id, label=label, stats_file=stats_path, events_file=events_path))

    # unmatched events files (rare, but flag them so nothing silently disappears)
    for match_id, events_path in events_by_id.items():
        if match_id not in stats_by_id:
            print(f"[warn] {events_path} no tiene su archivo de Stats correspondiente (mismo match id) — se omite.")

    # sort chronologically-ish using the date embedded in the label when possible; fall back to file order
    matches.sort(key=lambda m: m.label)
    return matches


def r1(v):
    return round(v, 1) if v is not None else None


def num(v, cast=float):
    try:
        return cast(v)
    except (TypeError, ValueError):
        return 0


def extract_match_events(match: MatchConfig):
    """Returns (label, competition, team_order, teams_dict) for events_data.json"""
    stats = json.load(open(match.stats_file, encoding='utf-8'))
    events = json.load(open(match.events_file, encoding='utf-8'))

    contestants = stats['matchInfo']['contestant']  # [home, away], each has id/name
    team_order = [c['id'] for c in contestants]
    team_names = {c['id']: c['name'] for c in contestants}
    competition = stats['matchInfo'].get('competition', {}).get('name', 'Otros')

    player_meta = {}
    for team in stats['liveData']['lineUp']:
        for p in team['player']:
            player_meta[p['playerId']] = {
                'shirt': p.get('shirtNumber'), 'name': p.get('matchName'),
                'position': p.get('position'), 'team': team['contestantId'],
            }

    raw_events = [e for e in events['liveData']['event'] if e.get('typeId') not in (34,) and e.get('playerId')]
    raw_events.sort(key=lambda e: (e['periodId'], e['timeMin'], e.get('timeSec', 0), e['eventId']))

    teams_out = {}
    for cid in team_order:
        team_events = [e for e in raw_events if e['contestantId'] == cid]

        passes = []
        for i, e in enumerate(team_events):
            if e.get('typeId') != 1:
                continue
            ex, ey = qual(e, 140), qual(e, 141)
            receiver_shirt = None
            if e.get('outcome') == 1:
                for nxt in team_events[i + 1:i + 4]:
                    if nxt.get('playerId') and nxt['playerId'] != e['playerId']:
                        receiver_shirt = player_meta.get(nxt['playerId'], {}).get('shirt')
                        break
            passes.append({
                'm': e['timeMin'], 'p': player_meta.get(e['playerId'], {}).get('shirt'),
                'x': r1(e['x']), 'y': r1(e['y']),
                'ex': r1(float(ex)) if ex else None, 'ey': r1(float(ey)) if ey else None,
                'o': e['outcome'], 'r': receiver_shirt,
            })

        shots = [{'m': e['timeMin'], 'p': player_meta.get(e.get('playerId'), {}).get('shirt'),
                   'x': r1(e['x']), 'y': r1(e['y']), 'res': SHOT_TYPES[e['typeId']]}
                  for e in team_events if e.get('typeId') in SHOT_TYPES]

        defs = [{'m': e['timeMin'], 'p': player_meta.get(e.get('playerId'), {}).get('shirt'),
                  'x': r1(e['x']), 'y': r1(e['y']), 't': DEF_TYPES[e['typeId']], 'o': e.get('outcome')}
                 for e in team_events if e.get('typeId') in DEF_TYPES]

        roster = {str(m['shirt']): {'name': m['name'], 'pos': m['position']}
                   for m in player_meta.values() if m['team'] == cid and m.get('shirt') is not None}

        teams_out[cid] = {'name': team_names[cid], 'roster': roster, 'passes': passes, 'shots': shots, 'defActions': defs}

    return match.label, competition, team_order, teams_out


def extract_player_full_stats(match: MatchConfig):

    stats = json.load(open(match.stats_file, encoding='utf-8'))

    out = {}

    for team in stats['liveData']['lineUp']:

        cid = team['contestantId']

        out[cid] = {}

        for p in team['player']:

            st = {
                s.get('type'): s.get('value')
                for s in p.get('stat', [])
                if isinstance(s, dict) and s.get('type') is not None
            }

            shirt = p.get('shirtNumber')

            if shirt is None:
                continue

            row = {}

            for _, keys in PLAYER_STAT_GROUPS:

                for k, _ in keys:

                    v = st.get(k)

                    try:
                        v = float(v)
                        row[k] = int(v) if v == int(v) else round(v, 1)

                    except (TypeError, ValueError):
                        row[k] = 0

            out[cid][str(shirt)] = row

    return out

def extract_team_summary(match: MatchConfig):
    stats = json.load(open(match.stats_file, encoding='utf-8'))
    contestants = stats['matchInfo']['contestant']
    team_order = [c['id'] for c in contestants]
    team_names = {c['id']: c['name'] for c in contestants}

    team_stats = {}
    for team in stats['liveData']['lineUp']:
        team_stats[team['contestantId']] = {s['type']: s['value'] for s in team['stat']}

    def val(d, k):
        v = d.get(k)
        try:
            v = float(v)
            return int(v) if v == int(v) else round(v, 1)
        except (TypeError, ValueError):
            return 0

    categories = []
    for cat_name, keys in TEAM_STAT_CATEGORIES:
        rows = []
        for k, label in keys:
            row = {'key': k, 'label': label}
            for cid in team_order:
                row[cid] = val(team_stats.get(cid, {}), k)
            rows.append(row)
        categories.append({'cat': cat_name, 'rows': rows})

    scores = stats.get('liveData', {}).get('matchDetails', {}).get('scores', {})
    # Prefer "aet" (after extra time) if the match went to extra time — otherwise "ft" (90 min).
    reg = scores.get('aet') or scores.get('ft', {})
    pen = scores.get('pen', {})
    score = None
    if len(team_order) == 2 and reg:
        score = {
            team_order[0]: int(reg.get('home', 0) or 0),
            team_order[1]: int(reg.get('away', 0) or 0),
        }
        if pen:
            score['penalties'] = {
                team_order[0]: int(pen.get('home', 0) or 0),
                team_order[1]: int(pen.get('away', 0) or 0),
            }

    return {'teamOrder': team_order, 'teamNames': team_names, 'categories': categories, 'score': score}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    auto_matches = discover_matches(RAW_DIR)
    manual_ids = {m.id for m in MANUAL_MATCHES}
    matches = list(MANUAL_MATCHES) + [m for m in auto_matches if m.id not in manual_ids]

    if not matches:
        print(f"No se encontraron pares de archivos Stats+Events en {RAW_DIR}/.")
        print("Copia ahí los dos JSON de un partido (cualquier nombre) y vuelve a correr este script.")
        return

    events_data = {}
    player_full_stats = {}
    team_summary = {}

    for match in matches:
        label, competition, team_order, teams = extract_match_events(match)
        events_data[match.id] = {'label': label, 'competition': competition, 'teamOrder': team_order, 'teams': teams}
        player_full_stats[match.id] = extract_player_full_stats(match)
        team_summary[match.id] = extract_team_summary(match)
        print(f"[ok] {label}")

    with open(os.path.join(OUT_DIR, 'events_data.json'), 'w', encoding='utf-8') as f:
        json.dump(events_data, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT_DIR, 'player_full_stats.json'), 'w', encoding='utf-8') as f:
        json.dump(player_full_stats, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT_DIR, 'team_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(team_summary, f, ensure_ascii=False, separators=(',', ':'))

    print(f"\nListo. {len(matches)} partido(s) escritos en {OUT_DIR}/")
    print("Corre build_html.py para generar el archivo final.")


if __name__ == '__main__':
    main()
