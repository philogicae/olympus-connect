# olympus-connect

Relay an Olympus wifi camera's live stream through a Raspberry Pi to any server over Bluetooth.

```
Camera ──WiFi──→ RPi (--serve) ──Bluetooth PAN──→ Your server
```

The camera streams RTP/UDP → RPi decodes to MJPEG → serves via HTTP → Bluetooth device pulls `GET /stream`. No display, no cloud, no proprietary SDK.

```bash
uv tool install git+https://github.com/philogicae/olympus-connect
olympus-camera --serve    # connect camera wifi, then run
```

## Commands

| `olympus-camera` | |
|---|---|
| `--shoot` / `-S` | Take a picture |
| `--set-clock` / `-c` | Sync camera clock |
| `--live` / `-L` | GUI live view (tkinter) |
| `--serve [port]` / `-s` | **Headless MJPEG relay** (default port 8080) |
| `--download` / `-d` | Download photos |
| `--download --date-range 7 0` | Last 7 days |
| `--download --extension .orf` | Raw files only |
| `--power-off` / `-p` | Turn camera off |
| `--cmd "get_camprop com=get propname=whitebalance"` | Arbitrary command |
| `--output` / `-o` | Download directory |
| `--port` / `-P` | UDP port for live view |

| `olympus-log2gpx` | |
|---|---|
| `olympus-log2gpx track.log` | Convert GPS `.LOG` to `.gpx` |

With no flag, prints help.

## `--serve` (the relay)

The core feature. Starts live view, receives RTP, serves MJPEG:

| Endpoint | What you get |
|---|---|
| `http://rpi:8080/` | HTML with embedded `<img src="/stream">` |
| `http://rpi:8080/stream` | Raw MJPEG (`multipart/x-mixed-replace`) |

```
olympus-camera --serve           # port from config or 8080
olympus-camera --serve 9090      # explicit port
olympus-camera -s 9090 -P 40001  # custom UDP + HTTP port
```

### Bluetooth relay

One-time RPi setup:

```bash
sudo apt install bluez bluez-tools
sudo bt-pan server --role NAP &
sudo ip addr add 172.16.0.1/24 dev bnep0
```

On the external server (connected via Bluetooth): `curl http://172.16.0.1:8080/stream`

Requires `"bind": "0.0.0.0"` in config (default). Bluetooth caps at ~1–3 Mbps — 640×480 works well.

## GUI (`--live`)

tkinter window with **File** (take picture, set clock, exit), **View** (resolution), **Settings** (ISO, white balance, aperture — auto-detected).

## Configuration

`config.json` in project root or `~/.config/olympus-connect/config.json`:

```json
{
  "camera": { "host": "192.168.0.10", "user_agent": "OI.Share v2",
              "live_port": 40000, "live_resolution": "0640x0480" },
  "server": { "http_port": 8080, "bind": "0.0.0.0" },
  "download": { "output": "./camera-output" }
}
```

| Key | What it controls |
|---|---|
| `camera.host` | Camera IP (default: `192.168.0.10`) |
| `camera.live_port` | UDP port for RTP stream |
| `camera.live_resolution` | Camera resolution |
| `server.http_port` | Default `--serve` port |
| `server.bind` | Interface to bind (`0.0.0.0` = all including Bluetooth PAN) |
| `download.output` | Download directory |

CLI overrides config. Config overrides defaults.

## Install

```bash
git clone https://github.com/philogicae/olympus-connect.git
cd olympus-connect
uv sync
uv run olympus-camera --help
```

Requires Python ≥ 3.14. tkinter needed for `--live` (`python3-tk` on Debian/Ubuntu). No external HTTP lib — uses stdlib `urllib`.

## Development

`scripts/dev.sh` — lock, sync, ruff lint/format, shellcheck, reinstall.

## How it works

Camera exposes `http://192.168.0.10/` (OPC Protocol 1.0a). The library fetches `get_commandlist.cgi`, sends HTTP GET/POST commands, receives live view as RTP/MJPEG over UDP, and serves frames as MJPEG over HTTP. Downloads are plain HTTP (camera is a file server). All HTTP via stdlib `urllib`.

## License

MIT
