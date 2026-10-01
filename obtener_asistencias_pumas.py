"""
obtener_asistencias_pumas.py

Extrae, para cada gol de Pumas en uno o varios partidos, el goleador y su asistente
a partir de los JSON de eventos (MA3 - Match Events) generados por tu pipeline
(fetch_from_api.py -> build_data.py).

Lógica Opta:
- Un gol es un evento con typeId == 16.
- El qualifier con id 55 ("Related Event ID") en el evento de gol apunta al
  eventId del pase que originó la jugada (la asistencia).
- Si no existe ese qualifier, el gol no tiene asistencia registrada
  (jugada individual, penal, rebote, gol olímpico, etc.).

NOTA: Si tu build_data.py ya "aplana" los qualifiers a otro formato
(por ejemplo dict {qualifierId: value} en vez de lista de dicts), ajusta
la función `obtener_qualifier()` de acuerdo a tu estructura real.
"""

import json
import glob
import csv
from pathlib import Path

# ---- CONFIGURA ESTO ----
PUMAS_FEMENIL_CONTESTANT_ID = "aav9njbcwyltszy8ia7dwqxyi"  # <-- reemplazar
CARPETA_JSON = "data/raw"  # carpeta donde build_data.py guarda los JSON por partido

QUALIFIER_ASISTENCIA = 55   # "Related Event ID" en Opta
QUALIFIER_AUTOGOL = 28      # "Own goal" en Opta
 
GOAL_TYPE_ID = 16
PASS_TYPE_ID = 1
 
 
def obtener_qualifier(evento, qualifier_id):
    """Busca el valor de un qualifier específico dentro de un evento.
    Soporta lista de dicts [{'qualifierId': x, 'value': y}, ...]
    Devuelve el valor si existe, o None si no está presente.
    Para qualifiers "bandera" (sin value, ej. 28 Own goal) devuelve True.
    """
    for q in evento.get("qualifier", evento.get("qualifiers", [])):
        qid = q.get("qualifierId", q.get("id"))
        if qid == qualifier_id:
            return q.get("value", True) if q.get("value") is not None else True
    return None
 
 
def nombre_jugador(evento):
    return (
        evento.get("playerName")
        or evento.get("player_name")
        or evento.get("playerId")
        or "Desconocido"
    )
 
 
def datos_partido(match_info, contestant_id):
    """Extrae jornada, rival, fecha y localía a partir de matchInfo."""
    jornada = match_info.get("week")
    fecha = match_info.get("localDate", match_info.get("date"))
 
    equipos = match_info.get("contestant", [])
    equipo_pumas = next((c for c in equipos if c.get("id") == contestant_id), None)
    rival = next((c for c in equipos if c.get("id") != contestant_id), None)
 
    localia = equipo_pumas.get("position") if equipo_pumas else None  # "home"/"away"
    localia = "Local" if localia == "home" else "Visitante" if localia == "away" else None
 
    return {
        "jornada": jornada,
        "fecha": fecha,
        "rival": rival.get("name") if rival else None,
        "localia": localia,
    }
 
 
def procesar_partido(ruta_json, contestant_id):
    with open(ruta_json, "r", encoding="utf-8") as f:
        data = json.load(f)
 
    match_info = data.get("matchInfo", {})
 
    # Validación: descarta el archivo si Pumas no participa en este partido
    # (evita procesar JSON de otras categorías/equipos que se hayan mezclado
    # en la misma carpeta).
    ids_equipos = {c.get("id") for c in match_info.get("contestant", [])}
    if contestant_id not in ids_equipos:
        return []
 
    info = datos_partido(match_info, contestant_id)
 
    # Estructura confirmada del feed MA3: liveData.event
    eventos = data.get("liveData", {}).get("event", []) or data.get("events", [])
 
    todos_los_goles = [e for e in eventos if e.get("typeId") == GOAL_TYPE_ID]
 
    resultados = []
    for gol in todos_los_goles:
        es_autogol = obtener_qualifier(gol, QUALIFIER_AUTOGOL) is not None
 
        if es_autogol:
            # OJO: en un autogol, contestantId es el equipo DE LA JUGADORA que
            # metió el balón en su propia portería, NO el equipo beneficiado.
            # El gol se le acredita al equipo contrario a contestantId.
            equipo_que_comete = gol.get("contestantId")
            beneficia_a_pumas = equipo_que_comete != contestant_id
 
            if not beneficia_a_pumas:
                continue  # autogol en contra de Pumas: no nos interesa reportarlo
 
            tipo = "Autogol a favor"
            goleador = f"{nombre_jugador(gol)} (rival)"
            asistente = "N/A (autogol)"  # Opta nunca asigna asistencia en autogoles
 
        elif gol.get("contestantId") == contestant_id:
            tipo = "Gol"
            goleador = nombre_jugador(gol)
            assist_event_id = obtener_qualifier(gol, QUALIFIER_ASISTENCIA)
            asistente = None
            if assist_event_id and assist_event_id is not True:
                # OJO: "eventId" NO es único en todo el partido (puede repetirse
                # entre eventos de distinto tipo). Filtramos a typeId==1 (Pase)
                # para encontrar el pase correcto que originó la asistencia.
                candidatos = [
                    e for e in eventos
                    if str(e.get("eventId")) == str(assist_event_id)
                    and e.get("typeId") == PASS_TYPE_ID
                ]
                if candidatos:
                    asistente = nombre_jugador(candidatos[0])
            asistente = asistente or "Sin asistencia"
 
        else:
            continue  # gol normal del rival, no aplica
 
        resultados.append({
            "jornada": info["jornada"],
            "fecha": info["fecha"],
            "rival": info["rival"],
            "localia": info["localia"],
            "minuto": gol.get("timeMin", gol.get("minute")),
            "tipo": tipo,
            "goleador": goleador,
            "asistente": asistente,
        })
 
    return resultados
 
 
def main():
    todos = []
    for ruta in glob.glob(f"{CARPETA_JSON}/*.json"):
        todos.extend(procesar_partido(ruta, PUMAS_FEMENIL_CONTESTANT_ID))
 
    # Ordena por jornada (numérica cuando se pueda) y luego por minuto
    def clave_orden(g):
        try:
            jornada_num = int(g["jornada"])
        except (TypeError, ValueError):
            jornada_num = 999
        return (jornada_num, g.get("minuto") or 0)
 
    todos.sort(key=clave_orden)
 
    # Salida en consola
    for g in todos:
        print(
            f"J{g['jornada']} - vs {g['rival']} ({g['localia']}) {g['fecha']} | "
            f"Min {g['minuto']}' - [{g['tipo']}] {g['goleador']} | Asistencia: {g['asistente']}"
        )
 
    # Salida a CSV
    if todos:
        campos = ["jornada", "fecha", "rival", "localia", "minuto", "tipo", "goleador", "asistente"]
        with open("goles_asistencias_pumas_femenil.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(todos)
        print(f"\n{len(todos)} goles procesados -> goles_asistencias_pumas_femenil.csv")
    else:
        print("No se encontraron goles de Pumas en los JSON revisados.")
 
 
if __name__ == "__main__":
    main()
 
 