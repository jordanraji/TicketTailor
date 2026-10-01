#!/usr/bin/env bash
# Regenerate the report figure PDFs from the authoritative d2 diagram sources
# (model/artefacts/). Run after editing a diagram, then rebuild the report.
# Requires d2 (https://d2lang.com).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${REPO}/report/figures"
mkdir -p "${OUT}"

render() {
  d2 --layout=elk "${REPO}/$1" "${OUT}/$2"
  echo "  rendered $2"
}

render model/artefacts/c4/tickettailor_c4_l1.d2                    c4_l1.pdf
render model/artefacts/c4/tickettailor_c4_l2.d2                    c4_l2.pdf
render model/artefacts/c4/tickettailor_c4_l3.d2                    c4_l3.pdf
render model/artefacts/sequence/tickettailor_seq_1_outbox_overview.d2 seq_outbox.pdf

echo "Done. Figures written to report/figures/."
