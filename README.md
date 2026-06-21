# olympus-connect

Relay an Olympus WiFi camera live view through a Raspberry Pi over Bluetooth.

```
Camera ──WiFi──→ RPi (--serve) ──Bluetooth PAN──→ Client
```

Camera RTP/UDP → RPi pipelines raw frames → parallel JPEG re-compression → MJPEG over HTTP + JSON API.

```bash
olympus-camera --serve
```

## Commands

| Flag | Action |
|------|--------|
| `--serve` / `-s` | Headless MJPEG relay + JSON API (default port 8080) |
| `--shoot` / `-S` | Take a picture |
| `--live` / `-L` | GUI live view (tkinter) |
| `--download` / `-d` | Download photos |
| `-d --date-range 7 0` | Last 7 days |
| `-d --extension .orf` | Raw files only |
| `--set-clock` / `-c` | Sync camera clock |
| `--power-off` / `-p` | Turn camera off |
| `--cmd "get_camprop com=get propname=whitebalance"` | Arbitrary command |
| `--output` / `-o` | Download directory |
| `--port` / `-P` | UDP port for live view |
| `--quality` / `-Q` | JPEG compression quality 1–100 (default 85) |
| `--scale` / `-R` | Downscale factor e.g. `0.5` for half resolution (default 1.0) |
| `--fps` / `-F` | Max frames per second to stream (default 15 for `--serve`) |

| Binary | Action |
|--------|--------|
| `olympus-log2gpx track.log` | Convert GPS `.LOG` to `.gpx` |

## `--serve` endpoints

```
olympus-camera --serve              # port from config or 8080
olympus-camera --serve 9090         # explicit port
olympus-camera -s 9090 -P 40001     # custom UDP + HTTP port
olympus-camera -s -Q 50             # lower JPEG quality for slower links
olympus-camera -s -Q 75 -R 0.5     # half resolution at good quality
olympus-camera -s -F 10            # cap at 10 fps for Bluetooth PAN
olympus-camera -s -F 5 -Q 50 -R 0.5  # 5 fps at half-res for very slow links
olympus-camera -s -Q 95               # bypass JPEG re-compression entirely (zero-copy passthrough)
```

| Endpoint | Returns |
|----------|---------|
| `GET /` | HTML with embedded stream |
| `GET /stream` | MJPEG (`multipart/x-mixed-replace`) |
| `GET /api` | Endpoint list |
| `GET /api/info` | Hostname, client IP, uptime |
| `GET /api/bluetooth` | PAN interface, IP, client address |

### Bluetooth relay

```
sudo apt install bluez bluez-tools
sudo bt-pan server --role NAP &
sudo ip addr add 192.168.44.1/24 dev bnep0
olympus-camera --serve
```

Client over BT PAN: `curl http://192.168.44.1:8080/api/info`

BT caps at ~1–3 Mbps — 640×480 works well. Requires `"bind": "0.0.0.0"` in config (default).

## GUI (`--live`)

tkinter window with **File** (take picture, set clock, exit), **View** (resolution), **Settings** (ISO, WB, aperture — auto-detected from camera).

## Configuration

`config.json` in project root or `~/.config/olympus-connect/config.json`:

```json
{
  "camera": { "host": "192.168.0.10", "user_agent": "OI.Share v2",
              "live_port": 40000, "live_resolution": "0640x0480" },
  "server": { "http_port": 8080, "bind": "0.0.0.0",
              "jpeg_quality": 75, "jpeg_scale": 1.0, "jpeg_optimize": false,
              "max_fps": 15 },
  "bluetooth": { "interface": "bt0", "pan_ip": "192.168.44.1" },
  "download": { "output": "./camera-output" }
}
```

| Key | Controls |
|-----|----------|
| `camera.host` | Camera IP |
| `camera.live_port` | UDP port for RTP stream |
| `camera.live_resolution` | Camera resolution |
| `server.http_port` | Default `--serve` port |
| `server.bind` | Interface to bind (`0.0.0.0` = all including BT PAN) |
| `server.jpeg_quality` | JPEG re-compression quality 1–100 (default 85) |
| `server.jpeg_scale` | Downscale factor (default 1.0) |
| `server.jpeg_optimize` | JPEG Huffman optimization (smaller files, slower encode; disable for streaming) |
| `server.max_fps` | Max frames per second to stream (default 15) |
| `bluetooth.interface` | BT PAN network interface |
| `bluetooth.pan_ip` | BT PAN IP for `/api/bluetooth` |
| `download.output` | Download directory |

CLI overrides config. Config overrides defaults.

## Install

```bash
git clone https://github.com/philogicae/olympus-connect.git
cd olympus-connect
uv sync
uv run olympus-camera --help
```

Requires Python ≥ 3.14. tkinter needed for `--live` (`python3-tk` on Debian/Ubuntu). No external HTTP lib — stdlib `urllib` only.

## How it works

Camera exposes `http://192.168.0.10/` (OPC Protocol 1.0a). Fetches `get_commandlist.cgi` to discover capabilities, sends GET/POST for commands, receives live view as RTP/MJPEG over UDP. The `--serve` path pipelines raw frame reception into separate threads for JPEG re-compression (quality/scale) so UDP packet reception never blocks on CPU work. With `--quality 95` (or higher), JPEG re-compression is bypassed entirely — the receiver writes frames directly to a shared `threading.Condition` slot (zero-copy passthrough, no PIL, no queue). Frames are assembled with `bytearray` (O(1) per packet vs O(n) with `bytes +=`). The HTTP handler sets `TCP_NODELAY` to disable Nagle's algorithm, rate-limits output to `--fps`, and flushes after each frame. The `--live` GUI path re-compresses inline in the receiver thread. Downloads are plain HTTP (camera is a file server).

## Development

```
bash scripts/dev.sh
```

Lock, sync, ruff check + format, typecheck, shellcheck, reinstall.

## License

MIT
