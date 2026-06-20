import argparse
import sys

from .src.camera import OlympusCamera, ResultError
from .download import download_photos, parse_date
from .liveview import LiveViewWindow, serve_stream
from .config import get_config


def user_command(camera: OlympusCamera, cmd: str) -> bool:
    cmd_list = cmd.strip().split()
    if not cmd_list:
        return True
    command = cmd_list[0]
    args = {k: v for k, v in (kv.split("=", 1) for kv in cmd_list[1:] if "=" in kv)}
    try:
        response = camera.send_command(command, **args)
    except (ValueError, ResultError) as e:
        print(e, file=sys.stderr)
        return True
    if "Content-Type" in response.headers and response.headers[
        "Content-Type"
    ].startswith("text"):
        print(response.text)
    elif response.content:
        n = len(response.content)
        content = response.headers.get("Content-Type", "unknown kind")
        print(
            f"Command '{cmd}' returned {n:,} bytes of {content}. Re-run with redirection to obtain data."
        )
    return False


_SERVE_DEFAULT = object()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", help="Local directory for downloaded photos.")
    parser.add_argument(
        "--download", "-d", action="store_true", help="Download photos from camera."
    )
    parser.add_argument("--extension", "-e", help="Limit download to this extension.")
    parser.add_argument(
        "--date-range",
        "-D",
        nargs=2,
        type=parse_date,
        metavar=("START", "END"),
        default=(None, None),
        help="Start and end dates to download photos from. "
        "Must be in YYYY-MM-DD format or integers "
        "(days before today, e.g. -D 1 0 for yesterday "
        "to today). If argument not "
        "given, will download everything.",
    )
    parser.add_argument(
        "--power_off", "-p", action="store_true", help="Turn camera off."
    )
    parser.add_argument(
        "--set_clock",
        "-c",
        action="store_true",
        help="Set camera clock to current time.",
    )
    parser.add_argument("--shoot", "-S", action="store_true", help="Take a picture.")
    parser.add_argument(
        "--live",
        "-L",
        action="store_true",
        help="Show live camera stream. Close "
        "the live view window to quit. This script will run a "
        "few more seconds, then exit.",
    )
    parser.add_argument(
        "--port",
        "-P",
        type=int,
        default=None,
        help="UDP port for live view.",
    )
    parser.add_argument(
        "--serve",
        "-s",
        type=int,
        nargs="?",
        const=None,
        default=_SERVE_DEFAULT,
        metavar="PORT",
        help="Serve MJPEG stream over HTTP (port from config.json or 8080). Headless — no GUI needed.",
    )
    parser.add_argument(
        "--quality",
        "-Q",
        type=int,
        default=None,
        help="JPEG compression quality 1-100 (lower = smaller, faster). Default 85.",
    )
    parser.add_argument(
        "--scale",
        "-R",
        type=float,
        default=None,
        help="Downscale factor (e.g. 0.5 for half resolution). Default 1.0.",
    )
    parser.add_argument(
        "--cmd",
        "-C",
        type=str,
        nargs="+",
        help="Command to send to camera; multiple commands are supported.",
    )

    args = parser.parse_args()
    if all(args.date_range):
        start, end = args.date_range
        if start > end:
            parser.error("Start date must be before end date")

    if not any(
        [
            args.set_clock,
            args.cmd,
            args.shoot,
            args.live,
            args.download,
            args.power_off,
            args.serve is not _SERVE_DEFAULT,
        ]
    ):
        parser.print_help()
        return

    try:
        print(
            f"Connecting to {get_config().get('camera', {}).get('host', '192.168.0.10')}...",
            file=sys.stderr,
        )
        camera = OlympusCamera()
        camera.report_model()

        if args.set_clock:
            print("Setting clock...", file=sys.stderr)
            camera.set_clock()

        if args.cmd:
            for cmd in args.cmd:
                if user_command(camera, cmd):
                    break

        if args.shoot:
            print("Taking picture...", file=sys.stderr)
            camera.take_picture()
            print("Done.", file=sys.stderr)

        if args.live:
            print("Opening live view window...", file=sys.stderr)
            LiveViewWindow(camera, args.port)

        if args.serve is not _SERVE_DEFAULT:
            serve_stream(camera, args.port, args.serve, args.quality, args.scale)

        if args.download:
            download_photos(camera, args.output, args.date_range, args.extension)

        if args.power_off:
            print("Powering off...", file=sys.stderr)
            camera.send_command("exec_pwoff")
    except KeyboardInterrupt:
        sys.exit(130)
