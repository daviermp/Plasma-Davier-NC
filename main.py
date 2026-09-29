
"""
DAVIER NC PLASMA V3.5 - FINAL COMPLETA
- Rejillas + Reglas en cm visibles
- Área máquina + material editables y visibles en visor
- Visor con auto-ajuste, zoom con ruedita, arrastre con click derecho
- Botón ABRIR G-CODE grande
- Panel izquierdo con scroll para pantallas 1024x600
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re, threading, time, os, sys
from collections import deque

def resource_path(rel):
    try: base = sys._MEIPASS
    except: base = os.path.abspath(".")
    return os.path.join(base, rel)

def get_icon_path():
    for n in ["davier_icon.ico","davier_logo_transparent.png","davier_icon_256.png"]:
        p=resource_path(n)
        if os.path.exists(p): return p
        if os.path.exists(n): return n
    return None

try:
    import serial, serial.tools.list_ports
    HAS_SERIAL=True
except: HAS_SERIAL=False

BG_MAIN="#0f0f14"; BG_PANEL="#17171f"; BG_DARK="#0a0a0f"; BG_INPUT="#1e1e28"
NEON="#8cff00"; NEON_DIM="#3a5a00"; GRID_MINOR="#162016"; GRID_MAJOR="#223422"
YELLOW="#ffcc00"; RED="#ff4444"

class FluidNC:
    def __init__(self, log_callback=None, log_cb=None, **k):
        self.log_cb=log_callback or log_cb
        self.ser=None; self.connected=False; self.port="COM3"; self.baud=115200
        self.status={"x":0,"y":0,"z":0}; self.running=False; self.rx=deque(maxlen=200)
    def log(self,m):
        if self.log_cb:
            try: self.log_cb(m)
            except: pass
    def list_ports(self):
        if not HAS_SERIAL: return [f"COM{i}" for i in range(1,11)]
        try:
            p=serial.tools.list_ports.comports()
            return [x.device for x in p] if p else ["COM3","COM4"]
        except: return ["COM3","COM4"]
    def connect(self,port,baud=115200):
        self.port=port; self.baud=baud
        if not HAS_SERIAL:
            self.connected=True; self.running=True
            return True,f"SIM {port}"
        try:
            self.ser=serial.Serial(port,baud,timeout=0.2)
            time.sleep(1.5); self.ser.write(b"\x18"); time.sleep(0.5)
            self.ser.reset_input_buffer()
            self.connected=True; self.running=True
            threading.Thread(target=self._listen,daemon=True).start()
            return True,f"Conectado {port}"
        except Exception as e: return False,str(e)
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
                    l=self.ser.readline().decode(errors='ignore').strip()
                    if l.startswith("<"):
                        m=re.search(r'MPos:([-\d.]+),([-\d.]+),([-\d.]+)',l)
                        if m: self.status["x"]=float(m.group(1)); self.status["y"]=float(m.group(2)); self.status["z"]=float(m.group(3))
            except: pass
            time.sleep(0.05)
    def send(self,c):
        if not self.connected: self.log(f"[OFF] {c}"); return False
        if HAS_SERIAL and self.ser:
            try: self.ser.write(f"{c}\n".encode()); self.log(f"> {c}"); return True
            except Exception as e: self.log(str(e)); return False
        else: self.log(f"[SIM] {c}"); return True
    def jog(self,a,d,f=4000): return self.send(f"$J=G91 G21 {a}{d} F{f}")
    def home(self): return self.send("$H")
    def reset(self): return self.send("\x18")
    def hold(self): return self.send("!")
    def resume(self): return self.send("~")

class PortDialog:
    def __init__(self,parent,fluid):
        self.fluid=fluid; self.result=None
        self.top=tk.Toplevel(parent); self.top.title("Puerto"); self.top.geometry("380x320"); self.top.configure(bg=BG_PANEL); self.top.transient(parent); self.top.grab_set()
        tk.Label(self.top,text="⚡ Seleccionar Puerto COM",bg=BG_PANEL,fg=NEON,font=("Segoe UI",11,"bold")).pack(pady=10)
        self.lb=tk.Listbox(self.top,bg=BG_INPUT,fg="white",selectbackground=NEON,selectforeground="black",font=("Consolas",10),height=8)
        self.lb.pack(fill="both",padx=20,pady=5,expand=True)
        for p in fluid.list_ports(): self.lb.insert("end",p)
        if fluid.list_ports(): self.lb.select_set(0)
        f=tk.Frame(self.top,bg=BG_PANEL); f.pack(fill="x",padx=20,pady=6)
        tk.Label(f,text="Baud:",bg=BG_PANEL,fg="white").pack(side="left")
        self.baud=tk.StringVar(value="115200")
        ttk.Combobox(f,textvariable=self.baud,values=["9600","57600","115200","250000"],width=10,state="readonly").pack(side="right")
        bf=tk.Frame(self.top,bg=BG_PANEL); bf.pack(fill="x",padx=20,pady=10)
        def go():
            s=self.lb.curselection()
            if not s: return
            self.result=(self.lb.get(s[0]),int(self.baud.get())); self.top.destroy()
        tk.Button(bf,text="Cancelar",command=self.top.destroy).pack(side="left")
        tk.Button(bf,text="Conectar",bg=NEON,fg="black",font=("Segoe UI",9,"bold"),command=go).pack(side="right")

class GCodePreview(tk.Frame):
    def __init__(self,parent,**k):
        super().__init__(parent,bg=BG_DARK)
        # Estado
        self.gcode=[]; self.mat_w=800; self.mat_h=500; self.maq_w=1220; self.maq_h=2440
        self.scale=0.5; self.off_x=80; self.off_y=80; self.drag_start=None
        self.show_grid=True
        self.bbox=(0,0,0,0)
        # Rulers
        self.ruler_h=22; self.ruler_v=30
        self.top_ruler=tk.Canvas(self,bg="#121212",height=self.ruler_h,highlightthickness=0)
        self.top_ruler.grid(row=0,column=1,sticky="ew")
        self.left_ruler=tk.Canvas(self,bg="#121212",width=self.ruler_v,highlightthickness=0)
        self.left_ruler.grid(row=1,column=0,sticky="ns")
        self.corner=tk.Canvas(self,bg="#121212",width=self.ruler_v,height=self.ruler_h,highlightthickness=0)
        self.corner.grid(row=0,column=0)
        self.canvas=tk.Canvas(self,bg=BG_DARK,highlightthickness=0)
        self.canvas.grid(row=1,column=1,sticky="nsew")
        self.grid_rowconfigure(1,weight=1); self.grid_columnconfigure(1,weight=1)
        # Toolbar visor
        tb=tk.Frame(self,bg="#111115",height=28); tb.grid(row=2,column=0,columnspan=2,sticky="ew")
        tk.Button(tb,text="Ajustar Vista",bg=BG_INPUT,fg=NEON,font=("Segoe UI",7),bd=0,command=self.fit_view).pack(side="left",padx=4,pady=2)
        tk.Button(tb,text="100%",bg=BG_INPUT,fg="white",font=("Segoe UI",7),bd=0,command=self.zoom_100).pack(side="left",padx=2)
        tk.Button(tb,text="🔍+ ",bg=BG_INPUT,fg="white",font=("Segoe UI",7),bd=0,command=lambda: self.zoom_factor(1.25)).pack(side="left",padx=2)
        tk.Button(tb,text="🔍- ",bg=BG_INPUT,fg="white",font=("Segoe UI",7),bd=0,command=lambda: self.zoom_factor(0.8)).pack(side="left",padx=2)
        self.grid_var=tk.BooleanVar(value=True)
        tk.Checkbutton(tb,text="Rejilla",variable=self.grid_var,bg="#111115",fg=NEON,selectcolor=BG_DARK,activebackground="#111115",command=self.toggle_grid).pack(side="left",padx=8)
        self.info_lbl=tk.Label(tb,text="Escala: 100% | X:0 Y:0",bg="#111115",fg="#888",font=("Consolas",7)); self.info_lbl.pack(side="right",padx=10)
        # Bindings
        self.canvas.bind("<Configure>",lambda e: self.redraw())
        self.canvas.bind("<ButtonPress-1>",self.on_drag_start)
        self.canvas.bind("<B1-Motion>",self.on_drag_move)
        self.canvas.bind("<MouseWheel>",self.on_wheel)
        self.canvas.bind("<Button-4>",lambda e: self.zoom_factor(1.1))
        self.canvas.bind("<Button-5>",lambda e: self.zoom_factor(0.9))
        self.canvas.bind("<Motion>",self.on_mouse_move)

    def set_material(self,w,h):
        self.mat_w=w; self.mat_h=h; self.fit_view()
    def set_machine(self,w,h):
        self.maq_w=w; self.maq_h=h; self.redraw()

    def load_gcode(self,text):
        self.gcode=[]; x=y=0; min_x=min_y=float('inf'); max_x=max_y=float('-inf')
        for line in text.splitlines():
            ls=line.strip().upper()
            if not ls or ls[0] in "(;": continue
            mx=re.search(r'X([-\d.]+)',ls); my=re.search(r'Y([-\d.]+)',ls)
            if mx: x=float(mx.group(1))
            if my: y=float(my.group(1))
            self.gcode.append((x,y))
            min_x=min(min_x,x); max_x=max(max_x,x); min_y=min(min_y,y); max_y=max(max_y,y)
        if min_x!=float('inf'):
            self.bbox=(min_x,min_y,max_x,max_y)
            self.fit_view()
            return (max_x-min_x, max_y-min_y, min_x, min_y)
        self.bbox=(0,0,0,0)
        return (0,0,0,0)

    def fit_view(self):
        w=self.canvas.winfo_width() or 800; h=self.canvas.winfo_height() or 600
        if not self.gcode:
            # fit to machine
            fw=self.maq_w; fh=self.maq_h
        else:
            min_x,min_y,max_x,max_y=self.bbox
            fw=max(max_x-min_x, self.mat_w, 100); fh=max(max_y-min_y, self.mat_h, 100)
            # centrar
        sx=(w-100)/max(fw,1); sy=(h-100)/max(fh,1)
        self.scale=min(sx,sy)*0.85
        # centrar origen
        self.off_x=60 - (self.bbox[0] if self.gcode else 0)*self.scale
        self.off_y=h-60 + (self.bbox[1] if self.gcode else 0)*self.scale
        # si bbox negativo, ajustar
        if self.gcode:
            # dejar margen
            self.off_x+=20; self.off_y-=20
        self.redraw()

    def zoom_100(self):
        self.scale=0.5; self.redraw()
    def zoom_factor(self,f, cx=None, cy=None):
        if cx is None:
            w=self.canvas.winfo_width() or 800; h=self.canvas.winfo_height() or 600
            cx=w//2; cy=h//2
        old=self.scale
        self.scale*=f
        self.scale=max(0.05,min(self.scale,10))
        # zoom hacia mouse
        self.off_x = cx - (cx - self.off_x)*(self.scale/old)
        self.off_y = cy - (cy - self.off_y)*(self.scale/old)
        self.redraw()
    def on_wheel(self,e):
        f=1.2 if e.delta>0 else 0.8
        self.zoom_factor(f, e.x, e.y)
    def on_drag_start(self,e): self.drag_start=(e.x,e.y,self.off_x,self.off_y)
    def on_drag_move(self,e):
        if self.drag_start:
            dx=e.x-self.drag_start[0]; dy=e.y-self.drag_start[1]
            self.off_x=self.drag_start[2]+dx; self.off_y=self.drag_start[3]+dy
            self.redraw()
    def on_mouse_move(self,e):
        wx=(e.x-self.off_x)/max(self.scale,0.001)
        wy=(self.off_y-e.y)/max(self.scale,0.001)
        self.info_lbl.config(text=f"X:{wx:.0f} Y:{wy:.0f} mm | Escala:{self.scale*100:.0f}% | Arrastra para mover, ruedita para zoom")

    def world_to_screen(self,x,y):
        sx=self.off_x + x*self.scale
        sy=self.off_y - y*self.scale
        return sx,sy

    def toggle_grid(self): self.show_grid=self.grid_var.get(); self.redraw()

    def redraw(self):
        self.canvas.delete("all"); self.top_ruler.delete("all"); self.left_ruler.delete("all")
        w=self.canvas.winfo_width() or 800; h=self.canvas.winfo_height() or 600
        # GRID
        if self.show_grid:
            # calcular inicio visible
            # lineas cada 10mm y 50mm
            min_wx=(0-self.off_x)/max(self.scale,0.001); max_wx=(w-self.off_x)/max(self.scale,0.001)
            min_wy=(self.off_y-h)/max(self.scale,0.001); max_wy=(self.off_y-0)/max(self.scale,0.001)
            # grid minor 10mm
            step_minor=10
            if self.scale<0.2: step_minor=100
            elif self.scale<0.5: step_minor=50
            # minor
            x=int(min_wx//step_minor)*step_minor
            while x<=max_wx:
                sx,_=self.world_to_screen(x,0)
                if sx>=0 and sx<=w:
                    self.canvas.create_line(sx,0,sx,h,fill=GRID_MINOR,dash=(1,3) if step_minor==10 else None)
                x+=step_minor
            y=int(min_wy//step_minor)*step_minor
            while y<=max_wy:
                _,sy=self.world_to_screen(0,y)
                if sy>=0 and sy<=h:
                    self.canvas.create_line(0,sy,w,sy,fill=GRID_MINOR,dash=(1,3) if step_minor==10 else None)
                y+=step_minor
            # major 100mm
            for x in range(int(min_wx//100)*100, int(max_wx)+1, 100):
                sx,_=self.world_to_screen(x,0)
                self.canvas.create_line(sx,0,sx,h,fill=GRID_MAJOR)
            for y in range(int(min_wy//100)*100, int(max_wy)+1, 100):
                _,sy=self.world_to_screen(0,y)
                self.canvas.create_line(0,sy,w,sy,fill=GRID_MAJOR)
        # MACHINE AREA - externo amarillo punteado
        x1,y1=self.world_to_screen(0,0)
        x2,y2=self.world_to_screen(self.maq_w,self.maq_h)
        self.canvas.create_rectangle(x1,y2,x2,y1,outline="#ffaa00",width=1,dash=(8,4))
        self.canvas.create_text(x1+6,y2+10,anchor="nw",text=f"ÁREA MÁQUINA {self.maq_w:.0f}x{self.maq_h:.0f} mm",fill="#ffaa00",font=("Segoe UI",7,"bold"))
        # MATERIAL AREA - verde solido
        mx1,my1=self.world_to_screen(0,0)
        mx2,my2=self.world_to_screen(self.mat_w,self.mat_h)
        self.canvas.create_rectangle(mx1,my2,mx2,my1,outline=NEON,width=2,fill="#8cff000d")
        self.canvas.create_text(mx1+6,my2+8,anchor="nw",text=f"MATERIAL {self.mat_w:.0f}x{self.mat_h:.0f}",fill=NEON,font=("Segoe UI",7,"bold"))
        # ORIGEN
        ox,oy=self.world_to_screen(0,0)
        self.canvas.create_line(ox-15,oy,ox+15,oy,fill="#ff4444",width=2)
        self.canvas.create_line(ox,oy-15,ox,oy+15,fill="#ff4444",width=2)
        self.canvas.create_text(ox+18,oy+4,text="0,0 ORIGEN",fill="#ff4444",font=("Segoe UI",7,"bold"))
        # GCODE
        if len(self.gcode)>1:
            pts=[]
            for x,y in self.gcode:
                sx,sy=self.world_to_screen(x,y)
                pts.extend([sx,sy])
            if len(pts)>=4:
                self.canvas.create_line(pts,fill=NEON,width=2,smooth=False)
            # inicio y fin
            if pts:
                self.canvas.create_oval(pts[0]-6,pts[1]-6,pts[0]+6,pts[1]+6,fill="#00ffaa",outline="white")
                self.canvas.create_text(pts[0],pts[1]-12,text="INICIO",fill="#00ffaa",font=("Segoe UI",7,"bold"))
        # RULERS
        # top ruler
        min_wx=(0-self.off_x)/max(self.scale,0.001); max_wx=(w-self.off_x)/max(self.scale,0.001)
        x=int(min_wx//50)*50
        while x<=max_wx:
            sx,_=self.world_to_screen(x,0)
            if 0<=sx<=w:
                hgt=12 if x%100==0 else 6
                self.top_ruler.create_line(sx,22,sx,22-hgt,fill="#888")
                if x%100==0:
                    self.top_ruler.create_text(sx,10,text=f"{int(x)}",fill="#aaa",font=("Consolas",7))
        # left ruler
        min_wy=(self.off_y-h)/max(self.scale,0.001); max_wy=(self.off_y-0)/max(self.scale,0.001)
        y=int(min_wy//50)*50
        while y<=max_wy:
            _,sy=self.world_to_screen(0,y)
            if 0<=sy<=h:
                wdt=12 if y%100==0 else 6
                self.left_ruler.create_line(30-wdt,sy,30,sy,fill="#888")
                if y%100==0:
                    self.left_ruler.create_text(12,sy,text=f"{int(y)}",fill="#aaa",font=("Consolas",7),angle=90)
            y+=50
        self.corner.create_text(15,11,text="mm",fill="#666",font=("Segoe UI",7))

class DavierPlasmaV35:
    def __init__(self,root):
        self.root=root
        self.root.title("DAVIER NC PLASMA V3.5 - CNC Plasma Control - CON REGLAS Y AREA MAQUINA")
        self.root.geometry("1360x740")
        self.root.minsize(1024,600)
        self.root.configure(bg=BG_MAIN)
        ip=get_icon_path()
        if ip and ip.endswith(".ico") and os.path.exists(ip):
            try: self.root.iconbitmap(ip)
            except: pass
        self.fluid=FluidNC(log_callback=self.log)
        self.step_var=tk.StringVar(value="1.00 mm")
        self.mat_w_var=tk.StringVar(value="800"); self.mat_h_var=tk.StringVar(value="500")
        self.maq_w_var=tk.StringVar(value="1220"); self.maq_h_var=tk.StringVar(value="2440")
        self.vel_max_var=tk.StringVar(value="4000"); self.vel_min_var=tk.StringVar(value="500"); self.acc_var=tk.StringVar(value="300")
        self.gcode_path=tk.StringVar(value="Sin archivo")
        self.build_ui()
        self.load_demo()
    def build_ui(self):
        top=tk.Frame(self.root,bg="#111115",height=50); top.pack(fill="x"); top.pack_propagate(False)
        lf=tk.Frame(top,bg="#111115"); lf.pack(side="left",padx=12,pady=6)
        try:
            from PIL import Image, ImageTk
            ip=get_icon_path()
            if ip:
                im=Image.open(ip).resize((36,36))
                self.logo=ImageTk.PhotoImage(im)
                tk.Label(lf,image=self.logo,bg="#111115").pack(side="left",padx=(0,8))
        except: pass
        tk.Label(lf,text="DAVIER NC PLASMA V3.5",bg="#111115",fg=NEON,font=("Segoe UI",14,"bold")).pack(side="left")
        tk.Label(lf,text=" | Rejillas + Reglas + Área Máquina",bg="#111115",fg="#aaa",font=("Segoe UI",9)).pack(side="left",padx=8)
        tk.Button(top,text="📁 ABRIR G-CODE",bg=YELLOW,fg="black",font=("Segoe UI",10,"bold"),padx=16,pady=4,bd=0,command=self.open_file).pack(side="right",padx=12,pady=8)
        main=tk.Frame(self.root,bg=BG_MAIN); main.pack(fill="both",expand=True)
        # LEFT SCROLL
        left_container=tk.Frame(main,bg=BG_PANEL,width=310); left_container.pack(side="left",fill="y",padx=6,pady=6); left_container.pack_propagate(False)
        canvas=tk.Canvas(left_container,bg=BG_PANEL,highlightthickness=0)
        scrollbar=tk.Scrollbar(left_container,orient="vertical",command=canvas.yview)
        scrollable=tk.Frame(canvas,bg=BG_PANEL)
        scrollable.bind("<Configure>",lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0),window=scrollable,anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left",fill="both",expand=True); scrollbar.pack(side="right",fill="y")
        def _mw(e): canvas.yview_scroll(int(-1*(e.delta/120)),"units")
        canvas.bind_all("<MouseWheel>",_mw)
        # CONEX
        f=tk.Frame(scrollable,bg=BG_PANEL,highlightbackground=NEON_DIM,highlightthickness=1); f.pack(fill="x",padx=6,pady=4)
        tk.Label(f,text="ESTADO DE CONEXIÓN",bg=BG_PANEL,fg=NEON,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=6,pady=(4,2))
        self.conn_lbl=tk.Label(f,text="● DESCONECTADO\nCOM3",bg=BG_PANEL,fg=RED,font=("Segoe UI",9,"bold"),justify="left"); self.conn_lbl.pack(anchor="w",padx=6)
        tk.Button(f,text="Conectar / Cambiar Puerto",bg=BG_INPUT,fg="white",command=self.toggle_connect).pack(fill="x",padx=6,pady=4)
        # ARCHIVO
        f2=tk.Frame(scrollable,bg=BG_PANEL,highlightbackground=NEON_DIM,highlightthickness=1); f2.pack(fill="x",padx=6,pady=4)
        tk.Label(f2,text="ARCHIVO G-CODE",bg=BG_PANEL,fg=NEON,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=6,pady=2)
        tk.Label(f2,textvariable=self.gcode_path,bg=BG_PANEL,fg="#aaa",font=("Consolas",7),wraplength=260,justify="left").pack(anchor="w",padx=6,pady=2)
        tk.Button(f2,text="📁 Cargar Archivo",bg=BG_INPUT,fg=NEON,command=self.open_file).pack(fill="x",padx=6,pady=4)
        # JOG
        f3=tk.Frame(scrollable,bg=BG_PANEL,highlightbackground=NEON_DIM,highlightthickness=1); f3.pack(fill="x",padx=6,pady=4)
        tk.Label(f3,text="CONTROLES DE JOG",bg=BG_PANEL,fg=NEON,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=6,pady=2)
        r=tk.Frame(f3,bg=BG_PANEL); r.pack(fill="x",padx=6,pady=2)
        tk.Label(r,text="Paso:",bg=BG_PANEL,fg="white",font=("Segoe UI",8)).pack(side="left")
        ttk.Combobox(r,textvariable=self.step_var,values=["0.10 mm","1.00 mm","10 mm","50 mm"],width=10,state="readonly").pack(side="right")
        pad=tk.Frame(f3,bg=BG_PANEL); pad.pack(pady=4)
        tk.Button(pad,text="Y+",width=6,bg=BG_INPUT,fg=NEON,command=lambda: self.jog("Y",1)).grid(row=0,column=1,padx=2,pady=2)
        tk.Button(pad,text="X-",width=6,bg=BG_INPUT,fg=NEON,command=lambda: self.jog("X",-1)).grid(row=1,column=0,padx=2,pady=2)
        tk.Button(pad,text="HOME",width=6,bg=YELLOW,fg="black",command=self.fluid.home).grid(row=1,column=1,padx=2,pady=2)
        tk.Button(pad,text="X+",width=6,bg=BG_INPUT,fg=NEON,command=lambda: self.jog("X",1)).grid(row=1,column=2,padx=2,pady=2)
        tk.Button(pad,text="Y-",width=6,bg=BG_INPUT,fg=NEON,command=lambda: self.jog("Y",-1)).grid(row=2,column=1,padx=2,pady=2)
        # MATERIAL
        f4=tk.Frame(scrollable,bg=BG_PANEL,highlightbackground=NEON,highlightthickness=1); f4.pack(fill="x",padx=6,pady=4)
        tk.Label(f4,text="📏 MATERIAL (área de corte)",bg=BG_PANEL,fg=NEON,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=6,pady=2)
        for lbl,var in [("Ancho (mm):",self.mat_w_var),("Alto (mm):",self.mat_h_var)]:
            row=tk.Frame(f4,bg=BG_PANEL); row.pack(fill="x",padx=6,pady=1)
            tk.Label(row,text=lbl,bg=BG_PANEL,fg="white",font=("Segoe UI",8),width=12,anchor="w").pack(side="left")
            e=tk.Entry(row,textvariable=var,bg=BG_INPUT,fg="white",width=12); e.pack(side="right")
            e.bind("<Return>",lambda ev: self.update_areas())
        tk.Button(f4,text="Aplicar a Visor",bg=BG_INPUT,fg=NEON,font=("Segoe UI",7),command=self.update_areas).pack(fill="x",padx=6,pady=2)
        # MAQUINA - ESTO TE FALTABA
        f5=tk.Frame(scrollable,bg=BG_PANEL,highlightbackground="#ffaa00",highlightthickness=2); f5.pack(fill="x",padx=6,pady=8)
        tk.Label(f5,text="🏭 ÁREA DE TRABAJO MÁQUINA",bg=BG_PANEL,fg="#ffaa00",font=("Segoe UI",9,"bold")).pack(anchor="w",padx=6,pady=4)
        tk.Label(f5,text="Tamaño físico de tu mesa",bg=BG_PANEL,fg="#aaa",font=("Segoe UI",7)).pack(anchor="w",padx=6)
        for lbl,var in [("Ancho máquina:",self.maq_w_var),("Alto máquina:",self.maq_h_var)]:
            row=tk.Frame(f5,bg=BG_PANEL); row.pack(fill="x",padx=6,pady=2)
            tk.Label(row,text=lbl,bg=BG_PANEL,fg="white",font=("Segoe UI",8),width=14,anchor="w").pack(side="left")
            e=tk.Entry(row,textvariable=var,bg=BG_INPUT,fg="#ffaa00",width=12,font=("Segoe UI",9,"bold")); e.pack(side="right")
            e.bind("<Return>",lambda ev: self.update_areas())
        tk.Button(f5,text="Actualizar Área Máquina",bg="#ffaa00",fg="black",font=("Segoe UI",8,"bold"),command=self.update_areas).pack(fill="x",padx=6,pady=4)
        # CONFIG
        f6=tk.Frame(scrollable,bg=BG_PANEL,highlightbackground=NEON_DIM,highlightthickness=1); f6.pack(fill="x",padx=6,pady=4)
        tk.Label(f6,text="⚙ CONFIGURACIÓN",bg=BG_PANEL,fg=NEON,font=("Segoe UI",8,"bold")).pack(anchor="w",padx=6,pady=2)
        for lbl,var in [("Vel Max:",self.vel_max_var),("Vel Min:",self.vel_min_var),("Aceler:",self.acc_var)]:
            row=tk.Frame(f6,bg=BG_PANEL); row.pack(fill="x",padx=6,pady=1)
            tk.Label(row,text=lbl,bg=BG_PANEL,fg="white",font=("Segoe UI",8),width=10,anchor="w").pack(side="left")
            tk.Entry(row,textvariable=var,bg=BG_INPUT,fg="white",width=12).pack(side="right")
        # ACCIONES
        f7=tk.Frame(scrollable,bg=BG_PANEL); f7.pack(fill="x",padx=6,pady=8)
        tk.Button(f7,text="RECORRIDO (Dry)",bg="#1e1e28",fg="white",command=self.do_recorrido).pack(fill="x",pady=2)
        tk.Button(f7,text="FRAME (Borde)",bg="#1e1e28",fg="white",command=self.do_frame).pack(fill="x",pady=2)
        tk.Button(f7,text="▶ INICIAR CORTE",bg=YELLOW,fg="black",font=("Segoe UI",11,"bold"),pady=8,command=self.do_iniciar).pack(fill="x",pady=6)
        tk.Button(f7,text="PAUSA / HOLD",bg="#333",fg="white",command=self.do_pausa).pack(fill="x",pady=2)
        tk.Button(f7,text="RESET / ALARMA",bg="#661111",fg="white",command=self.do_reset).pack(fill="x",pady=2)

        # RIGHT PREVIEW
        self.preview=GCodePreview(main); self.preview.pack(side="left",fill="both",expand=True,padx=(0,6),pady=6)

        # BOTTOM
        bottom=tk.Frame(self.root,bg="#111115",height=32); bottom.pack(fill="x",side="bottom"); bottom.pack_propagate(False)
        self.status_lbl=tk.Label(bottom,text="Listo - Usa ruedita para zoom, arrastra con click para mover, botón Ajustar Vista",fg=NEON,bg="#111115",font=("Consolas",8))
        self.status_lbl.pack(side="left",padx=10,pady=4)
        self.coord_lbl=tk.Label(bottom,text="X:0 Y:0 | Material: 800x500 | Máquina: 1220x2440",fg="#aaa",bg="#111115",font=("Consolas",7))
        self.coord_lbl.pack(side="right",padx=10)

    def log(self,msg):
        try: self.status_lbl.config(text=msg[:110])
        except: pass
    def load_demo(self):
        g="G0 X100 Y100\nG1 X700 Y100\nG1 X700 Y400\nG1 X100 Y400\nG1 X100 Y100\n"
        self.preview.load_gcode(g)
        self.update_areas()
    def get_step(self):
        try: return float(self.step_var.get().split()[0])
        except: return 1.0
    def jog(self,a,d): self.fluid.jog(a,self.get_step()*d,self.vel_max_var.get()); self.log(f"Jog {a}{d}")
    def do_recorrido(self): self.log("RECORRIDO Dry - THC OFF")
    def do_frame(self): self.log(f"FRAME Material {self.mat_w_var.get()}x{self.mat_h_var.get()}")
    def do_iniciar(self): self.log("INICIAR CORTE")
    def do_pausa(self): self.fluid.hold()
    def do_reset(self): self.fluid.reset()
    def update_areas(self):
        try:
            mw=float(self.mat_w_var.get()); mh=float(self.mat_h_var.get())
            qmw=float(self.maq_w_var.get()); qmh=float(self.maq_h_var.get())
            self.preview.set_material(mw,mh)
            self.preview.set_machine(qmw,qmh)
            self.coord_lbl.config(text=f"X:0 Y:0 | Material: {mw:.0f}x{mh:.0f} | Máquina: {qmw:.0f}x{qmh:.0f}")
            self.log(f"Áreas actualizadas - Material {mw:.0f}x{mh:.0f} - Máquina {qmw:.0f}x{qmh:.0f}")
        except Exception as e: messagebox.showerror("Error",str(e))
    def toggle_connect(self):
        if self.fluid.connected:
            self.fluid.disconnect(); self.conn_lbl.config(text="● DESCONECTADO\n"+self.fluid.port,fg=RED)
        else:
            dlg=PortDialog(self.root,self.fluid); self.root.wait_window(dlg.top)
            if dlg.result:
                p,b=dlg.result; ok,msg=self.fluid.connect(p,b)
                if ok: self.conn_lbl.config(text=f"● CONECTADO\n{p}",fg=NEON)
                else: messagebox.showerror("Error",msg)
    def open_file(self):
        path=filedialog.askopenfilename(filetypes=[("G-code","*.gcode *.nc *.tap *.txt"),("Todos","*.*")])
        if not path: return
        with open(path,'r',errors='ignore') as f: g=f.read()
        fw,fh,_,_=self.preview.load_gcode(g)
        self.gcode_path.set(path.split("/")[-1])
        try: mw=float(self.mat_w_var.get()); mh=float(self.mat_h_var.get())
        except: mw=mh=800
        if fw>mw or fh>mh: self.show_warn(fw,fh,mw,mh)
        self.log(f"Cargado: {path.split('/')[-1]} ({len(g.splitlines())} lineas) {fw:.0f}x{fh:.0f}mm - Auto-ajustado a visor")
    def show_warn(self,fw,fh,mw,mh):
        win=tk.Toplevel(self.root); win.title("Advertencia"); win.geometry("440x200"); win.configure(bg="#0a0a0a"); win.transient(self.root); win.grab_set()
        tk.Frame(win,bg=YELLOW,height=36).pack(fill="x")
        tk.Label(win,text=f"Pieza {fw:.0f}x{fh:.0f} mm > Material {mw:.0f}x{mh:.0f} mm",bg="#0a0a0a",fg="white",font=("Segoe UI",10)).pack(pady=20)
        bf=tk.Frame(win,bg="#0a0a0a"); bf.pack()
        def close(ok=False):
            if ok:
                self.mat_w_var.set(str(int(fw+20))); self.mat_h_var.set(str(int(fh+20))); self.update_areas()
            win.destroy()
        tk.Button(bf,text="Cancelar",bg="#222",fg="white",width=12,command=lambda: close(False)).pack(side="left",padx=6)
        tk.Button(bf,text="Agrandar Material",bg=YELLOW,fg="black",width=16,command=lambda: close(True)).pack(side="left",padx=6)

if __name__=="__main__":
    root=tk.Tk()
    app=DavierPlasmaV35(root)
    root.mainloop()
