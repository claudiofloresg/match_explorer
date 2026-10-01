"""
comparativo_previa.py
=======================
Genera el comparativo de estadísticas acumuladas entre dos equipos (por
ejemplo Pumas vs el próximo rival), buscando automáticamente sus partidos
en data/raw/ — no hace falta listar archivos a mano, ni saber de memoria
el contestantId de cada equipo.

Sirve para cualquier rival futuro: solo cambias el nombre en --team_b.

USO
----
    python3 comparativo_previa.py --team_a "Pumas UNAM" --team_b "Necaxa"

Por default toma las últimas 4 jornadas disponibles de cada equipo. Si
quieres otro número:

    python3 comparativo_previa.py --team_a "Pumas UNAM" --team_b "Necaxa" --n 6

Si tienes categorías con nombres parecidos (ej. "Pumas UNAM" y
"Pumas UNAM U21"), el script busca primero una coincidencia EXACTA de
nombre antes que una parcial, así no se te mezclan por accidente. Si aun
así hay más de una coincidencia, te dice cuáles encontró para que
especifiques mejor.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_DIR = Path(__file__).parent / "output_reportes"

# Stats que deben PROMEDIARSE en vez de sumarse al acumular jornadas
# (posesión, ppda, y cualquier métrica tipo "%"). Todo lo que no esté aquí se suma.
RATE_STATS = {
    "possessionPercentage",
    "ppda",
}

# ============================================================
# TRADUCCIÓN DE MÉTRICAS DE OPTA
# ============================================================
# Cubre las métricas que trae MA2 (Match Stats). Si algún día aparece una
# métrica nueva que no está aquí, el script no truena — simplemente muestra
# la clave original de Opta tal cual, para que sepas cuál falta agregar.
TRANSLATIONS = {
    "accurateBackZonePass": "Pases completados en campo propio",
    "accurateChippedPass": "Pases elevados completados",
    "accurateCornersIntobox": "Córners al área completados",
    "accurateCross": "Centros completados",
    "accurateCrossNocorner": "Centros completados (sin córners)",
    "accurateFlickOn": "Desvíos de cabeza completados",
    "accurateFreekickCross": "Centros de tiro libre completados",
    "accurateFwdZonePass": "Pases completados en campo rival",
    "accurateGoalKicks": "Saques de meta completados",
    "accurateKeeperSweeper": "Salidas del portero (líbero) completadas",
    "accurateKeeperThrows": "Saques de portero con la mano completados",
    "accurateLaunches": "Balones largos directos completados",
    "accurateLayoffs": "Paredes / toques de apoyo completados",
    "accurateLongBalls": "Balones largos completados",
    "accuratePass": "Pases completados",
    "accuratePullBack": "Pases atrás desde banda completados",
    "accurateThroughBall": "Pases al hueco completados",
    "accurateThrows": "Saques de banda completados",
    "aerialLost": "Duelos aéreos perdidos",
    "aerialWon": "Duelos aéreos ganados",
    "attAssistOpenplay": "Asistencias de tiro en juego abierto",
    "attAssistSetplay": "Asistencias de tiro a balón parado",
    "attBxCentre": "Disparos desde el centro del área",
    "attBxLeft": "Disparos desde la izquierda del área",
    "attBxRight": "Disparos desde la derecha del área",
    "attCmissLeft": "Disparos fuera, centro-izquierda",
    "attCmissRight": "Disparos fuera, centro-derecha",
    "attCorner": "Disparos directos de córner",
    "attFreekickTotal": "Disparos de tiro libre",
    "attGoalLowCentre": "Goles rasos al centro",
    "attGoalLowLeft": "Goles rasos a la izquierda",
    "attGoalLowRight": "Goles rasos a la derecha",
    "attHdGoal": "Goles de cabeza",
    "attHdMiss": "Remates de cabeza fuera",
    "attHdTarget": "Remates de cabeza a puerta",
    "attHdTotal": "Remates de cabeza totales",
    "attIboxBlocked": "Disparos bloqueados dentro del área",
    "attIboxGoal": "Goles dentro del área",
    "attIboxMiss": "Disparos fuera, dentro del área",
    "attIboxTarget": "Disparos a puerta dentro del área",
    "attLfGoal": "Goles con pierna izquierda",
    "attLfTarget": "Disparos a puerta con pierna izquierda",
    "attLfTotal": "Disparos totales con pierna izquierda",
    "attMissHigh": "Disparos altos fuera",
    "attMissHighLeft": "Disparos altos fuera por la izquierda",
    "attMissHighRight": "Disparos altos fuera por la derecha",
    "attMissLeft": "Disparos fuera por la izquierda",
    "attMissRight": "Disparos fuera por la derecha",
    "attOboxBlocked": "Disparos bloqueados fuera del área",
    "attOboxMiss": "Disparos fuera, desde fuera del área",
    "attOboxTarget": "Disparos a puerta desde fuera del área",
    "attObxCentre": "Disparos desde el centro, fuera del área",
    "attOpenplay": "Disparos en juego abierto",
    "attPenGoal": "Goles de penal",
    "attRfGoal": "Goles con pierna derecha",
    "attRfTarget": "Disparos a puerta con pierna derecha",
    "attRfTotal": "Disparos totales con pierna derecha",
    "attSetpiece": "Disparos a balón parado",
    "attSvHighCentre": "Disparos altos al centro atajados",
    "attSvLowCentre": "Disparos rasos al centro atajados",
    "attSvLowLeft": "Disparos rasos a la izquierda atajados",
    "attemptedTackleFoul": "Faltas por entradas",
    "attemptsConcededIbox": "Disparos recibidos dentro del área",
    "attemptsConcededObox": "Disparos recibidos fuera del área",
    "attemptsIbox": "Disparos dentro del área",
    "attemptsObox": "Disparos fuera del área",
    "backwardPass": "Pases hacia atrás",
    "ballRecovery": "Recuperaciones de balón",
    "bigChanceCreated": "Ocasiones claras creadas",
    "bigChanceMissed": "Ocasiones claras falladas",
    "bigChanceSaves": "Ocasiones claras atajadas",
    "bigChanceScored": "Ocasiones claras convertidas",
    "blockedCross": "Centros bloqueados",
    "blockedPass": "Pases bloqueados",
    "blockedScoringAtt": "Disparos bloqueados",
    "carries": "Conducciones de balón",
    "challengeLost": "Duelos 1v1 perdidos",
    "contentiousDecision": "Decisiones arbitrales polémicas",
    "cornerTaken": "Córners botados",
    "crosses18yard": "Centros desde dentro de 18 yardas",
    "crosses18yardplus": "Centros desde fuera de 18 yardas",
    "defensiveActions": "Acciones defensivas",
    "dispossessed": "Pérdidas de balón por presión rival",
    "divingSave": "Atajadas con estirada",
    "duelLost": "Duelos perdidos",
    "duelWon": "Duelos ganados",
    "effectiveBlockedCross": "Centros bloqueados de forma efectiva",
    "effectiveClearance": "Despejes efectivos",
    "effectiveHeadClearance": "Despejes de cabeza efectivos",
    "errorLeadToGoal": "Errores que derivan en gol",
    "errorLeadToShot": "Errores que derivan en disparo",
    "finalThirdEntries": "Entradas al último tercio",
    "finalThirdEntriesOpenPlay": "Entradas al último tercio en juego abierto",
    "firstHalfGoals": "Goles en el primer tiempo",
    "fkFoulLost": "Faltas cometidas",
    "fkFoulWon": "Faltas recibidas",
    "formationUsed": "Formación utilizada (código interno Opta)",
    "forwardGoals": "Goles de delanteros",
    "foulThrowIn": "Saques de banda mal ejecutados",
    "fouledFinalThird": "Faltas recibidas en el último tercio",
    "freekickCross": "Centros de tiro libre",
    "fwdPass": "Pases hacia adelante",
    "goalAssist": "Asistencias de gol",
    "goalAssistIntentional": "Asistencias de gol intencionales",
    "goalAssistOpenplay": "Asistencias de gol en juego abierto",
    "goalKicks": "Saques de meta",
    "goals": "Goles",
    "goalsConceded": "Goles recibidos",
    "goalsConcededIbox": "Goles recibidos dentro del área",
    "goalsConcededObox": "Goles recibidos fuera del área",
    "goalsIbox": "Goles dentro del área",
    "goalsOpenplay": "Goles en juego abierto",
    "goodHighClaim": "Salidas por arriba exitosas",
    "handBall": "Manos",
    "headClearance": "Despejes de cabeza",
    "interception": "Intercepciones",
    "interceptionWon": "Intercepciones",
    "interceptionsInBox": "Intercepciones dentro del área",
    "keeperThrows": "Saques de portero con la mano",
    "lastManTackle": "Entradas como último hombre",
    "leftsidePass": "Pases por la izquierda",
    "longPassOwnToOpp": "Balones largos de campo propio a campo rival",
    "longPassOwnToOppSuccess": "Balones largos completados de campo propio a campo rival",
    "lostCorners": "Córners con pérdida de posesión",
    "midfielderGoals": "Goles de mediocampistas",
    "offtargetAttAssist": "Pases clave que terminan en disparo fuera",
    "ontargetAttAssist": "Pases clave (a disparo a puerta)",
    "ontargetScoringAtt": "Disparos a puerta",
    "openPlayPass": "Pases en juego abierto",
    "oppositionPasses": "Pases del rival bajo presión",
    "outfielderBlock": "Bloqueos de jugador de campo",
    "overrun": "Balones que se le van largos al jugador",
    "passesLeft": "Pases hacia la izquierda",
    "passesRight": "Pases hacia la derecha",
    "penAreaEntries": "Entradas al área",
    "penAreaEntriesOpenPlay": "Entradas al área en juego abierto",
    "penaltyWon": "Penales ganados",
    "possLostAll": "Pérdidas de posesión totales",
    "possLostCtrl": "Pérdidas de posesión por mal control",
    "possWonAtt3rd": "Recuperaciones en el tercio de ataque",
    "possWonDef3rd": "Recuperaciones en el tercio defensivo",
    "possWonMid3rd": "Recuperaciones en el tercio medio",
    "possessionPercentage": "Posesión (%)",
    "ppda": "PPDA (intensidad de presión)",
    "progressiveCarries": "Conducciones progresivas",
    "ptsDroppedWinningPos": "Puntos perdidos yendo ganando",
    "ptsGainedLosingPos": "Puntos rescatados yendo perdiendo",
    "punches": "Despejes de puños del portero",
    "putThrough": "Pases al hueco intentados",
    "rightsidePass": "Pases por la derecha",
    "savedIbox": "Disparos atajados dentro del área",
    "savedObox": "Disparos atajados fuera del área",
    "saves": "Atajadas",
    "shieldBallOop": "Balones protegidos fuera de juego",
    "shotCreated": "Ocasiones de disparo creadas",
    "shotOffTarget": "Disparos fuera",
    "sixYardBlock": "Bloqueos dentro del área chica",
    "staffRed": "Expulsiones de cuerpo técnico",
    "subsGoals": "Goles de jugadores de cambio",
    "subsMade": "Cambios realizados",
    "successfulFinalThirdEntries": "Entradas exitosas al último tercio",
    "successfulFinalThirdEntriesOpenPlay": "Entradas exitosas al último tercio en juego abierto",
    "successfulFinalThirdPasses": "Pases exitosos en el último tercio",
    "successfulOpenPlayPass": "Pases completados en juego abierto",
    "successfulPenAreaEntries": "Entradas exitosas al área",
    "successfulPenAreaEntriesOpenPlay": "Entradas exitosas al área en juego abierto",
    "successfulPutThrough": "Pases al hueco completados",
    "totalAttAssist": "Pases clave (total)",
    "totalBackZonePass": "Pases intentados en campo propio",
    "totalChippedPass": "Pases elevados intentados",
    "totalClearance": "Despejes totales",
    "totalContest": "Regates intentados",
    "totalCornersIntobox": "Córners al área intentados",
    "totalCross": "Centros intentados",
    "totalCrossNocorner": "Centros intentados (sin córners)",
    "totalFinalThirdPasses": "Pases intentados en el último tercio",
    "totalFlickOn": "Desvíos de cabeza intentados",
    "totalFwdZonePass": "Pases intentados en campo rival",
    "totalHighClaim": "Salidas por arriba intentadas",
    "totalKeeperSweeper": "Salidas del portero (líbero) intentadas",
    "totalLaunches": "Balones largos directos intentados",
    "totalLayoffs": "Paredes / toques de apoyo intentados",
    "totalLongBalls": "Balones largos intentados",
    "totalOffside": "Fueras de lugar",
    "totalPass": "Pases intentados",
    "totalPullBack": "Pases atrás desde banda intentados",
    "totalScoringAtt": "Disparos totales",
    "totalTackle": "Entradas intentadas",
    "totalThroughBall": "Pases al hueco intentados",
    "totalThrows": "Saques de banda intentados",
    "totalYellowCard": "Tarjetas amarillas",
    "touches": "Toques de balón",
    "touchesInFinalThird": "Toques en el último tercio",
    "touchesInOppBox": "Toques en el área rival",
    "unsuccessfulTouch": "Toques que resultan en pérdida",
    "wonContest": "Regates ganados",
    "wonCorners": "Tiros de esquina",
    "wonTackle": "Entradas ganadas",
    "attCmissHighLeft": "Disparos altos fuera, centro-izquierda",
    "attFastbreak": "Disparos de contraataque",
    "attFreekickMiss": "Tiros libres fuera",
    "attFreekickTarget": "Tiros libres a puerta",
    "attGoalHighLeft": "Goles altos a la izquierda",
    "attGoalHighRight": "Goles altos a la derecha",
    "attHdPost": "Remates de cabeza al poste",
    "attIboxPost": "Disparos al poste dentro del área",
    "attLgCentre": "Disparos rasos al centro",
    "attOboxGoal": "Goles desde fuera del área",
    "attObxLeft": "Disparos desde la izquierda, fuera del área",
    "attPostLeft": "Disparos al poste por la izquierda",
    "attSvHighLeft": "Disparos altos a la izquierda atajados",
    "attSvHighRight": "Disparos altos a la derecha atajados",
    "attSvLowRight": "Disparos rasos a la derecha atajados",
    "cleanSheet": "Partidos sin recibir gol (portería en cero)",
    "defenderGoals": "Goles de defensas",
    "goalsObox": "Goles desde fuera del área",
    "hitWoodwork": "Disparos al poste o travesaño",
    "penGoalsConceded": "Goles de penal recibidos",
    "penaltyConceded": "Penales concedidos",
    "penaltyFaced": "Penales enfrentados (portero)",
    "postScoringAtt": "Disparos al poste",
    "shotFastbreak": "Disparos de contraataque",
    "totalFastbreak": "Contraataques",
    "totalRedCard": "Tarjetas rojas",
    "attCmissHigh": "Disparos altos fuera, centro",
    "attCmissHighRight": "Disparos altos fuera, centro-derecha",
    "attGoalHighCentre": "Goles altos al centro",
    "attIboxOwnGoal": "Autogoles dentro del área",
    "attObpGoal": "Goles tras rechace",
    "attOneOnOne": "Mano a mano ante el portero",
    "goalAssistSetplay": "Asistencias de gol a balón parado",
    "ownGoals": "Autogoles",
    "secondYellow": "Segundas tarjetas amarillas",
    "staffYellow": "Amonestaciones a cuerpo técnico",
}


def traducir(metric_key):
    """Traduce una métrica de Opta al español. Si no la conocemos, regresa
    la clave original tal cual (para que el reporte nunca se rompa por una
    métrica nueva que todavía no hemos agregado al diccionario)."""
    return TRANSLATIONS.get(metric_key, metric_key)


# ============================================================
# CARGA Y BÚSQUEDA AUTOMÁTICA DE PARTIDOS
# ============================================================

def _load_stats_files():
    """Escanea data/raw/ y regresa los JSON que son Match Stats (traen
    liveData.lineUp) — ignora los de Match Events y cualquier otro archivo,
    y no repite un mismo partido aunque tengas el Stats y el Events juntos."""
    matches = []
    seen_ids = set()
    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if "lineUp" not in d.get("liveData", {}):
            continue
        mid = d.get("matchInfo", {}).get("id")
        if not mid or mid in seen_ids:
            continue
        seen_ids.add(mid)
        matches.append(d)
    return matches


def find_team(all_matches, name_query, competition_query=None):
    """Encuentra el contestantId + nombre oficial a partir de un texto de
    búsqueda. Prioriza coincidencia EXACTA (sin importar mayúsculas) sobre
    coincidencia parcial, para no mezclar 'Pumas UNAM' con 'Pumas UNAM U21'.

    Si dos equipos comparten el nombre EXACTO (pasa, por ejemplo, si Liga MX
    Femenil también se llama "Pumas UNAM" a secas en los datos de Opta), se
    desempata por competencia — usa competition_query, o si solo uno de los
    candidatos tiene partidos descargados, se usa ese."""
    query_low = name_query.strip().lower()
    comp_low = competition_query.strip().lower() if competition_query else None

    # id -> {"name": str, "competitions": set(), "n_matches": int}
    candidates = {}
    for d in all_matches:
        comp_name = d.get("matchInfo", {}).get("competition", {}).get("name", "?")
        for c in d["matchInfo"]["contestant"]:
            name_low = c["name"].lower()
            is_exact = name_low == query_low
            is_partial = query_low in name_low
            if not (is_exact or is_partial):
                continue
            bucket = candidates.setdefault(c["id"], {"name": c["name"], "exact": is_exact, "competitions": set(), "n_matches": 0})
            bucket["competitions"].add(comp_name)
            bucket["n_matches"] += 1

    if not candidates:
        raise SystemExit(
            f"No encontré ningún equipo que coincida con '{name_query}' en data/raw/.\n"
            f"Revisa que ya tengas al menos un partido de ese equipo descargado."
        )

    # Si hay coincidencias exactas, quédate solo con esas (mismo criterio de antes).
    exact_ids = {cid: info for cid, info in candidates.items() if info["exact"]}
    pool = exact_ids if exact_ids else candidates

    # Si además nos dieron competencia, filtra por ahí (exacto antes que parcial,
    # para que "Liga MX" no haga match con "Liga MX Femenil" por accidente).
    if comp_low:
        exact_comp = {cid: info for cid, info in pool.items()
                      if any(c.lower() == comp_low for c in info["competitions"])}
        if exact_comp:
            pool = exact_comp
        else:
            pool = {cid: info for cid, info in pool.items()
                    if any(comp_low in c.lower() for c in info["competitions"])}
        if not pool:
            raise SystemExit(
                f"'{name_query}' no tiene partidos en una competencia que coincida con "
                f"'{competition_query}' en data/raw/."
            )

    if len(pool) > 1:
        opciones = "\n".join(
            f"  - {info['name']}  [{', '.join(sorted(info['competitions']))}]  "
            f"({info['n_matches']} partido(s) en data/raw/)"
            for info in pool.values()
        )
        raise SystemExit(
            f"'{name_query}' coincide con más de un equipo, sé más específico:\n{opciones}\n\n"
            f"Agrega --competition_a o --competition_b para desempatar, por ejemplo:\n"
            f'  --competition_a "Liga MX"'
        )

    team_id, info = next(iter(pool.items()))
    team_name = info["name"]
    return team_id, team_name


def matches_for_team(all_matches, team_id):
    """Todos los partidos (ya jugados, con Stats) donde participó este equipo,
    ordenados cronológicamente (el más reciente al final)."""
    out = [d for d in all_matches if team_id in [c["id"] for c in d["matchInfo"]["contestant"]]]
    out.sort(key=lambda d: d["matchInfo"].get("localDate") or d["matchInfo"].get("date", ""))
    return out


def extract_team_stats(match_json, contestant_id):
    for team in match_json["liveData"]["lineUp"]:
        if team["contestantId"] != contestant_id:
            continue
        stats = {}
        for s in team.get("stat", []):
            stat_type, raw_value = s.get("type"), s.get("value")
            if stat_type is None or raw_value is None:
                continue
            try:
                stats[stat_type] = float(raw_value)
            except ValueError:
                continue
        return stats
    return {}


def build_team_block(all_matches, team_id, team_name, n):
    """Últimos n partidos de este equipo, con sus stats extraídas."""
    team_matches = matches_for_team(all_matches, team_id)[-n:]
    rows = []
    for d in team_matches:
        week = d["matchInfo"].get("week", "?")
        rival = next(c["name"] for c in d["matchInfo"]["contestant"] if c["id"] != team_id)
        rows.append({
            "jornada": f"J{week}",
            "rival": rival,
            "stats": extract_team_stats(d, team_id),
        })
    return rows


def accumulate(stats_list):
    """Suma conteos, promedia las métricas en RATE_STATS. Rellena con 0 lo
    que no aparezca en algún partido, para que los promedios sean correctos."""
    all_keys = set()
    for s in stats_list:
        all_keys.update(s.keys())
    n = len(stats_list) or 1
    combined = {}
    for key in all_keys:
        values = [s.get(key, 0) for s in stats_list]
        combined[key] = (sum(values) / n) if key in RATE_STATS else sum(values)
    return combined


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team_a", required=True, help='Ej. "Pumas UNAM"')
    parser.add_argument("--team_b", required=True, help='Ej. "Necaxa"')
    parser.add_argument("--competition_a", default=None, help='Opcional, para desempatar. Ej. "Liga MX"')
    parser.add_argument("--competition_b", default=None, help='Opcional, para desempatar. Ej. "Liga MX Femenil"')
    parser.add_argument("--n", type=int, default=4, help="Cuántas jornadas recientes tomar por equipo (default 4)")
    args = parser.parse_args()

    all_matches = _load_stats_files()
    if not all_matches:
        raise SystemExit(f"No encontré archivos de Match Stats en {RAW_DIR}/.")

    id_a, name_a = find_team(all_matches, args.team_a, args.competition_a)
    id_b, name_b = find_team(all_matches, args.team_b, args.competition_b)

    rows_a = build_team_block(all_matches, id_a, name_a, args.n)
    rows_b = build_team_block(all_matches, id_b, name_b, args.n)

    print(f"{name_a}: {len(rows_a)} jornada(s) -> "
          f"{', '.join(r['jornada'] + ' vs ' + r['rival'] for r in rows_a)}")
    print(f"{name_b}: {len(rows_b)} jornada(s) -> "
          f"{', '.join(r['jornada'] + ' vs ' + r['rival'] for r in rows_b)}")

    if len(rows_a) < args.n:
        print(f"[aviso] Solo hay {len(rows_a)} partido(s) de {name_a} en data/raw/ (pediste {args.n}).")
    if len(rows_b) < args.n:
        print(f"[aviso] Solo hay {len(rows_b)} partido(s) de {name_b} en data/raw/ (pediste {args.n}).")

    acum_a = accumulate([r["stats"] for r in rows_a])
    acum_b = accumulate([r["stats"] for r in rows_b])

    all_metrics = sorted(set(acum_a) | set(acum_b), key=traducir)

    df_acumulado = pd.DataFrame({
        "Métrica": {m: traducir(m) for m in all_metrics},
        "Clave Opta": {m: m for m in all_metrics},
        f"{name_a} (acumulado)": {m: acum_a.get(m, 0) for m in all_metrics},
        f"{name_b} (acumulado)": {m: acum_b.get(m, 0) for m in all_metrics},
    })
    df_acumulado[f"{name_a} (acumulado)"] = df_acumulado[f"{name_a} (acumulado)"].round(2)
    df_acumulado[f"{name_b} (acumulado)"] = df_acumulado[f"{name_b} (acumulado)"].round(2)
    df_acumulado[f"Diferencia ({name_a} - {name_b})"] = (
        df_acumulado[f"{name_a} (acumulado)"] - df_acumulado[f"{name_b} (acumulado)"]
    ).round(2)
    df_acumulado = df_acumulado.set_index("Métrica")

    print("\n" + "=" * 70)
    print(f"TABLA ACUMULADA — {name_a} vs {name_b}  "
          f"({len(all_metrics)} métricas, {len(rows_a)}+{len(rows_b)} jornadas)")
    print("=" * 70)
    print(df_acumulado.to_string())

    rows_table = []
    for metric in all_metrics:
        row = {"Métrica": traducir(metric), "Clave Opta": metric}
        for r in rows_a:
            row[f"{name_a} {r['jornada']} (vs {r['rival']})"] = r["stats"].get(metric, 0)
        row[f"{name_a} Acumulado"] = acum_a.get(metric, 0)
        for r in rows_b:
            row[f"{name_b} {r['jornada']} (vs {r['rival']})"] = r["stats"].get(metric, 0)
        row[f"{name_b} Acumulado"] = acum_b.get(metric, 0)
        rows_table.append(row)
    df_por_jornada = pd.DataFrame(rows_table).round(2)

    OUT_DIR.mkdir(exist_ok=True)
    safe_a, safe_b = name_a.replace(" ", "_"), name_b.replace(" ", "_")
    out_name = f"comparativo_{safe_a}_vs_{safe_b}"

    with pd.ExcelWriter(OUT_DIR / f"{out_name}.xlsx") as writer:
        df_acumulado.to_excel(writer, sheet_name="Acumulado")
        df_por_jornada.to_excel(writer, sheet_name="Por jornada", index=False)
    df_acumulado.to_csv(OUT_DIR / f"{out_name}_acumulado.csv")

    print(f"\n✅ Generado: {OUT_DIR / (out_name + '.xlsx')}  (2 hojas) + CSV")


if __name__ == "__main__":
    main()
