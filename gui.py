#!/usr/bin/env python3
"""
JARVIS GUI — Advanced Brain Interface
======================================
Full-screen / windowed frameless pygame UI with:
  • Animated neural-net brain (state-driven, 180 particles)
  • Live voice waveform visualiser
  • Wake-word detection ("hey jarvis")
  • Text-to-speech responses
  • Keyboard text-input fallback (just start typing)
  • Command history (↑ ↓ to recall)
  • Multiple HUD processing panels
  • F11 / F  = toggle fullscreen
  • ESC      = quit
"""

import threading, queue, sys, os, math, random, time, traceback, json, textwrap
from datetime import datetime
from collections import deque

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    import speech_recognition as sr
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", 160)
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False

try:
    import numpy as np
    import pyaudio
    WAVEFORM_AVAILABLE = True
except Exception:
    WAVEFORM_AVAILABLE = False

os.environ.setdefault("SDL_VIDEO_X11_VISUALID", "")
import pygame, pygame.gfxdraw

# ── JARVIS core ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_BOOT_ERRORS = []

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    _BOOT_ERRORS.append("Missing: python-dotenv  ->  pip install python-dotenv --break-system-packages")

try:
    from openai import OpenAI
except ImportError:
    _BOOT_ERRORS.append("Missing: openai  ->  pip install openai --break-system-packages")
    OpenAI = None

try:
    from core.registry  import PluginRegistry
    from core.validator import validate, ValidationError, ConfirmationRequired
except ImportError as e:
    _BOOT_ERRORS.append(f"Core module error: {e}")
    PluginRegistry = None
    def validate(d, **kw): return d
    class ValidationError(Exception): pass
    class ConfirmationRequired(Exception):
        def __init__(self, msg, decision=None):
            super().__init__(msg); self.decision = decision

_zai_key = os.getenv("ZAI_API_KEY", "")
_or_key  = os.getenv("OPENROUTER_API_KEY", "")
if _zai_key:
    _api_key, _base_url, _def_model = _zai_key, "https://api.z.ai/api/paas/v4", "glm-4.5-flash"
else:
    _api_key = _or_key or os.getenv("GROQ_API_KEY","")
    _base_url, _def_model = "https://openrouter.ai/api/v1", "mistralai/mistral-7b-instruct:free"

GROQ_MODEL = os.getenv("ZAI_MODEL", os.getenv("OPENROUTER_MODEL", os.getenv("GROQ_MODEL", _def_model)))
cwd  = os.getcwd()
HOME = os.path.expanduser("~")
try:
    client   = OpenAI(api_key=_api_key, base_url=_base_url) if OpenAI else None
    registry = PluginRegistry() if PluginRegistry else None
    if registry:
        registry.discover("plugins")
        registry.inject_ai(client, GROQ_MODEL)
except Exception as e:
    _BOOT_ERRORS.append(f"Init error: {e}")
    client = None; registry = None
conversation_history: list = []
WAKE_WORDS = ["hey jarvis","jarvis","ok jarvis"]

def get_system_prompt():
    return (
        f"You are JARVIS, a Linux automation assistant.\n"
        f"CWD: {cwd} | HOME: {HOME}\n\n"
        f"RULES:\n"
        f"  - Always use full absolute paths. Never use $HOME/$USER — use {HOME}\n"
        f"  - 'here','this folder','current dir' mean: {cwd}\n"
        f"  - To navigate: action=change_dir\n"
        f"  - To edit: action=edit_file with 'instruction'\n"
        f"  - To create: action=write_file\n"
        f"  - 'install X' → category=app, action=install_package, params={{\"package\":\"X\"}}\n\n"
        f"RESPONSE FORMAT — always return a JSON array, never empty:\n"
        f'  [{{"category":"...","action":"...","params":{{}},"message":"..."}}]\n\n'
        f"NEVER return an empty array. For greetings/questions use category=chat.\n\n"
        f"{registry.build_prompt()}"
    )

def get_ai_decisions(user_input):
    conversation_history.append({"role":"user","content":user_input})
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role":"system","content":get_system_prompt()}]+conversation_history,
        temperature=0.2, max_tokens=800,
    )
    reply = response.choices[0].message.content.strip()
    conversation_history.append({"role":"assistant","content":reply})
    if reply.startswith("```"):
        parts = reply.split("```")
        reply = parts[1][4:] if len(parts)>1 and parts[1].startswith("json") else (parts[1] if len(parts)>1 else reply)
    reply = reply.strip()
    try:
        parsed = json.loads(reply)
        if isinstance(parsed,list): return parsed or _fallback(reply)
        if isinstance(parsed,dict): return [parsed]
    except: pass
    decisions,depth,start=[],0,None
    for i,ch in enumerate(reply):
        if ch=="{":
            if depth==0: start=i
            depth+=1
        elif ch=="}":
            depth-=1
            if depth==0 and start is not None:
                try: decisions.append(json.loads(reply[start:i+1]))
                except: pass
                start=None
    return decisions or _fallback(reply)

def _fallback(msg): return [{"category":"chat","action":"answer","params":{},"message":msg}]

def execute_decision(decision):
    global cwd
    cat,action,params = decision.get("category","chat"),decision.get("action",""),decision.get("params",{})
    if cat=="file" and action=="change_dir":
        target = os.path.abspath(os.path.expanduser(params.get("path",cwd)))
        if os.path.isdir(target):
            cwd=target; os.chdir(cwd); return f"Now in: {cwd}"
        return f"Not found: {target}"
    if cat=="chat": return ""
    return registry.route(cat,action,params)

def process_command(user_input):
    results=[]
    for dec in get_ai_decisions(user_input):
        msg=dec.get("message","")
        if msg: results.append(msg)
        if dec.get("category")=="chat": continue
        try:
            out=execute_decision(validate(dec,skip_confirmation=False))
            if out: results.append(out)
        except ValidationError as e: results.append(f"Blocked: {e}")
        except ConfirmationRequired as e: results.append(f"Confirm? {e}")
        except Exception as e: results.append(f"Error: {e}")
    return results

def speak(text):
    if not TTS_AVAILABLE: return
    def _r():
        try: _tts_engine.say(text[:300]); _tts_engine.runAndWait()
        except: pass
    threading.Thread(target=_r,daemon=True).start()

# ─────────────────────────────────────────────────────────────────────────────
# COLOURS
# ─────────────────────────────────────────────────────────────────────────────
BG          = (6,   10,  22)
ACCENT      = (0,  212, 255)
ACCENT_DIM  = (0,  100, 140)
PURPLE      = (124, 58, 237)
GREEN       = (16, 185, 129)
AMBER       = (251,191,  36)
RED         = (239, 68,  68)
WHITE       = (220,235, 255)
MUTED       = (70,  90, 130)
FPS         = 60

STATE_COLORS = {"idle":MUTED,"listening":PURPLE,"thinking":ACCENT,"speaking":GREEN,"wake":AMBER}

def aa_circle(s,x,y,r,c):
    try: pygame.gfxdraw.aacircle(s,x,y,r,c)
    except: pass
def fill_circle(s,x,y,r,c):
    try: pygame.gfxdraw.filled_circle(s,x,y,r,c)
    except: pass

def draw_panel(surf, rect, title, font, alpha=200, border_col=None):
    s = pygame.Surface((rect.w,rect.h),pygame.SRCALPHA)
    s.fill((8,14,30,alpha))
    bc = border_col or (0,180,220,55)
    pygame.draw.rect(s,bc,(0,0,rect.w,rect.h),1,border_radius=4)
    # top accent line
    pygame.draw.rect(s,(0,212,255,60),(0,0,rect.w,1),border_radius=2)
    surf.blit(s,rect.topleft)
    if title:
        surf.blit(font.render(title,True,ACCENT_DIM),(rect.x+6,rect.y+5))


# ─────────────────────────────────────────────────────────────────────────────
# CINEMATIC BRAIN  — movie-style holographic neural sphere
# ─────────────────────────────────────────────────────────────────────────────
#
#  Architecture:
#   • Two concentric rotating hemisphere meshes (lat/lon grid) — one fast, one slow
#   • 200 neural nodes on sphere surface with depth-sorted rendering
#   • Glowing connection edges — thickness & brightness by depth & activity
#   • Electric arc bolts between random active nodes (jagged multi-segment)
#   • Data packet sparks racing along edges
#   • Volumetric core glow that pulses with state
#   • Equatorial energy ring that spins
#   • Brain "lobe" hint — slight left/right bulge on the sphere
#   • All colours and speeds react to brain state
# ─────────────────────────────────────────────────────────────────────────────

def _rot_y(x, y, z, a):
    return x*math.cos(a)+z*math.sin(a), y, -x*math.sin(a)+z*math.cos(a)

def _rot_x(x, y, z, a):
    return x, y*math.cos(a)-z*math.sin(a), y*math.sin(a)+z*math.cos(a)

def _rot_z(x, y, z, a):
    return x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a), z


class BrainNode:
    __slots__ = ['x0','y0','z0','phase','spd','base_r','active','act_t','energy','kind']
    def __init__(self, x0, y0, z0):
        self.x0 = x0; self.y0 = y0; self.z0 = z0
        self.phase  = random.uniform(0, math.tau)
        self.spd    = random.uniform(0.5, 2.2)
        self.base_r = random.uniform(2.0, 5.5)
        self.active = random.random() > 0.45
        self.act_t  = 0.0          # time since last activation
        self.energy = random.random()
        self.kind   = random.randint(0, 2)  # 0=cyan 1=purple 2=teal

    def update(self, dt, speed_mult):
        self.phase  += self.spd * dt * speed_mult
        self.act_t  += dt
        self.energy += (random.random()-0.5)*0.08
        self.energy  = max(0.0, min(1.0, self.energy))
        if random.random() < 0.005 * speed_mult:
            self.active = not self.active

    @property
    def pulse(self): return (math.sin(self.phase)+1)*0.5

    def screen_pos(self, cx, cy, radius, ry, rx, rz):
        x,y,z = self.x0, self.y0, self.z0
        x,y,z = _rot_z(x,y,z,rz)
        x,y,z = _rot_x(x,y,z,rx)
        x,y,z = _rot_y(x,y,z,ry)
        fov   = 3.2
        scale = radius * fov / (fov + z + 1.5)
        sx = int(cx + x * scale)
        sy = int(cy + y * scale * 0.94)
        return sx, sy, z, scale

    def color(self):
        p = self.pulse * self.energy
        if self.kind == 0:   # electric cyan
            return (int(10+p*20),  int(180+p*75), int(235+p*20), int(200+p*55))
        elif self.kind == 1: # deep purple
            return (int(90+p*65),  int(20+p*40),  int(200+p*55), int(170+p*85))
        else:                # teal-white
            return (int(20+p*40),  int(190+p*65), int(180+p*75), int(185+p*70))


class LightningBolt:
    def __init__(self, ax, ay, bx, by, color, lifetime=0.18):
        self.ax,self.ay,self.bx,self.by = ax,ay,bx,by
        self.color    = color
        self.lifetime = lifetime
        self.born     = time.time()
        self.segs     = random.randint(5, 11)
        self.jitter   = random.uniform(8, 22)
        # Pre-bake the jagged path
        self._bake()

    def _bake(self):
        pts = [(self.ax, self.ay)]
        for k in range(1, self.segs):
            t  = k / self.segs
            mx = self.ax + (self.bx-self.ax)*t + random.uniform(-self.jitter, self.jitter)
            my = self.ay + (self.by-self.ay)*t + random.uniform(-self.jitter, self.jitter)
            pts.append((int(mx), int(my)))
        pts.append((self.bx, self.by))
        self.pts = pts
        # Branch bolt
        self.branch = None
        if random.random() < 0.5 and self.segs > 4:
            bi = random.randint(2, self.segs-2)
            bx = self.pts[bi][0]+random.randint(-30,30)
            by = self.pts[bi][1]+random.randint(-30,30)
            branch_pts = [self.pts[bi]]
            for _ in range(3):
                branch_pts.append((branch_pts[-1][0]+random.randint(-15,15),
                                   branch_pts[-1][1]+random.randint(-15,15)))
            branch_pts.append((bx,by))
            self.branch = branch_pts

    @property
    def alive(self): return time.time()-self.born < self.lifetime

    @property
    def frac(self): return max(0.0, 1.0-(time.time()-self.born)/self.lifetime)

    def draw(self, surf):
        f = self.frac
        al = int(f * 230)
        c  = (*self.color[:3], al)
        if len(self.pts) > 1:
            try: pygame.draw.lines(surf, c, False, self.pts, 2)
            except: pass
            # Bright inner core
            ci = (min(255,self.color[0]+80), min(255,self.color[1]+80),
                  min(255,self.color[2]+80), int(f*180))
            try: pygame.draw.lines(surf, ci, False, self.pts, 1)
            except: pass
        if self.branch:
            cb = (*self.color[:3], int(al*0.5))
            try: pygame.draw.lines(surf, cb, False, self.branch, 1)
            except: pass


class DataPacket:
    def __init__(self, ax, ay, bx, by, color):
        self.ax,self.ay,self.bx,self.by = ax,ay,bx,by
        self.color = color
        self.t     = 0.0
        self.speed = random.uniform(0.8, 2.5)
        self.size  = random.randint(2,4)

    def update(self, dt): self.t += dt * self.speed
    @property
    def done(self): return self.t >= 1.0

    def draw(self, surf):
        t  = min(self.t, 1.0)
        # ease in-out
        et = t*t*(3-2*t)
        x  = int(self.ax + (self.bx-self.ax)*et)
        y  = int(self.ay + (self.by-self.ay)*et)
        al = int(255*(1-abs(t-0.5)*1.6)+80)
        al = max(0,min(255,al))
        r  = self.size
        # Trail
        for tr in range(3,0,-1):
            tt = max(0.0,t-tr*0.06)
            et2= tt*tt*(3-2*tt)
            tx = int(self.ax+(self.bx-self.ax)*et2)
            ty = int(self.ay+(self.by-self.ay)*et2)
            try: pygame.gfxdraw.filled_circle(surf,tx,ty,r-tr+1,(*self.color[:3],al//(tr+1)))
            except: pass
        try:
            pygame.gfxdraw.filled_circle(surf,x,y,r,(*self.color[:3],al))
            pygame.gfxdraw.filled_circle(surf,x,y,max(1,r-1),(255,255,255,al//2))
        except: pass


class BrainWidget:
    """
    Cinematic holographic brain:
    - Sphere mesh (two contra-rotating lat/lon grids)
    - 200 neural nodes with depth sorting and perspective
    - Glowing edges between close nodes
    - Lightning bolts and data packets
    - Pulsing volumetric core
    - Spinning equatorial ring
    """
    N_NODES = 200

    def __init__(self, cx, cy, radius):
        self.cx = cx; self.cy = cy; self.radius = radius
        self.state = "idle"
        self._t    = 0.0
        self.ry    = 0.0   # primary Y rotation
        self.rx    = 0.18  # slight X tilt (static-ish)
        self.rz    = 0.0   # slow Z wobble
        self.ry2   = 0.0   # second mesh counter-rotation
        self.nodes : list[BrainNode] = []
        self.bolts : list[LightningBolt] = []
        self.packets: list[DataPacket] = []
        self._next_bolt   = 0.0
        self._next_packet = 0.0
        self._build()

    def _build(self):
        self.nodes = []
        # Fibonacci sphere — perfectly even distribution
        golden = math.pi*(3-math.sqrt(5))
        for i in range(self.N_NODES):
            y   = 1-(i/(self.N_NODES-1))*2
            r   = math.sqrt(max(0.0, 1-y*y))
            th  = golden*i
            # Slight lobe bulge: left hemisphere bigger
            lobe_x = 1.0 + 0.08*math.cos(th)
            self.nodes.append(BrainNode(
                math.cos(th)*r*lobe_x,
                y,
                math.sin(th)*r
            ))

    def resize(self, cx, cy, radius):
        self.cx = cx; self.cy = cy; self.radius = radius

    # ── speeds per state ──────────────────────────────────────────────────
    def _speed(self):
        return {"idle":0.14,"listening":0.28,"thinking":0.75,
                "speaking":0.45,"wake":0.55}.get(self.state,0.14)

    def _bolt_interval(self):
        return {"idle":2.5,"listening":0.9,"thinking":0.12,
                "speaking":0.28,"wake":0.22}.get(self.state,2.0)

    def _packet_interval(self):
        return {"idle":3.0,"listening":1.2,"thinking":0.18,
                "speaking":0.35,"wake":0.3}.get(self.state,2.5)

    def update(self, dt):
        sp = self._speed()
        self._t  += dt
        self.ry  += sp * dt
        self.ry2 -= sp * 0.6 * dt
        self.rx   = 0.18 + 0.05*math.sin(self._t*0.3)
        self.rz   = 0.04*math.sin(self._t*0.17)

        for nd in self.nodes:
            nd.update(dt, sp/0.14)
        if self.state == "thinking":
            for nd in self.nodes:
                if random.random() < 0.015: nd.active = True

        now = time.time()
        # Bolts
        if now > self._next_bolt:
            active = [n for n in self.nodes if n.active]
            if len(active) >= 2:
                a,b = random.sample(active,2)
                ax,ay,_,_ = a.screen_pos(self.cx,self.cy,self.radius,self.ry,self.rx,self.rz)
                bx,by,_,_ = b.screen_pos(self.cx,self.cy,self.radius,self.ry,self.rx,self.rz)
                sc  = STATE_COLORS.get(self.state, ACCENT)
                self.bolts.append(LightningBolt(ax,ay,bx,by,sc))
            self._next_bolt = now + random.uniform(self._bolt_interval()*0.6,
                                                   self._bolt_interval()*1.4)
        # Packets
        if now > self._next_packet:
            proj = self._get_projected()
            if len(proj) >= 2:
                # pick two close front-facing nodes
                front = [(nd,sx,sy,d) for nd,sx,sy,d in proj if d>0]
                if len(front) >= 2:
                    a,b = random.sample(front[:60],2)
                    sc  = STATE_COLORS.get(self.state, ACCENT)
                    self.packets.append(DataPacket(a[1],a[2],b[1],b[2],sc))
            self._next_packet = now + random.uniform(self._packet_interval()*0.5,
                                                     self._packet_interval()*1.5)

        self.bolts   = [b for b in self.bolts   if b.alive]
        for pk in self.packets: pk.update(dt)
        self.packets = [pk for pk in self.packets if not pk.done]

    def _get_projected(self):
        proj = []
        for nd in self.nodes:
            sx,sy,depth,scale = nd.screen_pos(self.cx,self.cy,self.radius,
                                               self.ry,self.rx,self.rz)
            proj.append((nd,sx,sy,depth))
        proj.sort(key=lambda t: t[3])
        return proj

    def draw(self, surf):
        cx,cy,R = int(self.cx), int(self.cy), self.radius
        sc  = STATE_COLORS.get(self.state, MUTED)
        sp  = self._speed()

        # ── 1. Volumetric core glow ───────────────────────────────────────
        pulse_core = (math.sin(self._t*2.5)+1)*0.5
        n_layers = 14
        for i in range(n_layers, 0, -1):
            fr   = i/n_layers
            r2   = int(R*(0.18+fr*0.55))
            al   = int(fr*fr*(35+pulse_core*25))
            col  = (int(sc[0]*0.4+0*0.6),
                    int(sc[1]*0.4+10*0.6),
                    int(sc[2]*0.4+30*0.6), al)
            try: pygame.gfxdraw.filled_circle(surf,cx,cy,r2,col)
            except: pass

        # ── 2. Two sphere wire meshes ─────────────────────────────────────
        def draw_mesh(ry_off, alpha_mult, subdivs=18):
            for lat_i in range(1, subdivs//2):
                lat  = math.pi * lat_i / (subdivs//2)
                pts  = []
                for lon_i in range(subdivs+1):
                    lon = math.tau * lon_i / subdivs
                    x0  = math.sin(lat)*math.cos(lon)
                    y0  = math.cos(lat)
                    z0  = math.sin(lat)*math.sin(lon)
                    x,y,z = _rot_z(x0,y0,z0,self.rz)
                    x,y,z = _rot_x(x,y,z,self.rx)
                    x,y,z = _rot_y(x,y,z,ry_off)
                    fov=3.2; s=R*fov/(fov+z+1.5)
                    vis=(z+1)*0.5
                    if vis<0.08: pts.append(None); continue
                    pts.append((int(cx+x*s),int(cy+y*s*0.94),vis))
                # draw segments
                for k in range(len(pts)-1):
                    if pts[k] is None or pts[k+1] is None: continue
                    vis=pts[k][2]; al=int(vis*vis*55*alpha_mult)
                    if al<4: continue
                    col=(*sc,al)
                    try: pygame.gfxdraw.line(surf,pts[k][0],pts[k][1],
                                                  pts[k+1][0],pts[k+1][1],col)
                    except: pass

            for lon_i in range(subdivs):
                lon = math.tau*lon_i/subdivs
                pts = []
                for lat_i in range(subdivs//2+1):
                    lat = math.pi*lat_i/(subdivs//2)
                    x0  = math.sin(lat)*math.cos(lon)
                    y0  = math.cos(lat)
                    z0  = math.sin(lat)*math.sin(lon)
                    x,y,z=_rot_z(x0,y0,z0,self.rz)
                    x,y,z=_rot_x(x,y,z,self.rx)
                    x,y,z=_rot_y(x,y,z,ry_off)
                    fov=3.2; s=R*fov/(fov+z+1.5)
                    vis=(z+1)*0.5
                    if vis<0.08: pts.append(None); continue
                    pts.append((int(cx+x*s),int(cy+y*s*0.94),vis))
                for k in range(len(pts)-1):
                    if pts[k] is None or pts[k+1] is None: continue
                    vis=pts[k][2]; al=int(vis*vis*45*alpha_mult)
                    if al<4: continue
                    try: pygame.gfxdraw.line(surf,pts[k][0],pts[k][1],
                                                  pts[k+1][0],pts[k+1][1],(*sc,al))
                    except: pass

        draw_mesh(self.ry,  1.0,  18)   # primary mesh
        draw_mesh(self.ry2, 0.45, 12)   # counter-rotating ghost mesh

        # ── 3. Equatorial energy ring ─────────────────────────────────────
        ring_tilt = self.rx + 0.4
        ring_pts  = []
        n_rp      = 80
        for i in range(n_rp+1):
            a   = math.tau*i/n_rp
            x0  = math.cos(a)
            y0  = 0.0
            z0  = math.sin(a)*0.95
            x,y,z=_rot_z(x0,y0,z0,self.rz)
            x,y,z=_rot_x(x,y,z,ring_tilt)
            x,y,z=_rot_y(x,y,z,self.ry*1.8)
            fov=3.2; s=R*1.06*fov/(fov+z+1.5)
            vis=(z+1)*0.5
            ring_pts.append((int(cx+x*s),int(cy+y*s*0.94),vis))
        for k in range(len(ring_pts)-1):
            vis=ring_pts[k][2]
            al=int(vis**1.5*140)
            if al<6: continue
            bright=(*sc,al)
            try: pygame.gfxdraw.line(surf,ring_pts[k][0],ring_pts[k][1],
                                          ring_pts[k+1][0],ring_pts[k+1][1],bright)
            except: pass
        # Ring glow dots
        for k in range(0,len(ring_pts)-1,4):
            vis=ring_pts[k][2]
            if vis<0.3: continue
            try: pygame.gfxdraw.filled_circle(surf,ring_pts[k][0],ring_pts[k][1],
                                              2,(*sc,int(vis*180)))
            except: pass

        # ── 4. Node edges (connections) ───────────────────────────────────
        proj = self._get_projected()
        conn_r2 = (R*0.52)**2

        # Use a layer surface for blending
        edge_surf = pygame.Surface(surf.get_size(), pygame.SRCALPHA)

        for i in range(len(proj)):
            nd_a,ax,ay,da = proj[i]
            if da < -0.3: continue
            vis_a = (da+1)*0.5
            for nd_b,bx,by,db in proj[i+1:i+16]:
                if db < -0.3: continue
                d2=(ax-bx)**2+(ay-by)**2
                if d2 > conn_r2: continue
                vis=(vis_a+(db+1)*0.5)*0.5
                dist=math.sqrt(d2)
                fade=(1-dist/math.sqrt(conn_r2))
                if nd_a.active and nd_b.active:
                    al=int(fade*fade*vis*vis*200)
                    nc=nd_a.color()
                    col=(nc[0],nc[1],nc[2],al)
                    try: pygame.gfxdraw.line(edge_surf,ax,ay,bx,by,col)
                    except: pass
                elif nd_a.active or nd_b.active:
                    al=int(fade*vis*90)
                    try: pygame.gfxdraw.line(edge_surf,ax,ay,bx,by,(*sc,al))
                    except: pass
                else:
                    al=int(fade*vis*30)
                    try: pygame.gfxdraw.line(edge_surf,ax,ay,bx,by,(40,60,130,al))
                    except: pass

        surf.blit(edge_surf,(0,0))

        # ── 5. Lightning bolts ────────────────────────────────────────────
        for bolt in self.bolts:
            bolt.draw(surf)

        # ── 6. Data packets ───────────────────────────────────────────────
        for pk in self.packets:
            pk.draw(surf)

        # ── 7. Neural nodes ───────────────────────────────────────────────
        for nd,sx,sy,depth in proj:
            vis   = (depth+1)*0.5
            r_scl = 0.55 + vis*0.55
            r     = max(1, int(nd.base_r * r_scl))

            if nd.active:
                nc  = nd.color()
                pls = nd.pulse * vis
                # Outer glow layers
                for gi in range(5,0,-1):
                    gr  = r + gi*3
                    al  = int(pls * (28-gi*4) * vis)
                    if al > 3:
                        try: pygame.gfxdraw.filled_circle(surf,sx,sy,gr,(nc[0],nc[1],nc[2],al))
                        except: pass
                # Core node
                al_core = int((0.5+pls*0.5)*nc[3])
                try:
                    pygame.gfxdraw.filled_circle(surf,sx,sy,r,(nc[0],nc[1],nc[2],al_core))
                    pygame.gfxdraw.aacircle(surf,sx,sy,r,(nc[0],nc[1],nc[2],al_core))
                    # Bright hot centre
                    if r > 2:
                        pygame.gfxdraw.filled_circle(surf,sx,sy,max(1,r-1),
                                                     (255,255,255,int(pls*120*vis)))
                except: pass
            else:
                al = int(vis*vis*55)
                try: pygame.gfxdraw.filled_circle(surf,sx,sy,r,(30,50,120,al))
                except: pass

        # ── 8. Outer atmosphere rings ─────────────────────────────────────
        pulse_ring=(math.sin(self._t*1.8)+1)*0.5
        for i in range(6):
            ph = (self._t*0.55+i*0.167)%1.0
            rr = int(R*(1.02+ph*0.35))
            al = int((1-ph)**2.2*(40+pulse_ring*30))
            if al>3:
                try: pygame.gfxdraw.aacircle(surf,cx,cy,rr,(*sc,al))
                except: pass
        # Static outer ring
        try:
            pygame.gfxdraw.aacircle(surf,cx,cy,int(R*1.02),(*sc,55))
            pygame.gfxdraw.aacircle(surf,cx,cy,int(R*1.04),(*sc,25))
        except: pass



# ─────────────────────────────────────────────────────────────────────────────
# WAVEFORM CAPTURE
# ─────────────────────────────────────────────────────────────────────────────
class WaveformCapture(threading.Thread):
    CHUNK=512; RATE=16000; HIST=100
    def __init__(self):
        super().__init__(daemon=True)
        self.samples=deque([0.0]*self.HIST,maxlen=self.HIST)
        self._active=True; self._pa=self._stream=None
    def run(self):
        if not WAVEFORM_AVAILABLE: return
        try:
            self._pa=pyaudio.PyAudio()
            self._stream=self._pa.open(format=pyaudio.paInt16,channels=1,rate=self.RATE,
                input=True,frames_per_buffer=self.CHUNK)
            while self._active:
                try:
                    raw=self._stream.read(self.CHUNK,exception_on_overflow=False)
                    data=np.frombuffer(raw,dtype=np.int16).astype(np.float32)/32768.0
                    self.samples.append(float(np.abs(data).mean()))
                except: time.sleep(0.05)
        except: pass
    def stop(self):
        self._active=False
        try:
            if self._stream: self._stream.stop_stream(); self._stream.close()
            if self._pa: self._pa.terminate()
        except: pass
    def get(self): return list(self.samples)

# ─────────────────────────────────────────────────────────────────────────────
# VOICE LISTENER
# ─────────────────────────────────────────────────────────────────────────────
class VoiceListener(threading.Thread):
    def __init__(self,text_q,state_q):
        super().__init__(daemon=True)
        self.text_q,self.state_q=text_q,state_q
        self._stop=threading.Event()
        self.rec=sr.Recognizer() if VOICE_AVAILABLE else None
        if self.rec:
            self.rec.pause_threshold=0.8
            self.rec.energy_threshold=300
            self.rec.dynamic_energy_threshold=True

    def stop(self): self._stop.set()

    def _has_wake(self,t): return any(w in t.lower() for w in WAKE_WORDS)
    def _strip_wake(self,t):
        tl=t.lower()
        for w in WAKE_WORDS:
            if tl.startswith(w): return t[len(w):].strip(" ,!")
        return t

    def run(self):
        if not VOICE_AVAILABLE:
            self.state_q.put("idle"); return
        try: mic=sr.Microphone()
        except Exception as e:
            print(f"[Voice] No mic: {e}"); self.state_q.put("idle"); return
        with mic as src: self.rec.adjust_for_ambient_noise(src,duration=1)
        activated=False
        while not self._stop.is_set():
            try:
                self.state_q.put("listening" if activated else "idle")
                with mic as src:
                    audio=self.rec.listen(src,timeout=6,phrase_time_limit=18)
                text=self.rec.recognize_google(audio).strip()
                if not text: continue
                if not activated:
                    if self._has_wake(text):
                        activated=True; self.state_q.put("wake")
                        rest=self._strip_wake(text)
                        if rest: self.text_q.put(rest); activated=False
                    continue
                self.text_q.put(text); activated=False
            except sr.WaitTimeoutError: pass
            except sr.UnknownValueError: pass
            except sr.RequestError as e: print(f"[Voice] {e}"); time.sleep(2)
            except Exception as e: print(f"[Voice] {e}"); time.sleep(1)
        self.state_q.put("idle")

# ─────────────────────────────────────────────────────────────────────────────
# COMMAND WORKER
# ─────────────────────────────────────────────────────────────────────────────
class CommandWorker(threading.Thread):
    def __init__(self,cmd_q,result_q,state_q):
        super().__init__(daemon=True)
        self.cmd_q,self.result_q,self.state_q=cmd_q,result_q,state_q
    def run(self):
        while True:
            text=self.cmd_q.get()
            if text is None: break
            self.state_q.put("thinking")
            try: results=process_command(text)
            except Exception as e:
                results=[f"Error: {e}"]; traceback.print_exc()
            self.result_q.put((text,results))
            self.state_q.put("speaking")
            if results: speak(results[0])
            time.sleep(1.8)
            self.state_q.put("listening")

# ─────────────────────────────────────────────────────────────────────────────
# METRIC STREAM
# ─────────────────────────────────────────────────────────────────────────────
class MetricStream:
    def __init__(self,lo,hi,smooth=0.12):
        self.lo,self.hi,self.smooth=lo,hi,smooth
        self.val=random.uniform(lo,hi)
        self.hist=deque([self.val]*50,maxlen=50)
    def tick(self):
        self.val+=(random.uniform(self.lo,self.hi)-self.val)*self.smooth
        self.hist.append(self.val); return self.val
    def get_hist(self): return list(self.hist)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN GUI
# ─────────────────────────────────────────────────────────────────────────────
def run_gui():
    pygame.init()
    info = pygame.display.Info()
    DW, DH = info.current_w, info.current_h
    fullscreen = False
    WW, WH = 1380, 860

    def make_screen(fs):
        if fs:
            return pygame.display.set_mode((DW,DH), pygame.FULLSCREEN|pygame.HWSURFACE|pygame.DOUBLEBUF)
        return pygame.display.set_mode((WW,WH), pygame.NOFRAME|pygame.HWSURFACE|pygame.DOUBLEBUF)

    screen = make_screen(fullscreen)
    pygame.display.set_caption("JARVIS")
    clock  = pygame.time.Clock()

    def mono(sz, b=False): return pygame.font.SysFont("monospace", sz, b)
    fXS = mono(10); fS = mono(11); fM = mono(13,True)
    fL  = mono(15,True); fXL = mono(19,True); fT = mono(25,True)

    brain = BrainWidget(0, 0, 200)

    text_q, cmd_q, result_q, state_q = (queue.Queue() for _ in range(4))
    listener = VoiceListener(text_q, state_q)
    worker   = CommandWorker(cmd_q, result_q, state_q)
    waveform = WaveformCapture()
    listener.start(); worker.start(); waveform.start()

    # ── State ─────────────────────────────────────────────────────────────
    brain_state  = "idle"
    last_cmd     = ""
    # Persistent result: (question, [result lines])  — cleared on next question
    current_result_q  = ""
    current_result_lines: list = []
    result_scroll = 0   # scroll offset for long results

    cmd_history  = deque(maxlen=30)
    hist_idx     = -1
    typing_text  = ""
    typing_active= False

    metrics = {
        "Neural Load":   MetricStream(15,90),
        "Sig Clarity":   MetricStream(65,99),
        "Latency ms":    MetricStream(45,280),
        "Token Rate":    MetricStream(25,85),
        "Confidence":    MetricStream(72,99),
        "Mem Used":      MetricStream(35,75),
        "CPU Load":      MetricStream(10,60),
        "GPU Load":      MetricStream(5,40),
    }

    log_lines: deque = deque(maxlen=100)
    def log(msg, col=None):
        log_lines.append((datetime.now().strftime("%H:%M:%S"), str(msg)[:36], col or MUTED))

    log("JARVIS v2 boot sequence...", ACCENT)
    log(f"Model: {GROQ_MODEL[:22]}", ACCENT_DIM)
    log(f"CWD: {cwd[:24]}", MUTED)
    log("Voice: ACTIVE" if VOICE_AVAILABLE else "Voice: OFF", GREEN if VOICE_AVAILABLE else RED)
    log("TTS: ACTIVE"   if TTS_AVAILABLE   else "TTS: OFF",   GREEN if TTS_AVAILABLE   else MUTED)
    log("Waveform: ON"  if WAVEFORM_AVAILABLE else "Waveform: OFF", GREEN if WAVEFORM_AVAILABLE else MUTED)
    log("Say 'Hey JARVIS' to activate", AMBER)

    _act_pool = [
        "Plugin registry scan OK","Token budget check","Neural sync complete",
        "Memory index rebuild","Noise calibration OK","Context: 4096 tokens",
        "file_ops plugin ready","app_control ready","browser plugin ready",
        "email plugin ready","Heartbeat OK","Entropy pool seeded",
        "Ambient threshold recalc","Signal quality nominal","Cache warm",
        "Inference engine ready","Tokeniser loaded","Attention head OK",
    ]
    last_act  = time.time()
    t_start   = time.time()

    hex_lines: deque = deque(maxlen=22)
    def gen_hex(): return " ".join(f"{random.randint(0,255):02X}" for _ in range(9))
    last_hex  = time.time()

    running = True

    def layout(W, H):
        PAD = 12
        lw  = max(195, int(W*0.165))
        rw  = max(195, int(W*0.165))
        bw  = W - lw - rw - PAD*4
        bcx = lw + PAD*2 + bw//2
        # Brain sits in the upper portion; result panel below
        brain_top_frac = 0.48   # brain centre at ~48% height
        bcy  = int(H * brain_top_frac)
        brad = max(110, min(min(bw//2, int(H*0.35)), 240))
        # Result panel: starts below the waveform, ends above input bar
        res_top  = bcy + brad + 68        # below waveform
        res_bot  = H - 56                 # above input bar
        res_rect = pygame.Rect(lw+PAD*2, res_top, bw, max(60, res_bot-res_top))
        return dict(W=W,H=H,P=PAD,lw=lw,rw=rw,bw=bw,bcx=bcx,bcy=bcy,brad=brad,
                    res_rect=res_rect)

    while running:
        now = time.time()
        dt  = clock.tick(FPS) / 1000.0
        W, H = screen.get_size()
        L    = layout(W, H)
        PAD  = L["P"]
        brain.resize(L["bcx"], L["bcy"], L["brad"])

        # ── Events ────────────────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: running = False
            elif ev.type == pygame.KEYDOWN:
                k = ev.key
                if k == pygame.K_ESCAPE:
                    if typing_text: typing_text = ""; typing_active = False
                    else: running = False
                elif k in (pygame.K_F11, pygame.K_f) and not typing_active:
                    fullscreen = not fullscreen
                    screen = make_screen(fullscreen)
                elif k == pygame.K_RETURN and typing_text.strip():
                    cmd = typing_text.strip(); typing_text = ""; hist_idx = -1; typing_active = False
                    if cmd.lower() in ("exit","quit"): running = False
                    else:
                        cmd_history.appendleft(cmd)
                        last_cmd = cmd
                        # Clear result panel for new question
                        current_result_q = cmd
                        current_result_lines = ["⏳  Processing..."]
                        result_scroll = 0
                        log(f"CMD: {cmd[:32]}", WHITE)
                        cmd_q.put(cmd)
                elif k == pygame.K_BACKSPACE: typing_text = typing_text[:-1]
                elif k == pygame.K_UP:
                    if typing_active and cmd_history:
                        hist_idx = min(hist_idx+1, len(cmd_history)-1)
                        typing_text = list(cmd_history)[hist_idx]
                    else:
                        result_scroll = max(0, result_scroll-1)
                elif k == pygame.K_DOWN:
                    if typing_active:
                        hist_idx = max(hist_idx-1, -1)
                        typing_text = "" if hist_idx<0 else list(cmd_history)[hist_idx]
                    else:
                        result_scroll += 1
                elif ev.unicode and ev.unicode.isprintable():
                    typing_text += ev.unicode; typing_active = True

            elif ev.type == pygame.MOUSEWHEEL:
                result_scroll = max(0, result_scroll - ev.y)

        # ── Drain queues ──────────────────────────────────────────────────
        while not state_q.empty():
            brain_state = state_q.get_nowait(); brain.state = brain_state
        while not text_q.empty():
            spoken = text_q.get_nowait(); last_cmd = spoken
            current_result_q = spoken
            current_result_lines = ["⏳  Processing..."]
            result_scroll = 0
            log(f"VOICE: {spoken[:30]}", PURPLE)
            cmd_q.put(spoken)
        while not result_q.empty():
            _, results = result_q.get_nowait()
            current_result_lines = results if results else ["(no output)"]
            result_scroll = 0
            for r in results: log(f"OUT: {r[:32]}", GREEN)

        # ── Ticks ─────────────────────────────────────────────────────────
        for m in metrics.values(): m.tick()
        if now - last_act > random.uniform(1.5, 4):
            log(random.choice(_act_pool)); last_act = now
        if now - last_hex > 0.28:
            hex_lines.append(gen_hex()); last_hex = now
        brain.update(dt)
        sc = STATE_COLORS.get(brain_state, MUTED)

        # ══════════════════════════════════════════════════════════════════
        # DRAW
        # ══════════════════════════════════════════════════════════════════
        screen.fill(BG)

        # Subtle scanlines
        scan = pygame.Surface((W,H), pygame.SRCALPHA)
        for y in range(0,H,3): pygame.draw.line(scan,(0,0,0,15),(0,y),(W,y))
        screen.blit(scan,(0,0))

        # Centre glow behind brain
        for rg in range(L["brad"]+90, 0, -14):
            al = max(0, 10-(L["brad"]+90-rg)//12)
            fill_circle(screen, L["bcx"], L["bcy"], rg, (0,15,45,al))

        # Brain
        brain.draw(screen)

        # ── Waveform ──────────────────────────────────────────────────────
        wave = waveform.get()
        ww   = min(L["bw"]-30, 680); wx = L["bcx"]-ww//2
        wy   = L["bcy"] + L["brad"] + 18; wh = 38
        if wy + wh < L["res_rect"].top - 4:
            pygame.draw.rect(screen,(12,18,38),(wx,wy,ww,wh),border_radius=4)
            pygame.draw.rect(screen,(*sc,45),(wx,wy,ww,wh),1,border_radius=4)
            bw2 = max(1, ww//len(wave)) if wave else 1
            mid = wy + wh//2
            for i,sv in enumerate(wave):
                bh = max(2, min(int(sv*wh*5), wh//2-1))
                al = int(50+160*(i/max(len(wave),1)))
                bx2= wx + i*bw2
                pygame.draw.rect(screen,(*sc,al),(bx2,mid-bh,max(1,bw2-1),bh),border_radius=1)
                pygame.draw.rect(screen,(*sc,al//2),(bx2,mid,max(1,bw2-1),bh//2),border_radius=1)

        # ── State + last command labels ───────────────────────────────────
        slabels = {"idle":"◉  STANDBY","listening":"◎  LISTENING",
                   "thinking":"◈  PROCESSING","speaking":"◆  EXECUTING","wake":"★  WAKE WORD"}
        slbl = fL.render(slabels.get(brain_state, brain_state.upper()), True, sc)
        screen.blit(slbl,(L["bcx"]-slbl.get_width()//2, L["bcy"]-L["brad"]-34))
        if last_cmd:
            cl = fS.render(f'▸  "{last_cmd[:75]}"', True, (*WHITE,160))
            screen.blit(cl,(L["bcx"]-cl.get_width()//2, L["bcy"]-L["brad"]-16))

        # ══════════════════════════════════════════════════════════════════
        # PERSISTENT RESULT PANEL (centre bottom)
        # ══════════════════════════════════════════════════════════════════
        rr = L["res_rect"]
        if rr.height > 50:
            # Panel background
            rs = pygame.Surface((rr.w, rr.h), pygame.SRCALPHA)
            rs.fill((6,12,28,215))
            # Glowing border — colour matches state when active, else dim
            bc_col = (*sc, 90) if brain_state != "idle" else (0,180,220,40)
            pygame.draw.rect(rs, bc_col, (0,0,rr.w,rr.h), 1, border_radius=6)
            # Top accent bar
            pygame.draw.rect(rs, (*sc,70), (0,0,rr.w,2), border_radius=2)
            screen.blit(rs, rr.topleft)

            # Header row
            hdr = fM.render("◈  LAST RESULT", True, sc)
            screen.blit(hdr, (rr.x+10, rr.y+7))

            if current_result_q:
                qlbl = fXS.render(f"Q: {current_result_q[:90]}", True, (*AMBER,180))
                screen.blit(qlbl, (rr.x+10, rr.y+26))

            # Separator line
            pygame.draw.line(screen, (*sc,40), (rr.x+8,rr.y+40),(rr.x+rr.w-8,rr.y+40),1)

            # Result lines with scroll
            line_h   = 15
            max_vis  = max(1,(rr.h - 48) // line_h)
            # Wrap all lines
            wrapped = []
            for raw in current_result_lines:
                chars_per = max(20,(rr.w-24)//7)
                for wl in textwrap.wrap(str(raw), chars_per) or [" "]:
                    wrapped.append(wl)

            total    = len(wrapped)
            result_scroll = min(result_scroll, max(0, total-max_vis))
            visible  = wrapped[result_scroll : result_scroll+max_vis]

            for idx, wline in enumerate(visible):
                ly = rr.y + 48 + idx*line_h
                # colour: first line = AI message (white), rest = output (green-ish)
                col = WHITE if idx+result_scroll==0 else (*GREEN,210)
                if wline.startswith("⏳"): col = AMBER
                if wline.startswith("Blocked") or wline.startswith("Error"): col = (*RED,220)
                screen.blit(fXS.render(wline, True, col), (rr.x+10, ly))

            # Scroll indicator
            if total > max_vis:
                sb_h = max(20, int(rr.h * max_vis/total))
                sb_y = rr.y + 40 + int((rr.h-40-sb_h)*(result_scroll/max(1,total-max_vis)))
                pygame.draw.rect(screen,(*sc,60),(rr.x+rr.w-5, sb_y, 3, sb_h),border_radius=2)
                more = fXS.render(f"↓ {total-result_scroll-max_vis} more", True, (*sc,120))
                screen.blit(more,(rr.x+rr.w-more.get_width()-8, rr.y+rr.h-13))

        # ── Text input bar ────────────────────────────────────────────────
        ib_w = min(L["bw"]+60, W-L["lw"]-L["rw"]-30)
        ib_x = L["bcx"]-ib_w//2; ib_y = H-48; ib_h = 34
        pygame.draw.rect(screen,(10,16,36),(ib_x,ib_y,ib_w,ib_h),border_radius=6)
        pygame.draw.rect(screen,(*ACCENT,75) if typing_active else (*MUTED,38),
                         (ib_x,ib_y,ib_w,ib_h),1,border_radius=6)
        hint = fXS.render("Type command · Enter=send · ↑↓=history · F/F11=fullscreen · ESC=quit",True,MUTED)
        screen.blit(hint,(ib_x+8,ib_y-13))
        cursor = "█" if int(now*2)%2==0 else " "
        screen.blit(fS.render((typing_text+cursor)[-88:],True,WHITE),(ib_x+10,ib_y+10))

        # ══════════════════════════════════════════════════════════════════
        # LEFT PANELS
        # ══════════════════════════════════════════════════════════════════
        lx = PAD; lw = L["lw"]

        # Logo + uptime
        p = pygame.Rect(lx, PAD, lw, 58)
        draw_panel(screen,p,None,fXS)
        screen.blit(fT.render("JARVIS",True,ACCENT),(p.x+6,p.y+4))
        up = int(now-t_start)
        screen.blit(fXS.render(f"UP  {up//3600:02d}:{(up%3600)//60:02d}:{up%60:02d}",True,MUTED),(p.x+6,p.y+42))

        # Neural metrics
        p2y = p.bottom+PAD; p2h = min(265,H//3)
        p2  = pygame.Rect(lx,p2y,lw,p2h); draw_panel(screen,p2,"NEURAL METRICS",fXS)
        for idx,mk in enumerate(list(metrics.keys())[:4]):
            mv  = metrics[mk].val
            my2 = p2.y+22+idx*57
            vc  = GREEN if mv>70 else AMBER if mv>40 else RED
            screen.blit(fXS.render(mk,True,MUTED),(p2.x+6,my2))
            vs  = f"{mv:.0f}{'ms' if 'ms' in mk else '%'}"
            screen.blit(fXS.render(vs,True,vc),(p2.x+lw-42,my2))
            brx=p2.x+6; bry=my2+13; brw=lw-14; brh=7
            pygame.draw.rect(screen,(18,28,52),(brx,bry,brw,brh),border_radius=3)
            fw = int((min(mv,100)/100)*brw) if "ms" not in mk else int((min(mv,350)/350)*brw)
            pygame.draw.rect(screen,(*vc,185),(brx,bry,fw,brh),border_radius=3)
            hist=metrics[mk].get_hist()[-(lw-14):]
            if len(hist)>1:
                mn2,mx2=min(hist),max(hist)+0.001
                pts=[(brx+int(k*(lw-14)/len(hist)),bry+brh+2+int((1-(v-mn2)/(mx2-mn2))*9))
                     for k,v in enumerate(hist)]
                pygame.draw.lines(screen,(*vc,65),False,pts,1)

        # Inference stats
        p3y = p2.bottom+PAD; p3h = min(90,(H-p2.bottom-PAD*3)//3)
        if p3h > 38:
            p3 = pygame.Rect(lx,p3y,lw,p3h); draw_panel(screen,p3,"INFERENCE",fXS)
            screen.blit(fM.render(f"{metrics['Token Rate'].val:.0f} tok/s",True,ACCENT),(p3.x+6,p3.y+20))
            screen.blit(fM.render(f"{metrics['Latency ms'].val:.0f} ms",True,AMBER),(p3.x+6,p3.y+44))

        # Plugin status
        p4y = (p3.bottom if p3h>38 else p2.bottom)+PAD; p4h = H-p4y-PAD
        if p4h > 45:
            p4 = pygame.Rect(lx,p4y,lw,p4h); draw_panel(screen,p4,"PLUGINS",fXS)
            plugins=[("file_ops",GREEN),("app_control",GREEN),("browser",GREEN),
                     ("email",GREEN),("validator",AMBER),("registry",GREEN)]
            for idx,(pl,pc) in enumerate(plugins):
                if p4.y+22+idx*17 > p4.bottom-5: break
                screen.blit(fXS.render(f"▸ {pl}",True,MUTED),(p4.x+6,p4.y+22+idx*17))
                fill_circle(screen,p4.x+lw-14,p4.y+29+idx*17,4,(*pc,220))

        # ══════════════════════════════════════════════════════════════════
        # RIGHT PANELS
        # ══════════════════════════════════════════════════════════════════
        rx = W-L["rw"]-PAD; rw = L["rw"]

        # Clock
        r1 = pygame.Rect(rx,PAD,rw,58); draw_panel(screen,r1,None,fXS)
        screen.blit(fL.render(datetime.now().strftime("%H:%M:%S"),True,ACCENT),(r1.x+6,r1.y+6))
        screen.blit(fXS.render(datetime.now().strftime("%a %d %b %Y"),True,MUTED),(r1.x+6,r1.y+36))

        # System health
        r2y=r1.bottom+PAD; r2h=min(265,H//3)
        r2=pygame.Rect(rx,r2y,rw,r2h); draw_panel(screen,r2,"SYSTEM HEALTH",fXS)
        for idx,mk in enumerate(list(metrics.keys())[4:]):
            mv=metrics[mk].val; my2=r2.y+22+idx*57
            vc=GREEN if mv>70 else AMBER if mv>40 else RED
            screen.blit(fXS.render(mk,True,MUTED),(r2.x+6,my2))
            screen.blit(fXS.render(f"{mv:.0f}%",True,vc),(r2.x+rw-38,my2))
            brx=r2.x+6; bry=my2+13; brw=rw-14; brh=7
            pygame.draw.rect(screen,(18,28,52),(brx,bry,brw,brh),border_radius=3)
            pygame.draw.rect(screen,(*vc,185),(brx,bry,int((min(mv,100)/100)*brw),brh),border_radius=3)
            hist=metrics[mk].get_hist()[-(rw-14):]
            if len(hist)>1:
                mn2,mx2=min(hist),max(hist)+0.001
                pts=[(brx+int(k*(rw-14)/len(hist)),bry+brh+2+int((1-(v-mn2)/(mx2-mn2))*9))
                     for k,v in enumerate(hist)]
                pygame.draw.lines(screen,(*vc,65),False,pts,1)

        # Data stream
        r3y=r2.bottom+PAD; r3h=min(168,(H-r2.bottom-PAD*3)//2)
        if r3h > 38:
            r3=pygame.Rect(rx,r3y,rw,r3h); draw_panel(screen,r3,"DATA STREAM",fXS)
            vis=(r3h-22)//12
            for idx,hl in enumerate(list(hex_lines)[-vis:]):
                cy2=r3.y+22+idx*12
                if cy2>r3.bottom-3: break
                al=int(50+160*(idx/max(vis,1)))
                screen.blit(fXS.render(hl,True,(*ACCENT_DIM,al)),(r3.x+5,cy2))

        # Activity log
        r4y=(r3.bottom if r3h>38 else r2.bottom)+PAD; r4h=H-r4y-PAD
        if r4h > 45:
            r4=pygame.Rect(rx,r4y,rw,r4h); draw_panel(screen,r4,"ACTIVITY LOG",fXS)
            vis2=(r4h-22)//13
            for idx,(ts,msg,col) in enumerate(list(log_lines)[-vis2:]):
                ly=r4.y+22+idx*13
                if ly>r4.bottom-3: break
                screen.blit(fXS.render(ts,True,(*MUTED,110)),(r4.x+4,ly))
                screen.blit(fXS.render(msg,True,col),(r4.x+58,ly))

        # ── HUD bar ───────────────────────────────────────────────────────
        hud_items=[("MODEL",GROQ_MODEL[:14],ACCENT_DIM),
                   ("STATE",brain_state.upper(),sc),
                   ("VOICE","ON" if VOICE_AVAILABLE else "OFF",GREEN if VOICE_AVAILABLE else RED),
                   ("TTS","ON" if TTS_AVAILABLE else "OFF",GREEN if TTS_AVAILABLE else MUTED),
                   ("WAKE","HEY JARVIS",AMBER),
                   ("CMDS",str(len(cmd_history)),MUTED)]
        hx=L["lw"]+PAD*2; hy=PAD+62
        for label,val,col in hud_items:
            lb=fXS.render(label,True,MUTED); vb=fXS.render(val,True,col)
            screen.blit(lb,(hx,hy)); screen.blit(vb,(hx,hy+12))
            hx+=max(lb.get_width(),vb.get_width())+22
            if hx>L["bcx"]+L["bw"]//2-10: break

        # ── Corner brackets ───────────────────────────────────────────────
        def corner(x,y,sx,sy):
            pygame.draw.line(screen,(*ACCENT_DIM,90),(x,y),(x+sx*18,y),2)
            pygame.draw.line(screen,(*ACCENT_DIM,90),(x,y),(x,y+sy*18),2)
        corner(2,2,1,1); corner(W-3,2,-1,1)
        corner(2,H-3,1,-1); corner(W-3,H-3,-1,-1)

        # Subtle grid
        go=pygame.Surface((W,H),pygame.SRCALPHA)
        for gx in range(0,W,44): pygame.draw.line(go,(*ACCENT_DIM,4),(gx,0),(gx,H))
        for gy in range(0,H,44): pygame.draw.line(go,(*ACCENT_DIM,4),(0,gy),(W,gy))
        screen.blit(go,(0,0))

        pygame.display.flip()

    listener.stop(); waveform.stop(); cmd_q.put(None)
    pygame.quit()

if __name__ == "__main__":
    run_gui()