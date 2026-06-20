# olympus-connect

Control Olympus wifi cameras (TG-5, TG-6, etc.) over the camera's wifi network. Set the clock, download photos, stream live view, take pictures, change settings, turn it off.

```
uv tool install git+https://github.com/philogicae/olympus-connect
olympus-camera --set-clock
olympus-download
olympus-liveview
```

## Commands

| Command | Action |
|---|---|
| `olympus-camera --shoot` | Take a picture |
| `olympus-camera --set-clock` | Sync camera clock to PC time |
| `olympus-camera --liveview` | GUI live view window |
| `olympus-camera --download` | Download all photos |
| `olympus-camera --download --date-range 7 0` | Last 7 days only |
| `olympus-camera --download --extension .orf` | Raw files only |
| `olympus-camera --power-off` | Turn camera off |
| `olympus-camera --cmd "get_camprop com=get propname=whitebalance"` | Arbitrary command |
| `olympus-download` | Standalone download (same flags as above) |
| `olympus-liveview [--port 40001]` | Standalone live view |
| `olympus-log2gpx track.log` | Convert GPS `.LOG` to `.gpx` |

The GUI live view (tkinter) provides **File** (take picture, set clock, exit), **View** (resolution), and **Settings** (ISO, white balance, aperture, etc.) menus.

## Install from source

```bash
git clone https://github.com/philogicae/olympus-connect.git
cd olympus-connect
uv sync
uv run olympus-camera --help
```

Requires Python ≥ 3.14 and tkinter (`python3-tk` on Debian/Ubuntu).

## Lint

```bash
scripts/lint.sh
```

Runs `uv lock`, `uv sync`, ruff formatting/linting, and shellcheck.

## How it works

The camera exposes an HTTP API at `http://192.168.0.10/` (OPC Communication Protocol 1.0a). This library connects to the camera's wifi, fetches the command list via `get_commandlist.cgi`, and sends commands via HTTP GET/POST. Live view is received as RTP/MJPEG over UDP. Photos download via plain HTTP.

## License

MIT
