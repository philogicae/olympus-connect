from __future__ import annotations

import datetime
import sys
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from enum import Enum
from threading import Lock
import urllib.request
import urllib.parse
import urllib.error
from http.client import HTTPResponse as _HTTPResponse

_AnyResponse = _HTTPResponse | urllib.error.HTTPError


class _Response:
    __slots__ = ("status_code", "headers", "url", "content", "text")

    def __init__(self, resp: _AnyResponse):
        self.status_code = resp.status
        self.headers = resp.headers
        self.url = resp.url
        self.content = resp.read()
        self.text = self.content.decode()


class ResultError(Exception):
    def __init__(self, msg: str, response: _Response):
        super().__init__(msg)
        self.response = response


class OlympusCamera:
    class CamMode(Enum):
        UNKNOWN = None
        RECORD = "rec"
        PLAY = "play"
        SHUTTER = "shutter"

    @dataclass
    class CmdDescr:
        method: str
        args: dict[str, dict | None] | None

    @dataclass
    class FileDescr:
        file_name: str
        file_size: int
        date_time: str

    ANY_PARAMETER = "*"
    EMPTY_PARAMETERS: dict[str, dict | None] = {ANY_PARAMETER: None}

    def __init__(self):
        from ..config import get_config

        cfg = get_config().get("camera", {})
        self.URL_PREFIX = f"http://{cfg.get('host', '192.168.0.10')}/"
        self.HEADERS = {"User-Agent": cfg.get("user_agent", "OI.Share v2")}
        self.DEFAULT_PORT = cfg.get("live_port", 40000)
        self.DEFAULT_RES = cfg.get("live_resolution", "0640x0480")

        self.versions: dict[str, str] = {}
        self.camera_info = None
        self._cammode = self.CamMode.UNKNOWN
        self._liveview_active = False
        self._liveview_restart = False
        self._liveview_lvqty = self.DEFAULT_RES
        self._liveview_port = self.DEFAULT_PORT
        self._execution_lock = Lock()
        self.commands = {"get_commandlist": self.CmdDescr("get", None)}
        print("  fetching command list...", file=sys.stderr)
        response = self.send_command("get_commandlist")

        for elem in ElementTree.fromstring(response.text):
            if elem.tag == "cgi":
                for http_method in elem:
                    if http_method.tag == "http_method":
                        self.commands[elem.attrib["name"]] = self.CmdDescr(
                            http_method.attrib["type"],
                            self.commandlist_cmds(http_method),
                        )
            elif "version" in elem.tag:
                self.versions[elem.tag] = (elem.text or "").strip()

        print("  getting camera info...", file=sys.stderr)
        info_xml = self._parse_xml(self.send_command("get_caminfo"))
        self.camera_info = (
            {elem.tag: elem.text for elem in info_xml} if info_xml is not None else None
        )

        self.send_command("switch_cammode", mode="rec")
        cam_props_xml = self._parse_xml(
            self.send_command("get_camprop", com="desc", propname="desclist")
        )
        cam_props = []
        if cam_props_xml is not None:
            for prop in cam_props_xml:
                d = {child.tag: child.text for child in prop}
                cam_props.append(d)
        self.camprop_name2values = {
            d["propname"]: (d.get("enum") or " ").split()
            for d in cam_props
            if d.get("attribute") == "getset" and "enum" in d
        }

        print("  switching to play mode...", file=sys.stderr)
        self._switch_cammode(self.CamMode.PLAY)

    def commandlist_params(self, parent: ElementTree.Element) -> dict[str, dict | None]:
        params = {}
        for param in parent:
            if param.tag.startswith("cmd"):
                return {
                    self.ANY_PARAMETER: {
                        param.attrib["name"].strip(): self.commandlist_params(param)
                    }
                }
            else:
                name = (
                    param.attrib["name"].strip()
                    if "name" in param.attrib
                    else self.ANY_PARAMETER
                )
                params[name] = self.commandlist_cmds(param)
        return params if params else self.EMPTY_PARAMETERS

    def commandlist_cmds(
        self, parent: ElementTree.Element
    ) -> dict[str, dict | None] | None:
        cmds: dict[str, dict | None] = {}
        for cmd in parent:
            assert cmd.tag.startswith("cmd")
            cmds[cmd.attrib["name"].strip()] = self.commandlist_params(cmd)
        return cmds if cmds else None

    def _request(self, method: str, url: str, **kw) -> _Response:
        if "params" in kw and kw["params"]:
            url += "?" + urllib.parse.urlencode(kw["params"])
        data = kw.get("data")
        headers = kw.get("headers", self.HEADERS)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=kw.get("timeout"))
        except urllib.error.HTTPError as e:
            resp = e
        return _Response(resp)

    def send_command(self, command: str, **args) -> _Response:
        url = f"{self.URL_PREFIX}{command}.cgi"
        method = self.commands[command].method
        print(f"  >> {method.upper()} {command}.cgi {args or ''}", file=sys.stderr)
        if method == "get":
            response = self._request("GET", url, params=args or None)
        else:
            assert method == "post"
            if "post_data" not in args:
                raise ValueError(
                    f"Error in '{command}' with args "
                    f"'{', '.join([k + '=' + v for k, v in args.items()])}': "
                    "missing entry 'post_data' for method 'post'."
                )
            post_data = args.pop("post_data")
            headers = self.HEADERS.copy()
            if len(post_data) > 6 and post_data[:6] == b"<?xml ":
                headers["Content-Type"] = "text/plain;charset=utf-8"
            response = self._request(
                "POST", url, params=args or None, data=post_data, headers=headers
            )

        if response.status_code in (200, 202):
            return response
        else:
            err_xml = self._parse_xml(response)
            if err_xml is not None:
                msg = ", ".join(f"{elem.tag}={elem.text}" for elem in err_xml)
            else:
                msg = response.text.replace("\r\n", "")
            raise ResultError(
                f"Error #{response.status_code} "
                f"for url '{response.url.replace('%2F', '/')}': "
                f"{msg}.",
                response,
            )

    def _switch_cammode(self, cammode: CamMode, lvqty: str | None = None) -> None:
        if self._cammode.value != cammode.value and cammode != self.CamMode.UNKNOWN:
            kwargs = {"mode": cammode.value}
            if lvqty is not None:
                kwargs["lvqty"] = lvqty
            self.send_command("switch_cammode", **kwargs)
            self._cammode = cammode
            self._liveview_active = False

    def _action_begin(self, cammode: CamMode) -> bool:
        if self._execution_lock.acquire(timeout=10):
            self._liveview_restart = self._liveview_active
            self._switch_cammode(cammode)
            return True
        return False

    def _action_end(self) -> None:
        self._execution_lock.release()
        if self._liveview_restart and not self._liveview_active:
            self.start_liveview(self._liveview_port, self._liveview_lvqty)

    def get_camprop(self, propname: str) -> str:
        if self._action_begin(self.CamMode.RECORD):
            xml = self._parse_xml(
                self.send_command("get_camprop", com="get", propname=propname)
            )
            self._action_end()
            assert xml is not None
            elem = xml.find("value")
            assert elem is not None and elem.text is not None
            return elem.text
        return ""

    def set_camprop(self, propname: str, value: str) -> None:
        if self._action_begin(self.CamMode.RECORD):
            set_value_xml = (
                '<?xml version="1.0"?>\r\n<set>\r\n'
                f"<value>{value}</value>\r\n</set>\r\n"
            )
            self.send_command(
                "set_camprop",
                com="set",
                propname=propname,
                post_data=set_value_xml.encode("utf-8"),
            )
            self._action_end()

    def _parse_xml(self, response: _Response) -> ElementTree.Element | None:
        if response.headers.get("Content-Type") == "text/xml":
            return ElementTree.fromstring(response.text)
        return None

    def set_clock(self) -> None:
        if self._action_begin(self.CamMode.PLAY):
            self.send_command(
                "set_utctimediff",
                utctime=datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S"),
                diff=time.strftime("%z"),
            )
            self._action_end()

    def take_picture(self) -> None:
        args_mode = self.commands["switch_cammode"].args
        mode = args_mode.get("mode") if args_mode else None
        has_shutter = isinstance(mode, dict) and "shutter" in mode
        if not has_shutter:
            if self._action_begin(self.CamMode.RECORD):
                if not self._liveview_active:
                    self.start_liveview(self.DEFAULT_PORT, self._liveview_lvqty)
                    self.send_command("exec_takemotion", com="starttake")
                    self.stop_liveview()
                else:
                    self.send_command("exec_takemotion", com="starttake")
                self._action_end()
        else:
            if self._action_begin(self.CamMode.SHUTTER):
                time.sleep(0.5)
                self.send_command("exec_shutter", com="1st2ndpush")
                time.sleep(0.5)
                self.send_command("exec_shutter", com="2nd1strelease")
                self._action_end()

    def list_images(self, dir: str = "/DCIM") -> list[FileDescr]:
        try:
            result = self.send_command("get_imglist", DIR=dir)
        except ResultError as e:
            if e.response.status_code == 404:
                return []
            raise
        images = []
        for line in result.text.split("\r\n"):
            components = line.split(",")
            if len(components) != 6:
                continue
            path = "/".join(components[:2])
            size, attrib, date, time = [int(cmp) for cmp in components[2:]]
            datetime = (
                f"{1980 + (date >> 9)}-{(date >> 5) & 15:02d}-{date & 31:02d}"
                f"T{time >> 11:02d}:{(time >> 5) & 63:02d}:{2 * (time & 31):02d}"
            )
            if attrib & 16:
                images += self.list_images(path)
            elif not (attrib & 15):
                images.append(self.FileDescr(path, size, datetime))
        return images

    def download_image(self, dir: str) -> bytes:
        return urllib.request.urlopen(
            urllib.request.Request(self.URL_PREFIX + dir[1:], headers=self.HEADERS)
        ).read()

    def start_liveview(self, port: int, lvqty: str) -> None:
        print(f"  starting liveview (port {port}, res {lvqty})...", file=sys.stderr)
        if self._action_begin(self.CamMode.PLAY):
            self._switch_cammode(cammode=self.CamMode.RECORD, lvqty=lvqty)
            self._liveview_lvqty = lvqty
            self._liveview_port = port
            self.send_command("exec_takemisc", com="startliveview", port=port)
            self._liveview_active = True
            self._action_end()

    def stop_liveview(self) -> None:
        if self._liveview_active:
            if self._action_begin(self.CamMode.RECORD):
                self.send_command("exec_takemisc", com="stopliveview")
                self._switch_cammode(self.CamMode.PLAY)
                self._liveview_active = False
                self._liveview_restart = False
                self._action_end()

    def report_model(self) -> None:
        model = (
            self.camera_info.get("model", "unknown model")
            if self.camera_info
            else "unknown model"
        )
        versions = ", ".join([f"{key} {value}" for key, value in self.versions.items()])
        print(f"Connected to Olympus {model}, {versions}.")
