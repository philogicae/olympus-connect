import io
import queue
import socket
import sys
import threading
import tkinter

from PIL import Image, ImageTk

from .src.camera import OlympusCamera


class LiveViewReceiver:
    MAX_QUEUE_SIZE = 50

    def __init__(self, img_queue: queue.SimpleQueue):
        self.running = True
        self.img_queue = img_queue
        self.prev_sequence_number = 0
        self.assembling_frame = False  # ; ponytail: inline init_frame
        self.frame = b""
        self.extension = b""

    def shut_down(self):
        self.running = False

    def receive_packets(self, port: int) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("", port))
            sock.settimeout(1)
            while True:
                try:
                    packet = sock.recv(4096)
                except Exception as e:
                    if "timed out" in str(e):
                        if self.running:
                            continue
                    else:
                        print("Error reading liveview:", str(e))
                    break
                self.process_packet(packet)

    def decode_rtp(self, packet: bytes) -> tuple[int, int, bytes]:
        version = packet[0] >> 6
        assert version == 2
        padding = bool(packet[0] & 32)
        extension = bool(packet[0] & 16)
        csrc_count = packet[0] & 15
        marker = bool(packet[1] & 128)
        sequence_number = (packet[2] << 8) + packet[3]
        if padding:
            packet = packet[: -packet[-1]]
        if extension:
            start = 14 + 4 * csrc_count
            extension_header_length = (packet[start] << 8) + packet[start + 1]
            start += 2
            size = 4 * extension_header_length
            self.extension = packet[start : start + size]
            payload = packet[start + size :]
        else:
            payload = packet[12 + 4 * csrc_count :]
        return marker, sequence_number, payload

    def process_packet(self, packet: bytes) -> None:
        marker, sequence_number, payload = self.decode_rtp(packet)
        if self.assembling_frame:
            self.frame += payload
            if (self.prev_sequence_number + 1) % 65536 != sequence_number:
                self.assembling_frame = (
                    False  # ; ponytail: inline init_frame(valid=False)
                )
                self.frame = b""
                self.extension = b""
        self.prev_sequence_number = sequence_number
        if marker:
            if self.frame:
                self.process_frame(self.frame)
            self.assembling_frame = True  # ; ponytail: inline init_frame()
            self.frame = b""
            self.extension = b""

    def process_frame(self, frame: bytes) -> None:
        if frame[:2] == b"\xff\xd8" and frame[-2:] == b"\xff\xd9":
            while self.img_queue.qsize() >= self.MAX_QUEUE_SIZE:
                self.img_queue.get()
            self.img_queue.put((frame, self.extension))


class LiveViewWindow:
    UPDATE_INTERVAL = 25

    def __init__(self, camera: OlympusCamera, port: int | None = None):
        from .config import get_config

        if port is None:
            port = get_config().get("camera", {}).get("live_port", 40000)
        print("  creating tkinter window...", file=sys.stderr)
        self.power_off = False
        self.camera = camera
        self.port = port
        self.img_queue: queue.SimpleQueue = queue.SimpleQueue()
        self.window = tkinter.Tk()
        self.width = self.height = None
        if camera.camera_info and "model" in camera.camera_info:
            self.window.title(camera.camera_info["model"])
        else:
            self.window.title("LiveView")

        self.lvqty_list = ["0640x0480"]
        if "switch_cammode" in camera.commands:
            args = camera.commands["switch_cammode"].args
            if args:  # ; ponytail: chained get keeps it flat
                lvqty = ((args.get("mode") or {}).get("rec") or {}).get("lvqty")
                if lvqty:
                    self.lvqty_list = list(lvqty)
        self.lvqty_cur = 0
        width_height_min = min(
            self.window.winfo_screenwidth(), self.window.winfo_screenheight()
        )
        for i, lvqty in enumerate(self.lvqty_list):
            if max([int(c) for c in lvqty.split("x")]) < width_height_min:
                self.lvqty_cur = i
        self.lvqty_var = tkinter.IntVar()
        self.lvqty_var.set(self.lvqty_cur)
        self.lvqty_var.trace_add("write", self.on_lvqty)

        self.camprop_info: dict = {}  # ; ponytail: untyped dict keeps type-checker quiet
        camera.send_command("switch_cammode", mode="rec")
        cam_props = camera.xml_response(
            camera.send_command("get_camprop", com="desc", propname="desclist")
        )
        if isinstance(cam_props, list):
            for prop in cam_props:
                if prop["attribute"] != "getset":
                    continue
                values = prop["enum"].split()
                index = values.index(prop["value"])
                if index == -1:
                    continue
                variable = tkinter.IntVar()
                variable.set(index)
                variable.trace_add("write", self.on_camprop)
                self.camprop_info[
                    str(variable)
                ] = {  # ; ponytail: dict replaces inner class
                    "name": prop["propname"],
                    "values": values,
                    "cur_val": index,
                    "variable": variable,
                }
        camera.send_command("switch_cammode", mode="play")

        self.menubar = tkinter.Menu(self.window)
        self.filemenu = tkinter.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Take picture", command=self.take_pic)
        self.filemenu.add_command(label="Set clock", command=self.set_clock)
        self.filemenu.add_command(label="Exit", command=self.window.destroy)
        self.filemenu.add_command(
            label="Exit & Camera off", command=self.power_off_and_exit
        )
        self.menubar.add_cascade(label="File", menu=self.filemenu)

        self.viewmenu = tkinter.Menu(self.menubar, tearoff=0)
        self.sizemenu = tkinter.Menu(self.viewmenu, tearoff=0)
        for value, label in enumerate(self.lvqty_list):
            self.sizemenu.add_radiobutton(
                label=label, value=value, variable=self.lvqty_var
            )
        self.viewmenu.add_cascade(label="Size", menu=self.sizemenu)
        self.menubar.add_cascade(label="View", menu=self.viewmenu)

        self.campropmenu = tkinter.Menu(self.menubar, tearoff=0)
        for camprop in self.camprop_info.values():
            menu = tkinter.Menu(self.campropmenu, tearoff=0)
            for value, label in enumerate(camprop["values"]):
                menu.add_radiobutton(
                    label=label, value=value, variable=camprop["variable"]
                )
            self.campropmenu.add_cascade(label=camprop["name"], menu=menu)
        self.menubar.add_cascade(label="Settings", menu=self.campropmenu)
        self.window.config(menu=self.menubar)

        camera.start_liveview(port=self.port, lvqty=self.lvqty_list[self.lvqty_cur])

        print("  binding UDP listener on port", port, "...", file=sys.stderr)
        udp_client = LiveViewReceiver(self.img_queue)
        thread = threading.Thread(target=udp_client.receive_packets, args=[port])
        thread.start()

        print("  waiting for first frame...", file=sys.stderr)
        self.img = self.next_image()
        self.width = self.img.width()
        self.height = self.img.height()
        self.window.geometry(f"{self.width}x{self.height}")
        self.window.configure(background="grey")
        self.camimage = tkinter.Label(self.window, image=self.img)
        self.camimage.pack(side="bottom", fill="both", expand=1)

        self.window.after(self.UPDATE_INTERVAL, self.check_update_image)
        self.window.mainloop()

        udp_client.shut_down()
        self.camera.stop_liveview()
        thread.join()

        if self.power_off:
            self.camera.send_command("switch_cammode", mode="play")
            self.camera.send_command("exec_pwoff")

    def take_pic(self) -> None:
        self.camera.take_picture()

    def on_lvqty(self, *args) -> None:
        if self.lvqty_cur != self.lvqty_var.get():
            self.lvqty_cur = self.lvqty_var.get()
            self.camera.stop_liveview()
            self.camera.start_liveview(
                port=self.port, lvqty=self.lvqty_list[self.lvqty_cur]
            )

    def on_camprop(self, var_name: str, *dummy) -> None:
        camprop = self.camprop_info[var_name]
        if camprop["cur_val"] != camprop["variable"].get():
            camprop["cur_val"] = camprop["variable"].get()
            self.camera.set_camprop(
                camprop["name"], camprop["values"][camprop["cur_val"]]
            )

    def next_image(self) -> ImageTk.PhotoImage:
        try:
            jpeg_and_extension = self.img_queue.get(timeout=4.0)
        except queue.Empty:
            raise TimeoutError(
                "Timeout while waiting for imagedata from camera. Maybe you need to check your "
                "firewall settings for incoming UDP traffic (from 192.168.0.10)."
            )

        jpeg, extension = jpeg_and_extension
        orientation = self.get_orientation(extension)
        if orientation is None or orientation == 1:
            return ImageTk.PhotoImage(data=jpeg)
        with io.BytesIO(jpeg) as file:
            img = Image.open(file)
            img.load()
        img = img.transpose(
            Image.ROTATE_180
            if orientation == 3
            else Image.ROTATE_90
            if orientation == 8
            else Image.ROTATE_270
        )
        return ImageTk.PhotoImage(img)

    def check_update_image(self) -> None:
        while True:
            if not self.img_queue.empty():
                try:
                    img = self.next_image()
                    self.camimage.configure(image=img)
                    self.img = img
                    if img.width() != self.width or img.height() != self.height:
                        self.width = img.width()
                        self.height = img.height()
                        self.window.geometry(f"{self.width}x{self.height}")
                except OSError:
                    continue
            break
        self.window.after(self.UPDATE_INTERVAL, self.check_update_image)

    def get_orientation(self, extension: bytes) -> int | None:
        idx = 0
        while idx < len(extension):
            func_id = (extension[idx] << 8) + extension[idx + 1]
            length = 4 * ((extension[idx + 2] << 8) + extension[idx + 3])
            idx += 4

            if func_id == 4:
                orientation = extension[idx + 3]
                return orientation if orientation in [1, 3, 6, 8] else None

            idx += length
        return None

    def set_clock(self):
        self.camera.set_clock()

    def power_off_and_exit(self):
        self.power_off = True
        self.window.destroy()


def serve_stream(
    camera: OlympusCamera, lvport: int | None = None, http_port: int | None = None
):
    from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
    from .config import get_config

    cfg = get_config().get("server", {})
    ccfg = get_config().get("camera", {})
    if lvport is None:
        lvport = ccfg.get("live_port", 40000)
    if http_port is None:
        http_port = cfg.get("http_port", 8080)
    bind = cfg.get("bind", "0.0.0.0")
    res = ccfg.get("live_resolution", "0640x0480")

    q: queue.SimpleQueue = queue.SimpleQueue()

    print(f"  starting liveview on port {lvport}...", file=sys.stderr)
    camera.start_liveview(port=lvport, lvqty=res)
    receiver = LiveViewReceiver(q)
    t = threading.Thread(target=receiver.receive_packets, args=[lvport], daemon=True)
    t.start()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/stream":
                self._stream_mjpeg()
            else:
                self._serve_html()

        def _serve_html(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b'<html><body><img src="/stream"/></body></html>')

        def _stream_mjpeg(self):
            self.send_response(200)
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                try:
                    jpeg, _ = q.get(timeout=1)
                except queue.Empty:
                    continue
                try:
                    self.wfile.write(
                        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                    )
                except OSError:
                    break

        def log_message(self, format, *args):
            pass  # ; ponytail: silence HTTP access logs

    server = ThreadingHTTPServer((bind, http_port), _Handler)
    print(f"  MJPEG stream at http://0.0.0.0:{http_port}/", file=sys.stderr)
    print("  Press Ctrl-C to stop.", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    server.shutdown()
    receiver.shut_down()
    camera.stop_liveview()
