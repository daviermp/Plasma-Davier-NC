"""
DAVIER NC PLASMA DAVIER NC PLASMA V3.3 - LOGO + SELECTOR PUERTO
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re, threading, time, math, os, sys
from datetime import datetime
from collections import deque
from pathlib import Path

def resource_path(relative):
    # For PyInstaller bundle
    try:
        base = sys._MEIPASS
    except:
        base = os.path.abspath(".")
    return os.path.join(base, relative)

def get_icon_path():
    for name in ["davier_icon.ico", "davier_logo_transparent.png", "davier_icon_256.png"]:
        p = resource_path(name)
        if os.path.exists(p):
            return p
        if os.path.exists(name):
            return name
    return None


try:
    import serial
    import serial.tools.list_ports
    HAS_SERIAL = True
except:
    HAS_SERIAL = False

# Colores exactos de tu foto
BG_MAIN = "#0f0f14"
BG_PANEL = "#17171f"
BG_DARK = "#0a0a0f"
BG_INPUT = "#1e1e28"
NEON = "#8cff00"
NEON_DIM = "#4a7a00"
GRID_LINE = "#1a2e1a"
YELLOW = "#ffcc00"
YELLOW_DARK = "#e6b800"

class FluidNC:
    def __init__(self, log_cb=None):
        self.ser = None
        self.connected = False
        self.port = "COM3"
        self.baud = 115200
        self.log_cb = log_cb
        self.status = {"state": "IDLE", "x": 0, "y": 0, "z": 0, "feed": 0, "line": 0}
        self.running = False
        self.rx = deque(maxlen=200)
        self.thc_enabled = True
        self.thc_voltage = 0
        self.arc_ok = False
        self.torch_on = False

    def log(self, msg):
        if self.log_cb: self.log_cb(msg)

    def list_ports(self):
        if not HAS_SERIAL:
            return [f"COM{i}" for i in range(1,11)]
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports] if ports else ["COM3", "COM4", "COM5"]

    def connect(self, port, baud=115200):
        self.port = port
        self.baud = baud
        if not HAS_SERIAL:
            self.connected = True
            self.running = True
            return True, f"Conectado SIM {port}"
        try:
            self.ser = serial.Serial(port, baud, timeout=0.2)
            time.sleep(2)
            self.ser.write(b"\x18")
            time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.connected = True
            self.running = True
            threading.Thread(target=self._listen, daemon=True).start()
            self.send("$10=3")
            return True, f"Conectado a {port}"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        self.running=False
        if self.ser:
            try: self.ser.close()
            except: pass
        self.connected=False

    def _listen(self):
        while self.running and self.connected:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode(errors='ignore').strip()
                    if line:
                        self.rx.append(line)
                        if line.startswith("<"):
                            m=re.search(r'MPos:([-\d.]+),([-\d.]+),([-\d.]+)',line)
                            if m:
                                self.status["x"]=float(m.group(1)); self.status["y"]=float(m.group(2)); self.status["z"]=float(m.group(3))
            except: pass
            time.sleep(0.05)

    def send(self, cmd):
        if not self.connected:
            self.log(f"[OFF] {cmd}"); return False
        if HAS_SERIAL and self.ser:
            try: self.ser.write(f"{cmd}\n".encode()); self.log(f"> {cmd}"); return True
            except Exception as e: self.log(str(e)); return False
        else:
            self.log(f"[SIM] {cmd}"); return True

    def jog(self, axis, dist, feed=4000):
        return self.send(f"$J=G91 G21 {axis}{dist} F{feed}")
    def home(self): return self.send("$H")
    def unlock(self): return self.send("$X")
    def reset(self): return self.send("\x18")
    def hold(self): return self.send("!")
    def resume(self): return self.send("~")
    def torch_on_cmd(self): self.torch_on=True; return self.send("M3 S1000")
    def torch_off_cmd(self): self.torch_on=False; return self.send("M5")
    def thc_on(self): self.thc_enabled=True; return self.send("M62 P0")
    def thc_off(self): self.thc_enabled=False; return self.send("M63 P0")


class PortDialog:
    def __init__(self, parent, fluid):
        self.fluid = fluid
        self.result = None
        self.top = tk.Toplevel(parent)
        self.top.title("Conectar - Seleccionar Puerto")
        self.top.geometry("380x340")
        self.top.configure(bg=BG_PANEL)
        self.top.transient(parent)
        self.top.grab_set()
        # centrar
        self.top.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width()//2) - 190
        y = parent.winfo_y() + (parent.winfo_height()//2) - 170
        self.top.geometry(f"+{x}+{y}")

        tk.Label(self.top, text="⚡ Seleccionar Puerto COM", bg=BG_PANEL, fg=NEON, font=("Segoe UI", 12, "bold")).pack(pady=12)

        tk.Label(self.top, text="Puertos disponibles:", bg=BG_PANEL, fg="white", font=("Segoe UI",9)).pack(anchor="w", padx=20)

        self.listbox = tk.Listbox(self.top, bg=BG_INPUT, fg="white", selectbackground=NEON, selectforeground="black", font=("Consolas",10), height=8, bd=1, highlightthickness=1, highlightcolor=NEON)
        self.listbox.pack(fill="both", padx=20, pady=5, expand=True)

        ports = fluid.list_ports()
        for p in ports:
            self.listbox.insert("end", p)
        if ports:
            self.listbox.select_set(0)

        # baud
        frame_baud = tk.Frame(self.top, bg=BG_PANEL)
        frame_baud.pack(fill="x", padx=20, pady=8)
        tk.Label(frame_baud, text="Baudrate:", bg=BG_PANEL, fg="white", font=("Segoe UI",9)).pack(side="left")
        self.baud_var = tk.StringVar(value="115200")
        baud_combo = ttk.Combobox(frame_baud, textvariable=self.baud_var, values=["9600","19200","38400","57600","115200","250000"], width=12, state="readonly")
        baud_combo.pack(side="right")

        # botones
        bf = tk.Frame(self.top, bg=BG_PANEL)
        bf.pack(fill="x", padx=20, pady=12)
        tk.Button(bf, text="Cancelar", bg="#1a1a1a", fg="white", width=12, bd=1, relief="solid", command=self.cancel).pack(side="left")
        tk.Button(bf, text="Conectar", bg=NEON, fg="black", width=12, bd=0, font=("Segoe UI",9,"bold"), command=self.do_connect).pack(side="right")

        self.top.bind("<Double-Button-1>", lambda e: self.do_connect())
        self.top.protocol("WM_DELETE_WINDOW", self.cancel)

    def do_connect(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Puerto", "Selecciona un puerto")
            return
        port = self.listbox.get(sel[0])
        baud = int(self.baud_var.get())
        self.result = (port, baud)
        self.top.destroy()

    def cancel(self):
        self.result = None
        self.top.destroy()


class GCodePreview(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg="#0a0e0a", highlightthickness=1, highlightbackground=NEON_DIM, **kw)
        self.gcode_lines=[]
        self.bounds=(0,0,1000,600)
        self.mat_w=800; self.mat_h=500
        self.current=(0,0)
        self.progress=0.42
        self.bind("<Configure>", lambda e: self.redraw())

    def load_gcode(self, text):
        self.gcode_lines=[]
        xs=[]; ys=[]
        x=y=0
        for line in text.splitlines():
            line=line.strip()
            if not line: continue
            mx=re.search(r'X([-\d.]+)',line); my=re.search(r'Y([-\d.]+)',line)
            if mx: x=float(mx.group(1)); xs.append(x)
            if my: y=float(my.group(1)); ys.append(y)
            self.gcode_lines.append((x,y,line))
        if xs and ys:
            fw=max(xs)-min(xs); fh=max(ys)-min(ys)
            self.bounds=(min(xs), min(ys), fw, fh)
            self.redraw()
            return fw,fh,0,0
        self.redraw()
        return 0,0,0,0

    def set_material(self, w,h):
        self.mat_w=w; self.mat_h=h
        self.redraw()

    def redraw(self):
        self.delete("all")
        w=self.winfo_width(); h=self.winfo_height()
        if w<10 or h<10: return
        # grid
        for i in range(0, w, 40):
            self.create_line(i,0,i,h, fill=GRID_LINE, dash=(2,4))
        for i in range(0, h, 40):
            self.create_line(0,i,w,i, fill=GRID_LINE, dash=(2,4))

        # escala material
        pad=40
        sx = (w-2*pad)/max(self.mat_w,1000)
        sy = (h-2*pad)/max(self.mat_h,600)
        s=min(sx,sy)

        # transformar
        def tx(x): return pad + x*s
        def ty(y): return h - pad - y*s

        # dibujar trayectoria programada (neon)
        if self.gcode_lines:
            pts=[]
            for x,y,_ in self.gcode_lines:
                pts.append(tx(x)); pts.append(ty(y))
            if len(pts)>=4:
                self.create_line(pts, fill=NEON, width=2, smooth=False, capstyle="round")

        # ejes labels
        self.create_text(w//2, h-10, text="X (mm)", fill="#555", font=("Consolas",8))
        self.create_text(15, h//2, text="Y (mm)", fill="#555", font=("Consolas",8), angle=90)


class DavierPlasmaV33:
    def __init__(self, root):
        self.root=root
        root.title("DAVIER NC PLASMA V3.3")
        root.geometry("1280x720")
        root.configure(bg=BG_MAIN)
        root.minsize(1024,600)
        # ICONO DE VENTANA - TU LOGO
        try:
            icon_path = get_icon_path()
            if icon_path and icon_path.endswith(".ico") and os.path.exists(icon_path):
                root.iconbitmap(icon_path)
            else:
                # Usar PNG como iconphoto
                png_path = None
                for cand in ["davier_icon_256.png", "davier_logo_transparent.png", "davier_icon.png"]:
                    rp = resource_path(cand)
                    if os.path.exists(rp):
                        png_path = rp
                        break
                if png_path:
                    from PIL import Image, ImageTk
                    img = Image.open(png_path)
                    img = img.resize((32,32), Image.LANCZOS)
                    self.icon_tk = ImageTk.PhotoImage(img)
                    root.iconphoto(True, self.icon_tk)
        except Exception as e:
            print(f"Icon load error: {e}")

        self.fluid=FluidNC(log_callback=self.log)
        self.gcode_text=""

        # TOP BAR
        top=tk.Frame(root, bg="#0a0a0f", height=62)
        top.pack(fill="x")
        top.pack_propagate(False)

        # Logo izquierda - CON LOGO REAL
        logo_frame=tk.Frame(top, bg="#0a0a0f")
        logo_frame.pack(side="left", padx=5, pady=2)
        try:
            # Intentar cargar logo completo de tu foto
            logo_path = None
            for cand in ["davier_logo_full_transparent.png", "logo_raw.png", "davier_logo_transparent.png"]:
                rp = resource_path(cand)
                if os.path.exists(rp):
                    logo_path = rp
                    break
                if os.path.exists(cand):
                    logo_path = cand
                    break
            
            if logo_path:
                from PIL import Image, ImageTk
                pil_img = Image.open(logo_path)
                # redimensionar a altura 48px manteniendo aspecto
                h = 48
                w = int(pil_img.width * (h / pil_img.height))
                pil_img = pil_img.resize((w, h), Image.LANCZOS)
                self.logo_img_tk = ImageTk.PhotoImage(pil_img)
                tk.Label(logo_frame, image=self.logo_img_tk, bg="#0a0a0f").pack(side="left", padx=5)
            else:
                raise FileNotFoundError
        except Exception as e:
            # fallback texto si no hay imagen
            tk.Label(logo_frame, text="⬢", fg=NEON, bg="#0a0a0f", font=("Segoe UI",24)).pack(side="left")
            tk.Label(logo_frame, text="DAVIER NC PLASMA V3.1", fg=NEON, bg="#0a0a0f", font=("Segoe UI",16,"bold")).pack(side="left", padx=8)

        # Conectado derecha
        self.conn_frame=tk.Frame(top, bg="#111116", highlightbackground=NEON_DIM, highlightthickness=1)
        self.conn_frame.pack(side="right", padx=15, pady=8)
        self.conn_label=tk.Label(self.conn_frame, text="● DESCONECTADO\nCOM3", fg="#ff4444", bg="#111116", font=("Consolas",8,"bold"), justify="left")
        self.conn_label.pack(side="left", padx=8, pady=4)
        tk.Button(self.conn_frame, text="Conectar", bg=BG_MAIN, fg=NEON, bd=1, highlightbackground=NEON, font=("Segoe UI",8,"bold"), command=self.toggle_connect).pack(side="left", padx=6, pady=4)

        # MAIN SPLIT
        main_pane=tk.Frame(root, bg=BG_MAIN)
        main_pane.pack(fill="both", expand=True, padx=6, pady=4)

        # LEFT PANEL 260px
        left=tk.Frame(main_pane, bg=BG_PANEL, width=270, highlightbackground=NEON_DIM, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0,6))
        left.pack_propagate(False)

        # Manual XYZ
        tk.Label(left, text="⚙ Manual XYZ", fg=NEON, bg=BG_PANEL, font=("Segoe UI",9,"bold"), anchor="w").pack(fill="x", padx=10, pady=(10,6))

        tk.Label(left, text="Controles Manuales", fg="white", bg=BG_PANEL, font=("Segoe UI",8)).pack(anchor="w", padx=10, pady=2)

        # Controles grid
        ctrl=tk.Frame(left, bg=BG_PANEL)
        ctrl.pack(fill="x", padx=8, pady=4)

        self.step_var=tk.StringVar(value="1.00 mm")

        def jog_btn(axis, dir, txt):
            return tk.Button(ctrl, text=txt, bg=BG_INPUT, fg="white", bd=1, relief="solid", font=("Consolas",8), width=10, command=lambda a=axis,d=dir: self.jog(a,d))

        # X
        row=tk.Frame(ctrl, bg=BG_PANEL); row.pack(fill="x", pady=2)
        tk.Label(row, text="X", bg=NEON_DIM, fg=NEON, width=2, font=("Segoe UI",9,"bold")).pack(side="left")
        jog_btn("X", -1, "◂ [ X- ] ▸").pack(side="left", padx=4)
        jog_btn("X", 1, "◂ [ X+ ] ▸").pack(side="left", padx=4)
        # Y
        row=tk.Frame(ctrl, bg=BG_PANEL); row.pack(fill="x", pady=2)
        tk.Label(row, text="Y", bg=NEON_DIM, fg=NEON, width=2, font=("Segoe UI",9,"bold")).pack(side="left")
        jog_btn("Y", -1, "▴ [ Y- ] ▾").pack(side="left", padx=4)
        jog_btn("Y", 1, "▾ [ Y+ ] ▴").pack(side="left", padx=4)
        # Z
        row=tk.Frame(ctrl, bg=BG_PANEL); row.pack(fill="x", pady=2)
        tk.Label(row, text="Z", bg=NEON_DIM, fg=NEON, width=2, font=("Segoe UI",9,"bold")).pack(side="left")
        jog_btn("Z", -1, "▾ [ Z- ] ▾").pack(side="left", padx=4)
        jog_btn("Z", 1, "▾ [ Z+ ] ▴").pack(side="left", padx=4)

        # Paso
        pf=tk.Frame(left, bg=BG_PANEL, highlightbackground="#222", highlightthickness=1)
        pf.pack(fill="x", padx=8, pady=8)
        tk.Label(pf, text="Paso / Step", fg="#aaa", bg=BG_PANEL, font=("Segoe UI",7)).pack(anchor="w", padx=6, pady=(4,0))
        ttk.Combobox(pf, textvariable=self.step_var, values=["0.10 mm","0.50 mm","1.00 mm","5.00 mm","10.00 mm"], state="readonly", width=18).pack(padx=6, pady=4, fill="x")

        # Separador verde
        tk.Frame(left, bg=NEON, height=2).pack(fill="x", padx=8, pady=6)

        # Configuracion
        tk.Label(left, text="Configuración — Parámetros de Máquina", fg=NEON, bg=BG_PANEL, font=("Segoe UI",7,"bold")).pack(anchor="w", padx=10, pady=2)

        form=tk.Frame(left, bg=BG_PANEL)
        form.pack(fill="x", padx=10, pady=4)

        tk.Label(form, text="Área de Corte", fg="white", bg=BG_PANEL, font=("Segoe UI",8,"bold")).pack(anchor="w", pady=(6,2))

        self.area_x_var=tk.StringVar(value="1000")
        self.area_y_var=tk.StringVar(value="600")
        self.vel_max_var=tk.StringVar(value="4000")
        self.vel_min_var=tk.StringVar(value="200")
        self.acc_var=tk.StringVar(value="500")
        self.mat_w_var=tk.StringVar(value="800")
        self.mat_h_var=tk.StringVar(value="500")

        def param_row(label, var, unit):
            r=tk.Frame(form, bg=BG_PANEL); r.pack(fill="x", pady=2)
            tk.Label(r, text=label, fg="#ccc", bg=BG_PANEL, font=("Segoe UI",7), width=6, anchor="w").pack(side="left")
            e=tk.Entry(r, textvariable=var, bg=BG_INPUT, fg="white", bd=1, relief="solid", font=("Consolas",8), insertbackground="white")
            e.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(r, text=unit, fg="#666", bg=BG_PANEL, font=("Segoe UI",7)).pack(side="left")

        param_row("X:", self.area_x_var, "mm")
        param_row("Y:", self.area_y_var, "mm")

        tk.Label(form, text="Velocidad", fg="white", bg=BG_PANEL, font=("Segoe UI",8,"bold")).pack(anchor="w", pady=(8,2))
        param_row("Máx:", self.vel_max_var, "mm/min")
        param_row("Mín:", self.vel_min_var, "mm/min")
        param_row("Acelerac:", self.acc_var, "mm/s²")

        tk.Label(form, text="Dimensiones Material", fg="white", bg=BG_PANEL, font=("Segoe UI",8,"bold")).pack(anchor="w", pady=(8,2))
        param_row("Ancho:", self.mat_w_var, "mm")
        param_row("Largo:", self.mat_h_var, "mm")

        tk.Button(left, text="Abrir Configuración Avanzada", bg=BG_INPUT, fg=NEON, bd=1, relief="solid", font=("Segoe UI",7,"bold"), command=self.open_advanced).pack(fill="x", padx=10, pady=12, side="bottom")

        # RIGHT PANEL
        right=tk.Frame(main_pane, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        # Toolbar preview
        toolb=tk.Frame(right, bg=BG_DARK, height=32)
        toolb.pack(fill="x")
        toolb.pack_propagate(False)
        tk.Label(toolb, text="◍ Previsualización — Trayectoria G-code (Tiempo Real)", fg=NEON, bg=BG_DARK, font=("Segoe UI",8,"bold")).pack(side="left", padx=10)

        def small_btn(txt, cmd=None, green=False):
            bgc=BG_PANEL if not green else "#0f1a00"
            fgc=NEON if green else "white"
            b=tk.Button(toolb, text=txt, bg=bgc, fg=fgc, bd=1, relief="solid", font=("Segoe UI",7,"bold"), padx=6, command=cmd)
            b.pack(side="right", padx=2, pady=4)
            return b

        small_btn("↺ Reset", self.do_reset)
        small_btn("❚❚ Pausa", self.do_pausa)
        small_btn("▶ Iniciar", self.do_iniciar)
        small_btn("CONTORNO / FRAME", self.do_frame, green=True)
        small_btn("RECORRIDO", self.do_recorrido, green=True)

        # Canvas
        self.preview=GCodePreview(right)
        self.preview.pack(fill="both", expand=True, padx=6, pady=4)

        # Leyenda
        legend=tk.Frame(right, bg=BG_DARK, highlightbackground=NEON_DIM, highlightthickness=1)
        legend.place(relx=0.85, rely=0.85, anchor="center")
        tk.Label(legend, text="Leyenda:", fg=NEON, bg=BG_DARK, font=("Segoe UI",7,"bold"), anchor="w").pack(anchor="w", padx=6, pady=(4,0))
        tk.Label(legend, text="— Trayectoria programada", fg="#aaa", bg=BG_DARK, font=("Segoe UI",7)).pack(anchor="w", padx=6)
        tk.Label(legend, text="— Recorrido actual", fg=NEON, bg=BG_DARK, font=("Segoe UI",7)).pack(anchor="w", padx=6)
        tk.Label(legend, text="● Posición actual", fg="#00ffcc", bg=BG_DARK, font=("Segoe UI",7)).pack(anchor="w", padx=6, pady=(0,4))

        # Barra progreso verde
        prog_frame=tk.Frame(right, bg=BG_DARK, height=8)
        prog_frame.pack(fill="x", padx=6, pady=2)
        prog_frame.pack_propagate(False)
        self.prog_canvas=tk.Canvas(prog_frame, bg="#0a0a0a", highlightthickness=0, height=8)
        self.prog_canvas.pack(fill="both", expand=True)

        # Bottom status
        bottom=tk.Frame(root, bg="#111115", height=26)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        self.status_label=tk.Label(bottom, text="Estado: EN FUNCIONAMIENTO | Coordenadas: X: 120.45 Y: 80.20 Z: -5.00 | Progreso: 42% | Líneas: 218/520 | Tiempo: 00:12:34 | Feed: 1200 mm/min | Consumo: 1.8A 25.3°C", fg=NEON, bg="#111115", font=("Consolas",7))
        self.status_label.pack(side="left", padx=8)

        # cargar demo tipo tu foto (pieza irregular)
        self.load_demo_brazo()

    def log(self, msg):
        print(msg)

    def load_demo_brazo(self):
        # genera una pieza parecida a tu foto (brazo mecánico)
        g="""G0 X100 Y100
G1 X200 Y120
G1 X400 Y180
G1 X600 Y250
G1 X850 Y320
G1 X900 Y340
G1 X910 Y350
G1 X905 Y365
G1 X880 Y370
G1 X600 Y300
G1 X400 Y240
G1 X150 Y150
G0 X500 Y50
G1 X520 Y60
G1 X540 Y80
G1 X530 Y110
G1 X500 Y115
"""
        self.gcode_text=g
        self.preview.load_gcode(g)

    def get_step(self):
        try: return float(self.step_var.get().split()[0])
        except: return 1.0

    def jog(self, axis, dir):
        step=self.get_step()*dir
        feed=self.vel_max_var.get()
        self.fluid.jog(axis, step, feed)
        self.log(f"Jog {axis}{step}")

    def do_recorrido(self):
        self.fluid.thc_off()
        self.fluid.torch_off_cmd()
        self.log("RECORRIDO dry run")

    def do_frame(self):
        try:
            w=float(self.mat_w_var.get()); h=float(self.mat_h_var.get())
            g=f"G0 X0 Y0\nG1 X{w} Y0 F{self.vel_max_var.get()}\nG1 X{w} Y{h}\nG1 X0 Y{h}\nG1 X0 Y0\n"
            self.log(f"FRAME {w}x{h}")
        except: pass

    def do_iniciar(self):
        self.log("INICIAR")

    def do_pausa(self):
        self.fluid.hold()

    def do_reset(self):
        self.fluid.torch_off_cmd()
        self.fluid.reset()

    def open_advanced(self):
        messagebox.showinfo("Avanzado", "THC: ON\nIHS: G38.2\nArc OK: Input 32\nTorch Relay: GPIO 26\nSoft Limits: ON\nHoming: $H")

    def toggle_connect(self):
        if self.fluid.connected:
            self.fluid.disconnect()
            self.conn_label.config(text="● DESCONECTADO\n"+self.fluid.port, fg="#ff4444")
        else:
            # ABRE DIALOGO DE PUERTO - COMO PEDISTE
            dlg=PortDialog(self.root, self.fluid)
            self.root.wait_window(dlg.top)
            if dlg.result:
                port,baud=dlg.result
                ok,msg=self.fluid.connect(port,baud)
                if ok:
                    self.conn_label.config(text=f"● CONECTADO\n{port}", fg=NEON)
                else:
                    messagebox.showerror("Error Conexión", msg)
                    # reabrir dialogo si falla
                    self.toggle_connect()

    def open_file(self):
        path=filedialog.askopenfilename(filetypes=[("G-code","*.gcode *.nc *.tap"),("Todos","*.*")])
        if not path: return
        with open(path,'r') as f: g=f.read()
        self.gcode_text=g
        fw,fh,_,_=self.preview.load_gcode(g)
        try:
            mw=float(self.mat_w_var.get()); mh=float(self.mat_h_var.get())
        except:
            mw,mh=800,500
        if fw>mw or fh>mh:
            self.show_warning(fw,fh,mw,mh)

    def show_warning(self,fw,fh,mw,mh):
        # EXACTO A TU FOTO
        win=tk.Toplevel(self.root)
        win.title("Advertencia")
        win.geometry("420x200")
        win.configure(bg="#0a0a0a")
        win.transient(self.root)
        win.grab_set()
        win.update_idletasks()
        x=self.root.winfo_x()+(self.root.winfo_width()//2)-210
        y=self.root.winfo_y()+(self.root.winfo_height()//2)-100
        win.geometry(f"+{x}+{y}")

        top=tk.Frame(win, bg=YELLOW, height=38)
        top.pack(fill="x")
        tk.Label(top, text="⚠  Advertencia", bg=YELLOW, fg="black", font=("Segoe UI",11,"bold")).pack(side="left", padx=15, pady=6)

        body=tk.Frame(win, bg="#0a0a0a")
        body.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(body, text="Archivo mas grande que el material.", fg="white", bg="#0a0a0a", font=("Segoe UI",10), justify="center").pack(pady=(30,20))

        bf=tk.Frame(body, bg="#0a0a0a")
        bf.pack(pady=10)

        def cerrar(aceptar=False):
            win.destroy()
            if aceptar:
                try:
                    self.mat_w_var.set(str(int(fw+20)))
                    self.mat_h_var.set(str(int(fh+20)))
                    self.preview.set_material(fw+20, fh+20)
                except: pass

        tk.Button(bf, text="Cancelar", bg="#1a1a1a", fg="white", width=14, bd=1, relief="solid", font=("Segoe UI",9), command=lambda: cerrar(False)).pack(side="left", padx=10)
        tk.Button(bf, text="Aceptar", bg=YELLOW, fg="black", width=14, bd=0, font=("Segoe UI",9,"bold"), command=lambda: cerrar(True)).pack(side="left", padx=10)

if __name__=="__main__":
    root=tk.Tk()
    app=DavierPlasmaV33(root)
    # menu abrir archivo
    menubar=tk.Menu(root)
    filemenu=tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Abrir G-code", command=app.open_file)
    menubar.add_cascade(label="Archivo", menu=filemenu)
    root.config(menu=menubar)
    root.mainloop()
