#!/usr/bin/env zsh
# Download the Delpher open newspaper archive (KB, public domain, 1618-1879).
# Source: https://www.delpher.nl/over-delpher/delpher-open-krantenarchief/download-teksten-kranten-1618-1879/
# Recovered 18 Nov 2026 from the editor history of the script on the old WD disk (ExterneSchijf), which no
# longer reads reliably; md5s are the ones recovered then from the Delpher archive page.
#
# Usage: scripts/delpher_download.sh <destination dir>
# Resumable: verified files are skipped, partial files continue (curl -C -). Log: <dest>/delpher_download.log
set -uo pipefail

[[ $# -eq 1 ]] || { echo "usage: $0 <destination dir>" >&2; exit 2; }
DEST_DIR="$1"
LOG="$DEST_DIR/delpher_download.log"
MAX_ATTEMPTS=3
mkdir -p "$DEST_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

# filename:md5. Index and the smallest decade first, so a first look can start early; "-" = no published hash.
ENTRIES=(
  index_delpher_kranten_pd_v1-0_2020.zip:-
  kranten_pd_171x.zip:d748f42a9b80145a5541ff30a74a836d
  kranten_pd_16xx.zip:8a85d73a0ea97665614821ddb155a5e5
  kranten_pd_170x.zip:693ae105593c978278978f1679232bb1
  kranten_pd_172x.zip:9d0d9396b30e3ff07d9dd4af15530572
  kranten_pd_173x.zip:b5956fb0e83210cbcd8915931f941d4d
  kranten_pd_174x.zip:847d3fb859bcaa879808412a34d5dd0f
  kranten_pd_175x.zip:6f31341c943adc4eef6adcf4c0cbb633
  kranten_pd_176x.zip:278e5087353a448031ae2986815cbb42
  kranten_pd_177x.zip:6e413491230d14f2f52bb37f41cb642a
  kranten_pd_178x.zip:12e5f4ff7846e836a95d9b65caf1977a
  kranten_pd_179x.zip:a3c9657819a0a41045317d5375ff4093
  kranten_pd_180x.zip:af4fbab598dd794e8f2dbec4cced562d
  kranten_pd_181x.zip:f4d5ce16d18264b975fba4f07f4c8cd0
  kranten_pd_182x.zip:3ade528b5db82f4f3fdc763cc9b65b35
  kranten_pd_183x.zip:ef66eebbf47f0d9f1b9a12c01d8bdc0f
  kranten_pd_184x.zip:e48ee0d5a1d366f27886edc241be8ad2
  kranten_pd_1850-4.zip:1e8c727cbc79bd906372fda59368944d
  kranten_pd_1855-9.zip:9516510c0fe603c9024d58220f95d246
  kranten_pd_1860-4.zip:ef6044b92d37e8a91cb8c7c7327e30ef
  kranten_pd_1865-9.zip:833797483ba4b28dd752055a1f40e6d9
  kranten_pd_1870-4.zip:8055b117af66cb689c56aa0135551fd5
  kranten_pd_1875-6.zip:ac31e12871250f1ea7ac0343dba66c3e
  kranten_pd_1877-9.zip:afc421665b7254b87e88b7c7b07de308
)

url_for() { echo "https://resolver.kb.nl/resolve?urn=DATA:kranten:$1"; }

verify_md5() {
  local file="$1" expected="$2"
  [[ "$expected" == "-" ]] && return 0
  [[ "$(md5 -q "$file" 2>/dev/null)" == "$expected" ]]
}

log "=== Delpher newspaper archive download -> $DEST_DIR ==="
for entry in "${ENTRIES[@]}"; do
  fname="${entry%%:*}"; expected="${entry##*:}"; target="$DEST_DIR/$fname"
  if [[ -f "$target" ]] && verify_md5 "$target" "$expected"; then
    log "  SKIP $fname (present, verified)"; continue
  fi
  log "Fetching $fname ..."
  ok=0
  for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    if curl -L --fail -sS -C - -o "$target" "$(url_for "$fname")" >> "$LOG" 2>&1; then
      if verify_md5 "$target" "$expected"; then
        log "  OK  $fname ($(du -h "$target" | cut -f1))"; ok=1; break
      fi
      log "  MISMATCH md5 for $fname (attempt $attempt), refetching"; rm -f "$target"
    else
      log "  attempt $attempt failed for $fname"
    fi
  done
  [[ "$ok" -eq 1 ]] || { log "  FAILED $fname after $MAX_ATTEMPTS attempts — stopping"; exit 1; }
done
log "=== All files present and verified ==="
