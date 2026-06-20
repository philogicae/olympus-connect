#!/bin/bash
set -euo pipefail

get_ssid() {
  nmcli -g 802-11-wireless.ssid con show "$1" 2>/dev/null || true
}

detect_camera() {
  nmcli -t -f NAME,TYPE con show \
    | awk -F: '$2 == "802-11-wireless" {print $1}' \
    | while IFS= read -r name; do
        ssid=$(get_ssid "$name")
        if [[ "$ssid" == E-* ]]; then
          echo "$name"
          exit 0
        fi
      done
}

detect_home() {
  local cam
  cam=$(detect_camera)
  nmcli -t -f NAME,TYPE,TIMESTAMP con show \
    | awk -F: -v cam="$cam" '
        $2 == "802-11-wireless" && $1 != cam && $3 ~ /^[0-9]+$/ {print $1"|"$3}
      ' \
    | sort -t'|' -k2 -rn \
    | while IFS='|' read -r name _; do
        echo "$name"
        exit 0
      done
}

list_networks() {
  local cam_ssid
  cam_ssid=$(get_ssid "$(detect_camera)" 2>/dev/null || true)
  printf "%-30s %-10s %s\n" "SSID" "PRIORITY" "STATUS"
  printf -- "----------------------------------------\n"
  nmcli -t -f NAME,TYPE,TIMESTAMP,AUTOCONNECT-PRIORITY con show \
    | grep ':802-11-wireless:' \
    | while IFS=: read -r name _ ts prio; do
        ssid=$(get_ssid "$name" 2>/dev/null || echo "$name")
        status=""
        nmcli -t -f ACTIVE,SSID device wifi | grep -qi "^yes:$ssid$" && status="*active"
        printf "%-30s %-10s %s\n" "$ssid" "${prio:-0}" "$status"
      done
}

usage() {
  echo "Usage: $0 [--camera|--home|--status|--list]"
  echo "  --camera   Switch to the Olympus camera WiFi"
  echo "  --home     Switch back to home WiFi"
  echo "  --status   Show current WiFi connection"
  echo "  --list     Show saved WiFi networks"
  exit 1
}

case "${1:-}" in
  --camera)
    ssid=$(detect_camera)
    [ -z "$ssid" ] && { echo "No Olympus camera WiFi found"; exit 1; }
    sudo nmcli con modify "$ssid" connection.autoconnect-priority 100
    sudo nmcli con up "$ssid"
    ;;
  --home)
    ssid=$(detect_home)
    [ -z "$ssid" ] && { echo "No home WiFi found"; exit 1; }
    sudo nmcli con modify "$ssid" connection.autoconnect-priority 50
    sudo nmcli con up "$ssid"
    ;;
  --status)
    nmcli -t -f ACTIVE,SSID,DEVICE device wifi | grep '^yes' || echo "No active WiFi"
    ;;
  --list)
    list_networks
    ;;
  *)
    usage
    ;;
esac
