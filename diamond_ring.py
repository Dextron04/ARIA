#!/usr/bin/env python3
"""Diamond ring made of letters -- animated ASCII art (own implementation).

Timeline (26 s loop):
   0.3- 3.3  the band grows up from the bottom in a stream of sparks
   3.3- 4.3  the setting appears
   4.0- 6.0  the diamond glimmers into place
   6.5-14.5  the ring turns a full revolution, glints + orbiting sparkle trails
  14.8-17.3  "Will u marry me? - Tushin" is written under the ring, letter by letter
  18.3-19.3  the ring dissolves away
  19.4-26.0  big block-letter "WILL U MARRY ME? / MARYAM", a pulsing heart and - Tushin
  25.0-26.0  fade to black, loop

Usage:
    python diamond_ring.py --gif ring.gif     # export animated GIF
    python diamond_ring.py                    # play in a (256-colour) terminal
    python diamond_ring.py --frame 9.0        # print one frame at t=9.0s
"""
import argparse
import math
import random
import sys
import time

COLS, ROWS = 108, 64          # character grid
CELL_W, CELL_H = 6, 9         # pixels per character in the GIF
FLOOR = 54                    # row where the ring touches the "floor"
DURATION = 26.0
FPS = 20

# letters/digits ordered roughly by ink density
RAMP = " .,:;ilI1tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"


def smooth(a, b, t):
    t = max(0.0, min(1.0, (t - a) / (b - a)))
    return t * t * (3 - 2 * t)


def hrand(x, y, s=0):
    """Deterministic per-cell random in [0,1)."""
    return (((x * 73856093) ^ (y * 19349663) ^ (s * 83492791)) & 0xFFFF) / 65536.0


# ---------- vectors ----------
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0]/l, a[1]/l, a[2]/l)


def rot(p, ay, ax=0.0, az=0.0):
    x, y, z = p
    if az:
        c, s = math.cos(az), math.sin(az)
        x, y = x*c - y*s, x*s + y*c
    c, s = math.cos(ay), math.sin(ay)
    x, z = x*c + z*s, -x*s + z*c
    c, s = math.cos(ax), math.sin(ax)
    y, z = y*c - z*s, y*s + z*c
    return (x, y, z)


# ---------- geometry ----------
def build_band(R=1.0, rr=0.17, rz=0.26, nu=60, nv=12):
    """Torus; axis = Z, so the ring stands upright. u=90deg is the top."""
    verts, normals = [], []
    for i in range(nu):
        u = 2*math.pi*i/nu
        for j in range(nv):
            v = 2*math.pi*j/nv
            nx, ny, nz = math.cos(v)*math.cos(u), math.cos(v)*math.sin(u), math.sin(v)
            verts.append(((R + rr*math.cos(v))*math.cos(u), (R + rr*math.cos(v))*math.sin(u), rz*nz))
            normals.append(norm((nx, ny, nz/1.6)))
    tris = []
    for i in range(nu):
        i2 = (i+1) % nu
        # angular distance from the bottom (u = -90deg) for the grow-in effect
        u_mid = 2*math.pi*(i+0.5)/nu
        d = abs(((u_mid + math.pi/2 + math.pi) % (2*math.pi)) - math.pi)
        for j in range(nv):
            j2 = (j+1) % nv
            a, b, c, e = i*nv+j, i2*nv+j, i2*nv+j2, i*nv+j2
            tris += [(a, b, c, d), (a, c, e, d)]
    return verts, normals, tris


def build_setting(y0=1.08, y1=1.40, r0=0.20, r1=0.46, n=12):
    verts, normals = [], []
    for k in range(n):
        a = 2*math.pi*k/n
        verts += [(r0*math.cos(a), y0, r0*math.sin(a)), (r1*math.cos(a), y1, r1*math.sin(a))]
        normals += [norm((math.cos(a), 0.5, math.sin(a)))]*2
    tris = []
    for k in range(n):
        k2 = (k+1) % n
        a, b, c, d = 2*k, 2*k+1, 2*k2, 2*k2+1
        tris += [(a, b, c, 0), (b, d, c, 0)]
    return verts, normals, tris


def build_gem(cy=1.40, girdle=0.62, table=0.36, crown_h=0.34, pav_h=0.34, n=8):
    ring = lambda rad, y, off=0.0: [
        (rad*math.cos(2*math.pi*(k+off)/n), y, rad*math.sin(2*math.pi*(k+off)/n)) for k in range(n)]
    tbl, gir = ring(table, cy+crown_h), ring(girdle, cy, 0.5)
    apex, top = (0.0, cy-pav_h, 0.0), (0.0, cy+crown_h, 0.0)
    faces = []
    for k in range(n):
        k2 = (k+1) % n
        faces += [(top, tbl[k2], tbl[k]), (tbl[k], tbl[k2], gir[k]),
                  (gir[k], tbl[k2], gir[k2]), (gir[k], gir[k2], apex)]
    return faces


BAND, SETTING, GEM = build_band(), build_setting(), build_gem()
_r = random.Random(11)
DUST = [(_r.randrange(COLS), _r.randrange(ROWS), _r.random()*6.28, _r.random()) for _ in range(150)]

LIGHT = norm((-0.45, 0.65, 0.75))
HALF = norm((LIGHT[0], LIGHT[1], LIGHT[2]+1))


# ---------- canvas ----------
class Canvas:
    def __init__(self):
        self.z = [[-1e9]*COLS for _ in range(ROWS)]
        self.ch = [[" "]*COLS for _ in range(ROWS)]
        self.b = [[0.0]*COLS for _ in range(ROWS)]
        self.glints = 0

    def put(self, x, y, z, b, ch, force=False):
        if 0 <= x < COLS and 0 <= y < ROWS and (force or z > self.z[y][x]):
            self.z[y][x] = z
            self.ch[y][x] = ch
            self.b[y][x] = max(0.0, min(1.0, b))

    def letter(self, x, y, b):
        b = max(0.0, min(1.0, b))
        f = b*(len(RAMP)-1) + (hrand(x, y, 5) - 0.5)*2.2   # jitter -> "letter texture"
        return RAMP[max(1, min(len(RAMP)-1, int(f)))]

    def tri(self, p0, p1, p2, shade, reveal=1.0):
        minx, maxx = max(0, int(min(p0[0], p1[0], p2[0]))), min(COLS-1, int(max(p0[0], p1[0], p2[0]))+1)
        miny, maxy = max(0, int(min(p0[1], p1[1], p2[1]))), min(ROWS-1, int(max(p0[1], p1[1], p2[1]))+1)
        den = (p1[1]-p2[1])*(p0[0]-p2[0]) + (p2[0]-p1[0])*(p0[1]-p2[1])
        if abs(den) < 1e-9:
            return
        for y in range(miny, maxy+1):
            for x in range(minx, maxx+1):
                if reveal < 1.0 and hrand(x, y, 3) > reveal:
                    continue
                px, py = x+0.5, y+0.5
                l0 = ((p1[1]-p2[1])*(px-p2[0]) + (p2[0]-p1[0])*(py-p2[1])) / den
                l1 = ((p2[1]-p0[1])*(px-p2[0]) + (p0[0]-p2[0])*(py-p2[1])) / den
                l2 = 1 - l0 - l1
                if l0 < 0 or l1 < 0 or l2 < 0:
                    continue
                z = l0*p0[2] + l1*p1[2] + l2*p2[2]
                if z > self.z[y][x]:
                    b = shade(l0, l1, l2)
                    self.z[y][x] = z
                    self.b[y][x] = max(0.0, min(1.0, b))
                    self.ch[y][x] = self.letter(x, y, b)

    def text(self, x, y, s, b=0.4):
        for i, c in enumerate(s):
            if 0 <= x+i < COLS and 0 <= y < ROWS and c != " ":
                self.ch[y][x+i], self.b[y][x+i] = c, b


# ---------- scene ----------
def proj_static(p):
    """Orbit points use a slow independent camera (not the ring's spin)."""
    scale = ROWS*0.25
    x, y, z = rot(p, 0.0, -0.16)
    return (COLS/2 + x*scale*1.5, FLOOR - (y + 1.12)*scale, z), (x, y, z)


def render(t):
    cv = Canvas()
    gem_in = smooth(4.0, 6.0, t)
    ring_p = smooth(0.3, 3.3, t)
    set_in = smooth(3.3, 4.3, t)
    spin = smooth(6.5, 14.5, t)
    ay = spin * 2*math.pi
    ax = -0.16 + 0.03*math.sin(t*1.3)
    scale = ROWS*0.25
    xs = scale*1.5                     # characters are taller than wide

    def proj(p):
        x, y, z = rot(p, ay, ax)
        return (COLS/2 + x*xs, FLOOR - (y + 1.12)*scale, z), (x, y, z)

    # --- band (grows up from the bottom) ---
    front = math.pi * ring_p * 1.02
    bv, bn, bt = BAND
    P = [proj(v)[0] for v in bv]
    N = [rot(n, ay, ax) for n in bn]
    for a, b, c, d in bt:
        if d > front:
            continue
        pa, pb, pc = P[a], P[b], P[c]
        if (pb[0]-pa[0])*(pc[1]-pa[1]) - (pb[1]-pa[1])*(pc[0]-pa[0]) > 0:
            continue
        na, nb, nc = N[a], N[b], N[c]
        edge = max(0.0, 1 - (front - d)/0.35) if front < math.pi*1.01 else 0.0

        def shade(l0, l1, l2, na=na, nb=nb, nc=nc, edge=edge):
            n = norm((l0*na[0]+l1*nb[0]+l2*nc[0], l0*na[1]+l1*nb[1]+l2*nc[1], l0*na[2]+l1*nb[2]+l2*nc[2]))
            diff = max(0.0, dot(n, LIGHT))
            spec = max(0.0, dot(n, HALF)) ** 30
            rx, ry = 2*n[2]*n[0], 2*n[2]*n[1]
            env = 0.5 + 0.5*math.sin(5*ry + 1.5*rx + 1.0)
            rim = (1 - abs(n[2])) ** 2
            return (0.12 + 0.30*diff + 0.32*env + 0.55*spec + 0.35*rim) + edge*0.5
        cv.tri(pa, pb, pc, shade)

    # sparks flying off the growing front
    if 0.02 < ring_p < 0.995:
        for s in range(46):
            side = 1 if s % 2 else -1
            u = -math.pi/2 + side*front*(0.97 + 0.06*hrand(s, 1, 2))
            rr = 1 + (hrand(s, 2, int(t*10)) - 0.5)*0.55
            wp = (rr*math.cos(u), rr*math.sin(u), (hrand(s, 3, int(t*10)) - 0.5)*0.4)
            (sx, sy, sz), _ = proj(wp)
            cv.put(int(sx), int(sy), sz + 1, 0.55 + 0.45*hrand(s, 4, int(t*20)), "*+.'`"[s % 5])
            cv.glints += 1

    # --- setting (basket) ---
    if set_in > 0:
        sv, sn, st = SETTING
        SP = [proj(v)[0] for v in sv]
        SN = [rot(n, ay, ax) for n in sn]
        for a, b, c, _ in st:
            pa, pb, pc = SP[a], SP[b], SP[c]
            if (pb[0]-pa[0])*(pc[1]-pa[1]) - (pb[1]-pa[1])*(pc[0]-pa[0]) > 0:
                continue
            na, nb, nc = SN[a], SN[b], SN[c]

            def shade(l0, l1, l2, na=na, nb=nb, nc=nc):
                n = norm((l0*na[0]+l1*nb[0]+l2*nc[0], l0*na[1]+l1*nb[1]+l2*nc[1], l0*na[2]+l1*nb[2]+l2*nc[2]))
                spec = max(0.0, dot(n, HALF)) ** 20
                return 0.22 + 0.35*max(0.0, dot(n, LIGHT)) + 0.6*spec + 0.2*(1 - abs(n[2]))
            cv.tri(pa, pb, pc, shade, reveal=set_in)

    # --- gem ---
    bursts = []
    for k, tri3 in enumerate(GEM):
        pts = [proj(p) for p in tri3]
        s = [q[0] for q in pts]
        w3 = [q[1] for q in pts]
        n = norm(cross(sub(w3[1], w3[0]), sub(w3[2], w3[0])))
        if n[2] < 0:
            n = (-n[0], -n[1], -n[2])
        if (s[1][0]-s[0][0])*(s[2][1]-s[0][1]) - (s[1][1]-s[0][1])*(s[2][0]-s[0][0]) > 0:
            s[1], s[2] = s[2], s[1]
        diff = max(0.0, dot(n, LIGHT))
        spec = max(0.0, dot(n, HALF)) ** 12
        fire = 0.5 + 0.5*math.sin(t*7 + k*1.9 + ay*2)
        facet = ((k * 37) % 7) / 7.0            # each facet has its own tone
        b = 0.18 + 0.38*facet + 0.25*diff + 0.50*spec + 0.35*fire
        if k % 4 == 0:
            b += 0.12
        cv.tri(s[0], s[1], s[2], lambda *_, b=b: b, reveal=gem_in)
        if b > 1.0 and gem_in > 0.9:
            cx = sum(q[0] for q in s)/3
            cy = sum(q[1] for q in s)/3
            bursts.append((b, cx, cy, max(q[2] for q in s)))

    # starbursts on the gem (one always glows on top, plus the brightest facets)
    top, _ = proj((0, 1.76, 0))
    bursts.sort(reverse=True)
    pulse = 0.6 + 0.4*math.sin(t*5)
    allb = [(1.6*pulse, top[0], top[1] - 1, top[2] + 5)] + bursts[:2]
    if gem_in > 0.4:
        for b, bx, by, bz in allb:
            ln = (3 + 6*min(0.5, max(0.0, b - 0.9))) * gem_in
            cv.put(int(bx), int(by), bz + 5, 1.0, "*", True)
            for i in range(1, int(ln*1.6)):
                f = 1 - i/(ln*1.6)
                for dx, dy, c in ((i, 0, "-"), (-i, 0, "-")):
                    cv.put(int(bx)+dx, int(by)+dy, bz + 5, 0.9*f, c, True)
            for i in range(1, int(ln*1.4)):
                f = 1 - i/(ln*1.4)
                for dy in (i, -i):
                    cv.put(int(bx), int(by)+dy, bz + 5, 0.9*f, "|", True)
            for i in range(1, int(ln*0.55)):
                f = 1 - i/(ln*0.55)
                for dx, dy, c in ((i*2, i, "\\"), (-i*2, -i, "\\"), (i*2, -i, "/"), (-i*2, i, "/")):
                    cv.put(int(bx)+dx, int(by)+dy, bz + 5, 0.75*f, c, True)
            cv.glints += 1

    # random glints on the metal
    if ring_p > 0.9:
        for y in range(ROWS):
            for x in range(COLS):
                if cv.b[y][x] > 0.78 and cv.ch[y][x] != " " and hrand(x, y, int(t*12)) > 0.965:
                    cv.ch[y][x] = "+"
                    cv.b[y][x] = 1.0
                    cv.glints += 1

    # --- orbiting sparkle trails ---
    orb = smooth(8.0, 10.0, t) * (1 - smooth(14.5, 15.5, t))
    if orb > 0:
        for o, (tilt, spd) in enumerate(((0.62, 1.0), (-0.62, -0.8))):
            prec = t*0.35*(1 if o == 0 else -1)
            for dots in range(0, 360, 6):          # faint dotted path
                a = math.radians(dots)
                p = (2.05*math.cos(a), 0.55*math.sin(a) + 0.35, 0.9*math.sin(a))
                p = rot(p, prec, 0.0, tilt)
                (sx, sy, sz), _ = proj_static(p)
                cv.put(int(sx), int(sy), sz, 0.22*orb, ".")
            for k in range(7):                       # comets with tails
                for tail in range(14):
                    a = t*1.6*spd + k*2*math.pi/7 - tail*0.055*(1 if spd > 0 else -1)
                    p = (2.05*math.cos(a), 0.55*math.sin(a) + 0.35, 0.9*math.sin(a))
                    p = rot(p, prec, 0.0, tilt)
                    (sx, sy, sz), _ = proj_static(p)
                    f = (1 - tail/14.0) * orb
                    cv.put(int(sx), int(sy), sz, 0.25 + 0.75*f, "o.:'`,*"[min(tail//2, 6)] if tail else "*")
                    if tail == 0:
                        cv.glints += 1

    # --- reflection on the floor ---
    for y in range(FLOOR+1, FLOOR+5):
        src = 2*FLOOR - y + 1
        fade_r = 0.22 * (1 - (y - FLOOR)/5.0)
        for x in range(COLS):
            if cv.ch[y][x] == " " and 0 <= src < ROWS and cv.ch[src][x] != " ":
                cv.ch[y][x] = cv.ch[src][x]
                cv.b[y][x] = cv.b[src][x]*fade_r

    # --- love note under the ring, written letter by letter ---
    write = smooth(14.8, 17.3, t)
    lines = (("W i l l  u  m a r r y  m e ?", 59), ("- T u s h i n", 61))
    slots = [(x0 + i, row, c) for text, row in lines
             for x0 in [COLS//2 - len(text)//2] for i, c in enumerate(text) if c != " "]
    n_shown = int(write * len(slots) + 0.999) if write > 0 else 0
    for k, (x, row, c) in enumerate(slots[:n_shown]):
        newest = (k == n_shown - 1 and write < 1.0)
        if newest:                                   # fresh letter flashes as a little star
            cv.glints += 1
            for dx, dy, g in ((-1, 0, "-"), (1, 0, "-"), (0, -1, "|"), (0, 1, "|")):
                if cv.ch[row+dy][x+dx] == " ":
                    cv.ch[row+dy][x+dx], cv.b[row+dy][x+dx] = g, 0.6
        cv.ch[row][x] = "*" if newest else c
        cv.b[row][x] = 1.0 if newest else (0.95 if n_shown - k < 4 else 0.85)

    # --- the ring (and note) dissolve away ---
    dissolve(cv, 1.0 - smooth(18.3, 19.3, t), 9)

    # --- HUD (only while the ring is around) ---
    if t < 19.3:
        letters = sum(1 for row in cv.ch for c in row if c != " ")
        cv.text(COLS-9, 1, f"t {t:05.2f}s", 0.45)
        cv.text(4, ROWS-5, "ARIA - ascii diamond ring", 0.33)
        cv.text(4, ROWS-4, f"rotation {math.degrees(ay) % 360:06.2f}   glints {cv.glints:4d}", 0.33)
        cv.text(4, ROWS-3, f"letters {letters:,}", 0.33)

    # --- the proposal in big letters, after the ring is gone ---
    if t > 19.4:
        draw_proposal(cv, t)

    # --- dust (twinkling stars, always there) ---
    for (x, y, ph, br) in DUST:
        tw = 0.5 + 0.5*math.sin(t*2.2 + ph)
        if cv.ch[y][x] == " " and tw > 0.45:
            cv.ch[y][x] = ".'`,:"[int(br*5) % 5] if tw < 0.9 else "+"
            cv.b[y][x] = 0.12 + 0.25*tw*br

    dissolve(cv, 1.0 - smooth(25.0, 26.0, t), 11)     # final fade, then loop
    return cv


def dissolve(cv, fade, seed):
    if fade >= 1.0:
        return
    for y in range(ROWS):
        for x in range(COLS):
            if cv.ch[y][x] != " " and hrand(x, y, seed) > fade:
                cv.ch[y][x] = " "
            cv.b[y][x] *= fade


# 5x7 block font for the proposal
FONT = {
    "W": ["X...X", "X...X", "X...X", "X.X.X", "X.X.X", "XX.XX", "X...X"],
    "I": ["XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "XXXXX"],
    "L": ["X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"],
    "U": ["X...X", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."],
    "M": ["X...X", "XX.XX", "X.X.X", "X.X.X", "X...X", "X...X", "X...X"],
    "A": [".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"],
    "R": ["XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"],
    "Y": ["X...X", "X...X", ".X.X.", "..X..", "..X..", "..X..", "..X.."],
    "E": ["XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"],
    "?": [".XXX.", "X...X", "....X", "...X.", "..X..", ".....", "..X.."],
    " ": ["....."]*7,
}


def big_text(word, x0, y0, sx, t, reveal, seed):
    """Return list of (x, y, char, brightness) for `word` in the block font.
    Each lit pixel is filled with the word's own letters; a soft shadow is added."""
    cells = []
    gw = 5*sx + sx                                 # glyph advance
    total = len(word)*gw - sx
    x0 = COLS//2 - total//2 if x0 is None else x0
    for gi, ch in enumerate(word):
        for ry, row in enumerate(FONT[ch]):
            for rx, px in enumerate(row):
                if px != "X":
                    continue
                for ox in range(sx):
                    x, y = x0 + gi*gw + rx*sx + ox, y0 + ry
                    r = hrand(x, y, seed)
                    if r > reveal:
                        continue
                    new = reveal < 1.0 and r > reveal - 0.06       # just appeared -> flash
                    wave = 0.5 + 0.5*math.sin(x*0.22 - t*4.0 + y*0.3)
                    bright = 0.62 + 0.38*wave
                    body = "@" if bright > 0.8 else ("%" if bright > 0.7 else "#")   # solid, so the shape reads
                    cells.append((x, y, "*" if new else body, 1.0 if new else bright, False))
                    cells.append((x+1, y+1, ":", 0.2, True))                           # shadow
    return cells


def draw_proposal(cv, t):
    k = t - 19.4
    lines = (("WILL U MARRY ME?", None, 9, 1, 0.0, 1), ("MARYAM", None, 21, 2, 1.2, 2))
    shadows = []
    for word, x0, y0, sx, delay, seed in lines:
        reveal = smooth(delay, delay + 2.2, k)
        if reveal <= 0:
            continue
        for x, y, c, b, sh in big_text(word, x0, y0, sx, t, reveal, seed):
            if not (0 <= x < COLS and 0 <= y < ROWS):
                continue
            if sh:
                if cv.ch[y][x] == " ":
                    shadows.append((x, y, c, b))
            else:
                cv.ch[y][x], cv.b[y][x] = c, b
    for x, y, c, b in shadows:
        if cv.ch[y][x] == " ":
            cv.ch[y][x], cv.b[y][x] = c, b

    # pulsing heart, filled with letters
    heart = smooth(2.6, 3.6, k)
    if heart > 0:
        pulse = 1.0 + 0.07*max(0.0, math.sin(t*6.0))
        sy, cy = 5.2*pulse, 41
        sx = sy*1.6
        for y in range(cy-8, cy+8):
            for x in range(COLS//2-22, COLS//2+23):
                u, v = (x - COLS/2)/sx, -(y - cy)/sy
                if (u*u + v*v - 1)**3 - u*u*v**3 < 0 and hrand(x, y, 4) < heart:
                    shade = 0.55 + 0.45*max(0.0, v/1.3) + 0.15*math.sin(t*5 + x*0.3)
                    cv.ch[y][x] = "ILOVEYOU"[(x + 3*y) % 8]
                    cv.b[y][x] = min(1.0, shade)

    # signature, written letter by letter
    sig = smooth(3.4, 4.8, k)
    text = "- T u s h i n"
    x0 = COLS//2 - len(text)//2
    n_shown = int(sig*len(text) + 0.999) if sig > 0 else 0
    for i, c in enumerate(text[:n_shown]):
        if c != " ":
            cv.ch[52][x0+i], cv.b[52][x0+i] = c, 1.0
    if sig > 0.9 and math.sin(t*5) > 0.6:               # tiny sparkle by the signature
        cv.ch[52][x0+len(text)+1], cv.b[52][x0+len(text)+1] = "*", 1.0


# ---------- output ----------
def gray(b):
    return int(35 + 220*max(0.0, min(1.0, b)))


def to_ansi(cv):
    out = []
    for y in range(ROWS):
        line = []
        for x in range(COLS):
            c = cv.ch[y][x]
            line.append(" " if c == " " else f"\x1b[38;5;{232 + min(23, int(cv.b[y][x]*23))}m{c}")
        out.append("".join(line) + "\x1b[0m")
    return "\n".join(out)


def save_gif(path, fps=FPS, duration=DURATION):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 9)
    except OSError:
        font = ImageFont.load_default()
    n = int(duration*fps)
    frames = []
    for f in range(n):
        cv = render(f/fps)
        im = Image.new("L", (COLS*CELL_W, ROWS*CELL_H), 0)
        d = ImageDraw.Draw(im)
        for y in range(ROWS):
            for x in range(COLS):
                c = cv.ch[y][x]
                if c != " ":
                    d.text((x*CELL_W, y*CELL_H), c, fill=gray(cv.b[y][x]), font=font)
        frames.append(im)
        if f % 40 == 0:
            print(f"  frame {f}/{n}", flush=True)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000/fps),
                   loop=0, optimize=True)
    print(f"saved {path}: {n} frames @ {fps} fps")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gif", metavar="FILE")
    ap.add_argument("--frame", type=float, metavar="T")
    ap.add_argument("--fps", type=int, default=FPS)
    a = ap.parse_args()
    if a.gif:
        save_gif(a.gif, a.fps)
    elif a.frame is not None:
        print(to_ansi(render(a.frame)))
    else:
        sys.stdout.write("\x1b[2J\x1b[?25l")
        try:
            t0 = time.time()
            while True:
                sys.stdout.write("\x1b[H" + to_ansi(render((time.time()-t0) % DURATION)) + "\n")
                sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        finally:
            sys.stdout.write("\x1b[0m\x1b[?25h\n")


if __name__ == "__main__":
    main()
