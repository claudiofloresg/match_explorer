# Explorador de Partido — Pumas UNAM Inteligencia Deportiva

## Estructura de carpetas

```
pumas_explorer/
├── build_data.py        <- convierte los JSON de Opta en los 3 JSON que usa la app
├── build_html.py        <- combina la plantilla + los datos + el logo en el archivo final
├── template.html         <- la app en sí (HTML/CSS/JS), sin datos
├── README.md              <- este archivo
├── data/
│   ├── raw/                <- aquí van los JSON que te da el SDAPI (Match Stats y Match Events)
│   └── build/               <- aquí caen los 3 JSON procesados (se generan solos)
├── assets/
│   └── logo.png             <- tu escudo. Cámbialo por otro si quieres otro logo.
└── output/
    └── Explorador_Partido_Pumas.html   <- el archivo final, lista para abrir/compartir
```

## Cómo generar el archivo (primera vez o después de cualquier cambio)

```bash
cd pumas_explorer
python3 build_data.py   # lee data/raw/, escribe data/build/
python3 build_html.py    # combina todo, escribe output/Explorador_Partido_Pumas.html
```

Abre `output/Explorador_Partido_Pumas.html` en cualquier navegador. Es un solo archivo,
no necesita servidor ni internet (salvo para cargar la tipografía de Google Fonts —
si no hay internet, cae automáticamente a Helvetica/Arial del sistema).

## Cómo agregar un partido nuevo (de cualquier equipo)

1. Copia los dos JSON del partido a `data/raw/`:
   - El de **Match Stats** (MA2 detallado)
   - El de **Match Events** (MA3)

2. Abre `build_data.py` y agrega una línea a la lista `MATCHES`, arriba del archivo:

   ```python
   MatchConfig(id="J4", label="J4 · Pumas UNAM vs León",
               stats_file="data/raw/Match_Stats_J4_vs_Leon.json",
               events_file="data/raw/Match_Events_J4_vs_Leon.json"),
   ```

   - `id`: identificador corto y único (J4, J5... o el que quieras)
   - `label`: lo que se ve en el selector "Partido" dentro de la app
   - `stats_file` / `events_file`: las rutas a los dos JSON que copiaste

3. Corre de nuevo `python3 build_data.py` y `python3 build_html.py`.

**No hace falta indicar los IDs de los equipos ni sus nombres a mano** — el script los
lee directamente del propio JSON (`matchInfo.contestant`). Esto significa que puedes
cargar partidos de **cualquier equipo**, no solo de Pumas — por ejemplo, un partido de
scouting entre dos rivales. La app detecta automáticamente los dos equipos que jugaron
ese partido y los pone en el selector "Equipo".

Lo único que sí puedes ajustar es `TRACKED_TEAM_NAME` (en `build_data.py` y en
`template.html`, dentro del bloque `<script>`) — es el nombre del equipo que se
selecciona por default al abrir un partido, si está presente en ese partido. Por
default está en `"Pumas UNAM"`. Si cargas un partido donde Pumas no participa, la app
simplemente selecciona el equipo local.

## Cómo cambiar la tipografía

Toda la tipografía se controla desde dos variables CSS, al principio de `template.html`
(dentro de `<style>`, en el bloque `:root`):

```css
--fnt: 'Helvetica Neue', Helvetica, Arial, 'Inter', sans-serif;
--fnt-mono: 'JetBrains Mono', 'Consolas', monospace;
```

- `--fnt` es la tipografía principal (títulos, botones, texto). Actualmente usa
  Helvetica, que es la tipografía oficial que marca el manual de identidad gráfica
  de la UNAM para documentos. Si quieres cambiarla, solo edita esta línea — por
  ejemplo, para usar una tipografía de Google Fonts:

  1. Agrega el `<link>` de esa fuente en el `<head>` (junto al que ya existe para
     Inter/JetBrains Mono).
  2. Cambia `--fnt` para que empiece con el nombre de esa fuente.

- `--fnt-mono` es la que se usa para números y datos (marcador, minutos, estadísticas).
  Es una fuente monoespaciada a propósito, para que las cifras se alineen bien en
  columnas — normalmente no hace falta tocarla, pero funciona igual si la cambias.

Después de editar `template.html`, vuelve a correr `python3 build_html.py` para que el
cambio se refleje en el archivo final.

## Cómo cambiar el logo

Reemplaza `assets/logo.png` por tu propio archivo (PNG con fondo transparente,
idealmente no más de ~300px de ancho para que el archivo final no pese de más) y
vuelve a correr `python3 build_html.py`.

## Descargar partidos directo de la API (sin subir archivos a mano)

Si ya tienes tus credenciales de Stats Perform, `fetch_from_api.py` revisa qué
partidos hay disponibles en Liga MX, Liga MX Femenil, U21, U19 y U17, y baja
a `data/raw/` los que todavía no tengas — automáticamente.

**Primera vez:**
```bash
pip install requests python-dotenv --break-system-packages
cp .env.example .env
# abre .env y llena tus 3 credenciales (las mismas que usas en Postman)
```

**Cada vez que quieras actualizar:**
```bash
python3 fetch_from_api.py
python3 build_data.py
python3 build_html.py
```

Para probar con pocos partidos primero (recomendado la primera vez):
```bash
python3 fetch_from_api.py --limit 3
```

Para bajar solo una competencia:
```bash
python3 fetch_from_api.py --tmcl 9zum4nxferygj8bb0ldcavxn8
```

El archivo `.env` con tus credenciales nunca se sube a GitHub — ya está en
`.gitignore`.

## Qué contiene cada JSON generado (por si quieres inspeccionarlos)

- **`events_data.json`**: pases, disparos y acciones defensivas de cada jugador con
  su ubicación en la cancha, por partido y por equipo. Alimenta la Red de pases,
  Campograma, Disparos, Duelos y recuperaciones, y las vistas de jugador.
- **`player_full_stats.json`**: estadísticas curadas por jugador por partido (minutos,
  pases, disparos, duelos, etc.), usado en la Ficha completa.
- **`team_summary.json`**: ~55 estadísticas de equipo por categoría, comparando a los
  dos equipos del partido, usado en la hoja de Resumen.

## Límite conocido

Los datos son **por evento** (dónde tocó el balón cada jugador), no tracking óptico —
no hay movimiento continuo de un jugador sin balón entre esos eventos. Es lo máximo
que da el endpoint MA3 de Opta.
