#!/bin/bash
# actualizar.sh
# ---------------
# Un solo comando para procesar todo lo que hay en data/raw/ y generar el
# archivo final actualizado. Úsalo cada vez que agregues partidos nuevos o
# cambies algo en template.html.
#
# Uso:  ./actualizar.sh
set -e
cd "$(dirname "$0")"
echo "== Procesando partidos en data/raw/ =="
python3 build_data.py
echo ""
echo "== Generando el archivo final =="
python3 build_html.py
echo ""
echo "Listo. Abre output/index.html"
