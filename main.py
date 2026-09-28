"""
DAVIER NC PLASMA V3.3 - FINAL FIX - LOGO + SELECTOR PUERTO + GCODE LOAD
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re, threading, time, math, os, sys
from datetime import datetime
from collections import deque
from pathlib import Path

def resource_path(relative):
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
    def __init__(self, log_callback=None, log_cb=None, **kwargs):
        # ACEPTA ambos nombres para evitar el error de tu foto
        self.log_cb = log_callback or log_cb
        self.ser = None
        self.connected = False
        self.port = "COM3"
        self.baud = 115200
        self.status = {"state": "IDLE", "x": 0, "y": 0, "z": 0, "feed": 0, "line": 0}
        self.running = False
        self.rx = deque(maxlen=200)
        self.thc_enabled = True
        self.thc_voltage = 0
        self.arc_ok = False
        self.torch_on = False

    def log(self, msg):
        if self.log_cb: 
            try:
                self.log_cb(msg)
            except:
                pass
        print(msg)

    def list_ports(self):
        if not HAS_SERIAL:
            return [f"COM{i}" for i in range(1,11)]
        try:
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports] if ports else ["COM3", "COM4", "COM5"]
        except:
            return ["COM3", "COM4", "COM5"]

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
        frame_baud = tk.Frame(self.top, bg=BG_PANEL)
        frame_baud.pack(fill="x", padx=20, pady=8)
        tk.Label(frame_baud, text="Baudrate:", bg=BG_PANEL, fg="white", font=("Segoe UI",9)).pack(side="left")
        self.baud_var = tk.StringVar(value="115200")
        baud_combo = ttk.Combobox(frame_baud, textvariable=self.baud_var, values=["9600","19200","38400","57600","115200","250000"], width=12, state="readonly")
        baud_combo.pack(side="right")
        bf = tk.Frame(self.top, bg=BG_PANEL)
        bf.pack(fill="x", padx=20, pady=12)
        def on_connect():
            sel = self.listbox.curselection()
            if not sel:
                messagebox.showwarning("Selecciona puerto", "Selecciona un puerto COM")
                return
            port = self.listbox.get(sel[0])
            try:
                baud = int(self.baud_var.get())
            except:
                baud = 115200
            self.result = (port, baud)
            self.top.destroy()
        tk.Button(bf, text="Cancelar", bg="#1a1a1a", fg="white", width=12, command=self.top.destroy).pack(side="left")
        tk.Button(bf, text="Conectar", bg=NEON, fg="black", width=12, font=("Segoe UI",9,"bold"), command=on_connect).pack(side="right")

class GCodePreview(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_DARK, highlightthickness=0, **kwargs)
        self.gcode_lines = []
        self.area_w = 800
        self.area_h = 500
        self.current_pos = (0,0)
        self.bind("<Configure>", lambda e: self.redraw())
    def set_material(self, w, h):
        self.area_w = w
        self.area_h = h
        self.redraw()
    def load_gcode(self, text):
        self.gcode_lines = []
        x,y = 0,0
        min_x=min_y=float('inf')
        max_x=max_y=float('-inf')
        for line in text.splitlines():
            line=line.strip().upper()
            if not line or line.startswith("(") or line.startswith(";"):
                continue
            mx=re.search(r'X([-\d.]+)',line)
            my=re.search(r'Y([-\d.]+)',line)
            if mx: x=float(mx.group(1))
            if my: y=float(my.group(1))
            self.gcode_lines.append((x,y))
            min_x=min(min_x,x); max_x=max(max_x,x)
            min_y=min(min_y,y); max_y=max(max_y,y)
        self.redraw()
        if min_x!=float('inf'):
            return (max_x-min_x, max_y-min_y, min_x, min_y)
        return (0,0,0,0)
    def redraw(self):
        self.delete("all")
        w=self.winfo_width() or 800
        h=self.winfo_height() or 600
        for i in range(0,w,40):
            self.create_line(i,0,i,h, fill=GRID_LINE, dash=(2,4))
        for i in range(0,h,40):
            self.create_line(0,i,w,i, fill=GRID_LINE, dash=(2,4))
        scale_x=(w-100)/max(self.area_w,1)
        scale_y=(h-100)/max(self.area_h,1)
        scale=min(scale_x, scale_y)*0.9
        if len(self.gcode_lines)>1:
            pts=[]
            for x,y in self.gcode_lines:
                pts.extend([50+x*scale, h-50-y*scale])
            if len(pts)>=4:
                self.create_line(pts, fill=NEON, width=2)
        cx, cy = self.current_pos
        px = 50+cx*scale
        py = h-50-cy*scale
        self.create_oval(px-5, py-5, px+5, py+5, fill="#00ffaa", outline="")

class DavierPlasmaV33:
    def __init__(self, root):
        self.root=root
        self.root.title("DAVIER NC PLASMA V3.3 - CNC Plasma Control")
        self.root.geometry("1280x760")
        self.root.configure(bg=BG_MAIN)
        icon_path = get_icon_path()
        if icon_path and icon_path.endswith(".ico") and os.path.exists(icon_path):
            try: self.root.iconbitmap(icon_path)
            except: pass
        self.fluid=FluidNC(log_callback=self.log)
        self.gcode_text=""
        self.step_var=tk.StringVar(value="1.00 mm")
        self.area_x_var=tk.StringVar(value="1000")
        self.area_y_var=tk.StringVar(value="600")
        self.vel_max_var=tk.StringVar(value="4000")
        self.vel_min_var=tk.StringVar(value="200")
        self.acc_var=tk.StringVar(value="500")
        self.mat_w_var=tk.StringVar(value="800")
        self.mat_h_var=tk.StringVar(value="500")
        self.build_ui()
    def build_ui(self):
        top=tk.Frame(self.root, bg="#111115", height=70)
        top.pack(fill="x")
        top.pack_propagate(False)
        title_frame=tk.Frame(top, bg="#111115")
        title_frame.pack(side="left", padx=20, pady=10)
        # Logo
        logo_path = get_icon_path()
        if logo_path and os.path.exists(logo_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(logo_path)
                img = img.resize((48,48))
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(title_frame, image=self.logo_img, bg="#111115").pack(side="left", padx=(0,12))
            except:
                pass
        tk.Label(title_frame, text="DAVIER NC PLASMA V3.3", bg="#111115", fg=NEON, font=("Segoe UI", 18, "bold")).pack(side="left")
        main=tk.Frame(self.root, bg=BG_MAIN)
        main.pack(fill="both", expand=True)
        left=tk.Frame(main, bg=BG_PANEL, width=280)
        left.pack(side="left", fill="y", padx=6, pady=6)
        left.pack_propagate(False)
        conn_frame=tk.Frame(left, bg=BG_PANEL, highlightbackground=NEON_DIM, highlightthickness=1)
        conn_frame.pack(fill="x", padx=6, pady=6)
        tk.Label(conn_frame, text="ESTADO DE CONEXIÓN", bg=BG_PANEL, fg=NEON, font=("Segoe UI",8,"bold")).pack(anchor="w", padx=8, pady=(6,2))
        self.conn_label=tk.Label(conn_frame, text="● DESCONECTADO\nCOM3", bg=BG_PANEL, fg="#ff4444", font=("Segoe UI",9,"bold"), justify="left")
        self.conn_label.pack(anchor="w", padx=8, pady=2)
        tk.Button(conn_frame, text="Conectar / Cambiar Puerto", bg=BG_INPUT, fg="white", bd=1, relief="solid", font=("Segoe UI",8), command=self.toggle_connect).pack(fill="x", padx=8, pady=6)
        jog_frame=tk.Frame(left, bg=BG_PANEL, highlightbackground=NEON_DIM, highlightthickness=1)
        jog_frame.pack(fill="x", padx=6, pady=6)
        tk.Label(jog_frame, text="CONTROLES DE JOG", bg=BG_PANEL, fg=NEON, font=("Segoe UI",8,"bold")).pack(anchor="w", padx=8, pady=4)
        step_row=tk.Frame(jog_frame, bg=BG_PANEL)
        step_row.pack(fill="x", padx=8, pady=4)
        tk.Label(step_row, text="Paso:", bg=BG_PANEL, fg="white", font=("Segoe UI",8)).pack(side="left")
        step_combo=ttk.Combobox(step_row, textvariable=self.step_var, values=["0.10 mm","1.00 mm","10.00 mm","50.00 mm"], width=10, state="readonly")
        step_combo.pack(side="right")
        pad=tk.Frame(jog_frame, bg=BG_PANEL)
        pad.pack(pady=6)
        tk.Button(pad, text="Y+", width=6, bg=BG_INPUT, fg=NEON, command=lambda: self.jog("Y",1)).grid(row=0,column=1, padx=4, pady=2)
        tk.Button(pad, text="X-", width=6, bg=BG_INPUT, fg=NEON, command=lambda: self.jog("X",-1)).grid(row=1,column=0, padx=4, pady=2)
        tk.Button(pad, text="HOME", width=6, bg=YELLOW, fg="black", command=self.fluid.home).grid(row=1,column=1, padx=4, pady=2)
        tk.Button(pad, text="X+", width=6, bg=BG_INPUT, fg=NEON, command=lambda: self.jog("X",1)).grid(row=1,column=2, padx=4, pady=2)
        tk.Button(pad, text="Y-", width=6, bg=BG_INPUT, fg=NEON, command=lambda: self.jog("Y",-1)).grid(row=2,column=1, padx=4, pady=2)
        mat_frame=tk.Frame(left, bg=BG_PANEL, highlightbackground=NEON_DIM, highlightthickness=1)
        mat_frame.pack(fill="x", padx=6, pady=6)
        tk.Label(mat_frame, text="MATERIAL", bg=BG_PANEL, fg=NEON, font=("Segoe UI",8,"bold")).pack(anchor="w", padx=8, pady=4)
        for lbl,var in [("Ancho:", self.mat_w_var), ("Alto:", self.mat_h_var)]:
            r=tk.Frame(mat_frame, bg=BG_PANEL)
            r.pack(fill="x", padx=8, pady=2)
            tk.Label(r, text=lbl, bg=BG_PANEL, fg="white", font=("Segoe UI",8), width=8, anchor="w").pack(side="left")
            tk.Entry(r, textvariable=var, bg=BG_INPUT, fg="white", width=10, bd=1, relief="solid").pack(side="right")
        act_frame=tk.Frame(left, bg=BG_PANEL)
        act_frame.pack(fill="x", padx=6, pady=10)
        tk.Button(act_frame, text="RECORRIDO (Dry)", bg="#1a1a1a", fg="white", bd=1, relief="solid", command=self.do_recorrido).pack(fill="x", pady=2)
        tk.Button(act_frame, text="FRAME", bg="#1a1a1a", fg="white", bd=1, relief="solid", command=self.do_frame).pack(fill="x", pady=2)
        tk.Button(act_frame, text="INICIAR", bg=YELLOW, fg="black", font=("Segoe UI",9,"bold"), bd=0, command=self.do_iniciar).pack(fill="x", pady=4)
        tk.Button(act_frame, text="PAUSA / HOLD", bg="#333", fg="white", command=self.do_pausa).pack(fill="x", pady=2)
        tk.Button(act_frame, text="RESET", bg="#661111", fg="white", command=self.do_reset).pack(fill="x", pady=2)
        right=tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True, padx=(0,6), pady=6)
        self.preview=GCodePreview(right)
        self.preview.pack(fill="both", expand=True, padx=6, pady=4)
        bottom=tk.Frame(self.root, bg="#111115", height=26)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        self.status_label=tk.Label(bottom, text="Listo - Carga un G-code desde Archivo > Abrir G-code", fg=NEON, bg="#111115", font=("Consolas",8))
        self.status_label.pack(side="left", padx=8)
        self.load_demo_brazo()
    def log(self, msg):
        print(msg)
        try:
            self.status_label.config(text=msg[:120])
        except: pass
    def load_demo_brazo(self):
        g="""G0 X100 Y100
G1 X200 Y120
G1 X400 Y180
G1 X600 Y250
G1 X850 Y320
G1 X900 Y340
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
    def toggle_connect(self):
        if self.fluid.connected:
            self.fluid.disconnect()
            self.conn_label.config(text="● DESCONECTADO\n"+self.fluid.port, fg="#ff4444")
        else:
            dlg=PortDialog(self.root, self.fluid)
            self.root.wait_window(dlg.top)
            if dlg.result:
                port,baud=dlg.result
                ok,msg=self.fluid.connect(port,baud)
                if ok:
                    self.conn_label.config(text=f"● CONECTADO\n{port}", fg=NEON)
                else:
                    messagebox.showerror("Error Conexión", msg)
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
        self.log(f"G-code cargado: {path} - {len(g)} bytes")
    def show_warning(self,fw,fh,mw,mh):
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
    menubar=tk.Menu(root)
    filemenu=tk.Menu(menubar, tearoff=0)
    filemenu.add_command(label="Abrir G-code", command=app.open_file)
    filemenu.add_separator()
    filemenu.add_command(label="Salir", command=root.quit)
    menubar.add_cascade(label="Archivo", menu=filemenu)
    root.config(menu=menubar)
    root.mainloop()
