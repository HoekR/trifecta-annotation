#!/usr/bin/env zsh
# Timed progress report for scripts/delpher_download.sh (Rik, 18 Nov 2026: no messageless background scripts).
# Every <minutes> (default 60): files verified, GB on disk, MB/s, a macOS notification. Final notification
# when the download process is gone, saying whether all files were verified.
#
# Usage: scripts/download_progress.sh <destination dir> [minutes]
set -uo pipefail
[[ $# -ge 1 ]] || { echo "usage: $0 <destination dir> [minutes]" >&2; exit 2; }
DEST="$1"; EVERY="${2:-60}"; LOG="$DEST/delpher_download.log"
TOTAL=$(grep -c '\.zip:' "${0:A:h}/delpher_download.sh")
PAT="delpher_download[.]sh"   # [.] so this script's own command line does not match

say() {
  echo "$(date '+%H:%M') $1"
  osascript -e "display notification \"$1\" with title \"Newspaper download\"" >/dev/null 2>&1
}
bytes() { du -sk "$DEST" | awk '{print $1 * 1024}'; }
ok() { grep -cE '  (OK|SKIP) ' "$LOG" 2>/dev/null || echo 0; }

b0=$(bytes); t0=$(date +%s)
say "reporter on: $(ok) of $TOTAL files verified, $(( b0 / 1000000000 )) GB on disk"
while pgrep -f "$PAT" >/dev/null; do
  /bin/sleep $(( EVERY * 60 ))
  pgrep -f "$PAT" >/dev/null || break
  b=$(bytes); t=$(date +%s)
  rate=$(( (b - b0) / (t - t0) / 1000000 ))
  cur=$(grep 'Fetching' "$LOG" | tail -1 | sed -E 's/.*Fetching ([^ ]+).*/\1/')
  say "$(ok) of $TOTAL files verified, $(( b / 1000000000 )) GB, ${rate} MB/s, now $cur"
done
if grep -q 'All files present and verified' "$LOG"; then
  say "done: all $TOTAL files verified, $(( $(bytes) / 1000000000 )) GB"
else
  say "download stopped: $(ok) of $TOTAL files verified — NOT complete, check $LOG"
fi
