#!/bin/bash
set -e

CAM_SSID="${OLYMPUS_CAM_SSID:-E-M10MKII-P-BHLA20624}"
CAM_PASS="${OLYMPUS_CAM_PASS:-}"
HOME_SSID="${OLYMPUS_HOME_SSID:-}"

usage() {
  echo "Usage: $0 [--camera|--home|--status|--auto]"
  echo "  --camera   Switch WiFi to camera (sets higher priority too)"
  echo "  --home     Switch WiFi back to home network"
  echo "  --status   Show current WiFi connection"
  echo "  --auto     Set camera WiFi higher priority for auto-switch"
  echo ""
  echo "Env vars: OLYMPUS_CAM_SSID, OLYMPUS_CAM_PASS, OLYMPUS_HOME_SSID"
  exit 1
}

ensure_conn() {
  local ssid="$1" pass="$2"
  if ! nmcli -t -f NAME con show | grep -qxF "$ssid"; then
    [ -n "$pass" ] || { echo "Password required for $ssid"; exit 1; }
    sudo nmcli device wifi connect "$ssid" password "$pass"
  fi
}

case "${1:-}" in
  --camera)
    ensure_conn "$CAM_SSID" "$CAM_PASS"
    ensure_conn "$HOME_SSID"
    sudo nmcli con modify "$CAM_SSID" connection.autoconnect yes connection.autoconnect-priority 100
    sudo nmcli con modify "$HOME_SSID" connection.autoconnect yes connection.autoconnect-priority 50
    sudo nmcli con up "$CAM_SSID"
    ;;
  --home)
    ensure_conn "$HOME_SSID"
    sudo nmcli con up "$HOME_SSID"
    ;;
  --status)
    nmcli -t -f ACTIVE,SSID,DEVICE device wifi | grep '^yes'
    ;;
  --auto)
    ensure_conn "$CAM_SSID" "$CAM_PASS"
    ensure_conn "$HOME_SSID"
    sudo nmcli con modify "$CAM_SSID" connection.autoconnect yes connection.autoconnect-priority 100
    sudo nmcli con modify "$HOME_SSID" connection.autoconnect yes connection.autoconnect-priority 50
    echo "Camera WiFi has priority. Runs 'sudo nmcli con up \"$CAM_SSID\"'."
    ;;
  *)
    usage
    ;;
esac
