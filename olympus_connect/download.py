import argparse
import datetime
import os

from .src.camera import OlympusCamera


def download_photos(
    camera: OlympusCamera,
    output_dir: str | None = None,
    daterange: tuple = (None, None),
    extension: str | None = None,
) -> None:
    from .config import get_config

    if output_dir is None:
        output_dir = get_config().get("download", {}).get("output", "./camera-output")
    for cam_file in camera.list_images():
        if extension is not None and not cam_file.file_name.lower().endswith(
            extension.lower()
        ):
            continue

        if all(daterange):
            file_date = datetime.datetime.fromisoformat(cam_file.date_time).date()
            if not (daterange[0] <= file_date <= daterange[1]):
                continue

        local_dir = output_dir

        if not os.path.exists(local_dir):
            try:
                os.makedirs(local_dir)
            except Exception as e:
                print(f"Cannot create directory '{local_dir}': {str(e)}.")
                break

        local_file = os.path.join(local_dir, cam_file.file_name.split("/")[-1])
        msg_file = local_file.replace(os.path.expanduser("~"), "~")
        dt = datetime.datetime.strptime(cam_file.date_time, "%Y-%m-%dT%H:%M:%S")
        tim_epoch = dt.timestamp()

        if os.path.exists(local_file):
            if os.stat(local_file).st_size == cam_file.file_size:
                print(f"File '{msg_file}' exists; skipping download.")
            continue

        image = camera.download_image(cam_file.file_name)
        assert len(image) == cam_file.file_size
        try:
            with open(local_file, "wb") as f:
                f.write(image)
        except Exception as e:
            print(
                f"Failed to download '{cam_file.file_name}' to '{msg_file}': {str(e)}."
            )
            try:
                os.remove(local_file)
            except OSError:
                pass
            continue

        print(
            f"File '{cam_file.file_name}' of {cam_file.file_size:,} bytes"
            f" from {dt} downloaded to '{msg_file}'."
        )
        os.utime(local_file, (tim_epoch, tim_epoch))


def parse_date(date_string: str) -> datetime.date:
    try:
        return datetime.date.today() + datetime.timedelta(days=-int(date_string))
    except ValueError:
        pass
    try:
        return datetime.datetime.strptime(date_string, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {date_string}. \nPlease use YYYY-MM-DD"
        )
