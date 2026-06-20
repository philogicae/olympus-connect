#!/bin/bash
set -e

CAM_SSID="${OLYMPUS_CAM_SSID:-E-M10MKII-P-BHLA20624}"
CAM_PASS="${OLYMPUS_CAM_PASS:-}"
HOME_SSID="${OLYMPUS_HOME_SSID:-}"

usage() {
  echo "Usage: $0 [--camera|--home|--status|--auto]"
  echo "  --camera   Switch WiFi to camera"
  echo "  --home     Switch WiFi back to home network"
  echo "  --status   Show current WiFi connection"
  echo "  --auto     Set camera WiFi higher priority (auto-switch)"
  echo ""
  echo "Env vars: OLYMPUS_CAM_SSID, OLYMPUS_CAM_PASS, OLYMPUS_HOME_SSID"
  exit 1
}

case "${1:-}" in
  --camera)
    [ -n "$CAM_PASS" ] || { echo "Set OLYMPUS_CAM_PASS"; exit 1; }
    sudo nmcli device wifi connect "$CAM_SSID" password "$CAM_PASS"
    ;;
  --home)
    [ -n "$HOME_SSID" ] || { echo "Set OLYMPUS_HOME_SSID"; exit 1; }
    sudo nmcli device wifi connect "$HOME_SSID"
    ;;
  --status)
    nmcli -t -f ACTIVE,SSID,DEVICE device wifi | grep '^yes'
    ;;
  --auto)
    [ -n "$CAM_PASS" ] || { echo "Set OLYMPUS_CAM_PASS"; exit 1; }
    [ -n "$HOME_SSID" ] || { echo "Set OLYMPUS_HOME_SSID"; exit 1; }
    sudo nmcli con modify "$CAM_SSID" connection.autoconnect-priority 100 2>/dev/null || \
      sudo nmcli device wifi connect "$CAM_SSID" password "$CAM_PASS"
    sudo nmcli con modify "$HOME_SSID" connection.autoconnect-priority 50
    echo "Camera WiFi has priority. RPi will auto-switch when camera is on."
    ;;
  *)
    usage
    ;;
esac
