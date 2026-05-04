#!/usr/bin/env bash
# Download public raw inputs into data/raw/ (gitignored).
# Run from the repository root: bash scripts/download_raw_data.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

mkdir -p data/raw/miteco data/raw/esyrce data/raw/csic_drought

echo "==> MITECO BD-Embalses.zip (contains BD-Embalses.mdb)"
curl -fsSL -o data/raw/miteco/BD-Embalses.zip \
  "https://www.miteco.gob.es/content/dam/miteco/es/agua/temas/evaluacion-de-los-recursos-hidricos/boletin-hidrologico/Historico-de-embalses/BD-Embalses.zip"
unzip -o data/raw/miteco/BD-Embalses.zip -d data/raw/miteco/
# ingest_miteco.py reads BD-Embalses.mdb via mdb-export if mdbtools is installed
rm -f data/raw/miteco/BD-Embalses.zip

echo "==> ESYRCE Andalucía 2025 (Excel)"
curl -fsSL -A "Mozilla/5.0" -o data/raw/esyrce/andalucia_2025.xlsx \
  "https://www.mapa.gob.es/es/dam/jcr:5b7722a7-246a-4451-b99d-5083a8cdc117/Resultados%20provisionales%202025%20Andaluc%C3%ADa.xlsx"

echo "==> CSIC Spanish Drought Catalogue — Drought_episodes.zip"
curl -fsSL -o data/raw/csic_drought/Spanish_Drought_Catalogue_v1.0.0-Drought_episodes.zip \
  "https://digital.csic.es/bitstream/10261/331384/6/Spanish_Drought_Catalogue_v1.0.0-Drought_episodes.zip"
unzip -jo data/raw/csic_drought/Spanish_Drought_Catalogue_v1.0.0-Drought_episodes.zip \
  "Identification_and_characteristics.xlsx" -d data/raw/csic_drought/
rm -f data/raw/csic_drought/Spanish_Drought_Catalogue_v1.0.0-Drought_episodes.zip

echo "Done. Next:"
echo "  brew install mdbtools   # if you do not have mdb-export yet"
echo "  python forecasting/ingest_miteco.py"
echo "  python demand/ingest_esyrce.py"
echo "  python forecasting/ingest_drought_catalogue.py"
