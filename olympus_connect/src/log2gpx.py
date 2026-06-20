import argparse
import os
import sys
import xml.etree.ElementTree as ET


def read_log(fn: str) -> list[tuple[float, float, str, str]]:
    result = []
    line_no = 0
    with open(fn) as f:
        for line in f:
            line = line.strip()
            if not line:
                break
            line_no += 1

            components = line.split(",")
            if len(components) < 11:
                continue

            cksum = 8
            for c in line[: line.rfind(",")]:
                cksum ^= ord(c)

            if f"*{cksum:2X}" != components[-1]:
                print(
                    f"Checksum error: '*{cksum:2X}' vs. '{components[-1]}' "
                    f"in line {line_no}: '{line}'.",
                    file=sys.stderr,
                )
                continue

            if components[0] == "$GPGGA":
                elevation = components[9]
                assert components[10] == "M"
                continue

            if components[0] != "$GPRMC":
                continue

            time, a_or_v, lat, n_or_s, lon, e_or_w, _, _, date = components[1:10]

            if a_or_v != "A":
                print(f"Invalid line {line_no}: '{line}'.", file=sys.stderr)
                continue

            assert lat[4] == "."
            latitude = float(lat[:2]) + float(lat[2:]) / 60
            if n_or_s == "S":
                latitude = -latitude

            assert lon[5] == "."
            longitude = float(lon[:3]) + float(lon[3:]) / 60
            if e_or_w == "W":
                longitude = -longitude

            if time[-2:] == ".0":
                time = time[:-2]
            iso_time = (
                f"20{date[4:6]}-{date[2:4]}-{date[:2]}T"
                f"{time[:2]}:{time[2:4]}:{time[4:]}Z"
            )

            result.append((latitude, longitude, elevation, iso_time))

    return result


def write_gpx(fn: str, track: list[tuple[float, float, str, str]]) -> None:
    ns = "http://www.topografix.com/GPX/1/1"
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    ET.register_namespace("", ns)
    ET.register_namespace("xsi", xsi)
    gpx = ET.Element(
        f"{{{ns}}}gpx",
        version="1.1",
        creator="log2gpx.py https://github.com/philogicae/olympus-connect",
    )
    gpx.set(
        f"{{{xsi}}}schemaLocation", f"{ns} http://www.topografix.com/GPX/1/1/gpx.xsd"
    )
    trk = ET.SubElement(gpx, f"{{{ns}}}trk")
    name = ET.SubElement(trk, f"{{{ns}}}name")
    name.text = os.path.splitext(os.path.split(fn)[1])[0]
    trkseg = ET.SubElement(trk, f"{{{ns}}}trkseg")
    for lat, lon, ele, iso_time in track:
        trkpt = ET.SubElement(
            trkseg, f"{{{ns}}}trkpt", lat=f"{lat:.6f}", lon=f"{lon:.6f}"
        )
        ET.SubElement(trkpt, f"{{{ns}}}ele").text = ele
        ET.SubElement(trkpt, f"{{{ns}}}time").text = iso_time
    ET.indent(gpx)
    ET.ElementTree(gpx).write(fn, xml_declaration=True, encoding="utf-8")


def main() -> None:
    def existing_file(fn):
        if not os.path.isfile(fn):
            raise argparse.ArgumentTypeError(f"File '{fn}' cannot be read.")
        return fn

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "log",
        type=existing_file,
        nargs="+",
        help="Convert a GPS track from .LOG to .gpx format.",
    )
    args = parser.parse_args()

    try:
        for fn in args.log:
            track = read_log(fn)
            if len(track) == 0:
                print(f"No GPS track found in '{fn}'.", file=sys.stderr)
            else:
                outfn = os.path.splitext(fn)[0] + ".gpx"
                print(f"Converting '{fn} to '{outfn}'.")
                write_gpx(outfn, track)
    except KeyboardInterrupt:
        sys.exit(130)
