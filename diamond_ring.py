#!/usr/bin/env python3
"""Rotating diamond ring rendered as ASCII art.

Usage:
    python diamond_ring.py                 # animate in the terminal (Ctrl+C to quit)
    python diamond_ring.py --gif ring.gif  # export an animated GIF
    python diamond_ring.py --frame         # print a single frame
Options: --width N --height N --frames N --no-color

A tiny software 3D renderer: a faceted brilliant-cut gem on a gold torus band,
z-buffered, flat-shaded gem facets (so they flash as it turns) and a smooth
shaded band, then mapped to characters.
"""
import argparse
import math
import random
import sys
import time

BAND_RAMP = " .,-~:;=!*#$@"
GEM_RAMP = " .:+*oO#@"


# ---------- tiny vector helpers ----------
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0]/l, a[1]/l, a[2]/l)


def rot(p, ay, ax):
    """Rotate point about Y by ay, then about X by ax."""
    x, y, z = p
    c, s = math.cos(ay), math.sin(ay)
    x, z = x*c + z*s, -x*s + z*c
    c, s = math.cos(ax), math.sin(ax)
    y, z = y*c - z*s, y*s + z*c
    return (x, y, z)


# ---------- geometry ----------
def build_band(R=1.0, r=0.17, nu=44, nv=14):
    """Torus whose hole axis is Z (ring stands upright, gem on +Y)."""
    verts, normals = [], []
    for i in range(nu):
        u = 2*math.pi*i/nu
        for j in range(nv):
            v = 2*math.pi*j/nv
            cx, cy = R*math.cos(u), R*math.sin(u)
            nx, ny, nz = math.cos(v)*math.cos(u), math.cos(v)*math.sin(u), math.sin(v)
            verts.append((cx + r*nx, cy + r*ny, r*nz*1.3))
            normals.append((nx, ny, nz))
    tris = []
    for i in range(nu):
        for j in range(nv):
            a = i*nv + j
            b = ((i+1) % nu)*nv + j
            c = ((i+1) % nu)*nv + (j+1) % nv
            d = i*nv + (j+1) % nv
            tris += [(a, b, c), (a, c, d)]
    return verts, normals, tris


def build_gem(cy=1.38, girdle=0.68, table=0.40, crown_h=0.27, pav_h=0.58, n=8):
    """Brilliant-cut: table (top), crown, girdle, pavilion down to a point."""
    rings = lambda rad, y, off=0.0: [
        (rad*math.cos(2*math.pi*(k+off)/n), y, rad*math.sin(2*math.pi*(k+off)/n))
        for k in range(n)]
    tbl = rings(table, cy + crown_h)
    gir = rings(girdle, cy, 0.5)
    apex = (0.0, cy - pav_h, 0.0)
    top = (0.0, cy + crown_h, 0.0)
    faces = []  # (triangle verts, is_table)
    for k in range(n):
        k2 = (k+1) % n
        faces.append(((top, tbl[k2], tbl[k]), True))             # table
        faces.append(((tbl[k], tbl[k2], gir[k]), False))         # crown
        faces.append(((gir[k], tbl[k2], gir[k2]), False))        # star
        faces.append(((gir[k], gir[k2], apex), False))           # pavilion
    return faces


# ---------- rasterizer ----------
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.clear()

    def clear(self):
        self.z = [[-1e9]*self.w for _ in range(self.h)]
        self.ch = [[" "]*self.w for _ in range(self.h)]
        self.col = [[0]*self.w for _ in range(self.h)]  # 0 none,1 gold,2 gem,3 sparkle,4 star

    def tri(self, p0, p1, p2, shade, ramp, color):
        """p = (sx, sy, z). shade(l0,l1,l2)->brightness 0..1 by barycentric weights."""
        minx = max(0, int(min(p0[0], p1[0], p2[0])))
        maxx = min(self.w-1, int(max(p0[0], p1[0], p2[0])) + 1)
        miny = max(0, int(min(p0[1], p1[1], p2[1])))
        maxy = min(self.h-1, int(max(p0[1], p1[1], p2[1])) + 1)
        den = (p1[1]-p2[1])*(p0[0]-p2[0]) + (p2[0]-p1[0])*(p0[1]-p2[1])
        if abs(den) < 1e-9:
            return
        for y in range(miny, maxy+1):
            for x in range(minx, maxx+1):
                px, py = x + 0.5, y + 0.5
                l0 = ((p1[1]-p2[1])*(px-p2[0]) + (p2[0]-p1[0])*(py-p2[1])) / den
                l1 = ((p2[1]-p0[1])*(px-p2[0]) + (p0[0]-p2[0])*(py-p2[1])) / den
                l2 = 1 - l0 - l1
                if l0 < 0 or l1 < 0 or l2 < 0:
                    continue
                z = l0*p0[2] + l1*p1[2] + l2*p2[2]
                if z > self.z[y][x]:
                    b = max(0.0, min(1.0, shade(l0, l1, l2)))
                    self.z[y][x] = z
                    self.ch[y][x] = ramp[int(b*(len(ramp)-1))]
                    self.col[y][x] = color(b) if callable(color) else color


LIGHT = norm((-0.5, 0.7, 0.8))
VIEW = (0.0, 0.0, 1.0)


def render(t, w, h, stars):
    cv = Canvas(w, h)
    ay = t * 2*math.pi          # spin
    ax = -0.35 + 0.08*math.sin(t*2*math.pi)   # gentle tilt/bob
    scale = h * 0.27
    aspect = 2.0                # chars are ~2x taller than wide
    cx, cy = w/2, h/2 + 0.15*scale

    def project(p):
        x, y, z = rot(p, ay, ax)
        return (cx + x*scale*aspect, cy - y*scale, z), (x, y, z)

    # band
    bv, bn, bt = BAND_CACHE
    proj = [project(v) for v in bv]
    nrm = [rot(n, ay, ax) for n in bn]
    for a, b, c in bt:
        pa, pb, pc = proj[a][0], proj[b][0], proj[c][0]
        if (pb[0]-pa[0])*(pc[1]-pa[1]) - (pb[1]-pa[1])*(pc[0]-pa[0]) > 0:
            continue  # back-face (screen y is down)
        na, nb, nc = nrm[a], nrm[b], nrm[c]

        def shade(l0, l1, l2, na=na, nb=nb, nc=nc):
            n = norm((l0*na[0]+l1*nb[0]+l2*nc[0], l0*na[1]+l1*nb[1]+l2*nc[1],
                      l0*na[2]+l1*nb[2]+l2*nc[2]))
            diff = max(0.0, dot(n, LIGHT))
            hv = norm((LIGHT[0], LIGHT[1], LIGHT[2]+1))
            spec = max(0.0, dot(n, hv)) ** 24
            return 0.12 + 0.6*diff + 0.5*spec
        cv.tri(pa, pb, pc, shade, BAND_RAMP, 1)

    # gem
    for k, (tri3, is_table) in enumerate(GEM_FACES):
        pts = [project(p) for p in tri3]
        s = [q[0] for q in pts]
        w3 = [q[1] for q in pts]
        n = norm(cross(sub(w3[1], w3[0]), sub(w3[2], w3[0])))
        if n[2] < 0:
            n = (-n[0], -n[1], -n[2])
        if (s[1][0]-s[0][0])*(s[2][1]-s[0][1]) - (s[1][1]-s[0][1])*(s[2][0]-s[0][0]) > 0:
            s[1], s[2] = s[2], s[1]
        diff = max(0.0, dot(n, LIGHT))
        hv = norm((LIGHT[0], LIGHT[1], LIGHT[2]+1))
        spec = max(0.0, dot(n, hv)) ** 14
        # per-facet "fire": facets flash as they sweep past the light
        fire = 0.5 + 0.5*math.sin(t*2*math.pi*3 + k*1.7)
        b = 0.25 + 0.35*diff + 0.9*spec + (0.15 + 0.2*spec)*fire
        if is_table:
            b += 0.15
        sparkle = b > 0.95
        col = 3 if sparkle else 2
        cv.tri(s[0], s[1], s[2], lambda *_ , b=b: b, GEM_RAMP, col)

    # twinkling stars around the ring
    for (sx, sy, ph) in stars:
        tw = math.sin(t*2*math.pi*2 + ph)
        if tw > 0.55:
            x, y = int(sx*w), int(sy*h)
            if 0 <= x < w and 0 <= y < h and cv.ch[y][x] == " ":
                cv.ch[y][x] = "*" if tw > 0.85 else "+"
                cv.col[y][x] = 4
                if tw > 0.93:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        xx, yy = x+dx, y+dy
                        if 0 <= xx < w and 0 <= yy < h and cv.ch[yy][xx] == " ":
                            cv.ch[yy][xx] = "-" if dy == 0 else "|"
                            cv.col[yy][xx] = 4
    return cv


BAND_CACHE = build_band()
GEM_FACES = build_gem()
_rng = random.Random(7)
STARS = [(_rng.random(), _rng.random(), _rng.random()*6.28) for _ in range(34)]

ANSI = {0: "", 1: "\x1b[38;5;178m", 2: "\x1b[38;5;123m", 3: "\x1b[1;38;5;231m", 4: "\x1b[38;5;229m"}
RGB = {0: (255, 255, 255), 1: (230, 175, 60), 2: (130, 225, 255), 3: (255, 255, 255), 4: (255, 245, 170)}


def to_text(cv, color=True):
    lines = []
    for y in range(cv.h):
        if not color:
            lines.append("".join(cv.ch[y]).rstrip())
            continue
        out, last = [], None
        for x in range(cv.w):
            c = cv.col[y][x] if cv.ch[y][x] != " " else 0
            if c != last:
                out.append("\x1b[0m" + ANSI[c])
                last = c
            out.append(cv.ch[y][x])
        lines.append("".join(out) + "\x1b[0m")
    return "\n".join(lines)


def save_gif(path, w, h, frames, fps=20):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("DejaVuSansMono.ttf", 12)
    except OSError:
        font = ImageFont.load_default()
    cw, chh = 7, 14
    imgs = []
    for f in range(frames):
        cv = render(f/frames, w, h, STARS)
        im = Image.new("RGB", (w*cw, h*chh), (6, 6, 14))
        d = ImageDraw.Draw(im)
        for y in range(h):
            for x in range(w):
                c = cv.ch[y][x]
                if c != " ":
                    d.text((x*cw, y*chh), c, fill=RGB[cv.col[y][x]], font=font)
        imgs.append(im)
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=int(1000/fps), loop=0)
    print(f"saved {path} ({frames} frames)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=72)
    ap.add_argument("--height", type=int, default=34)
    ap.add_argument("--frames", type=int, default=60, help="frames per rotation (GIF)")
    ap.add_argument("--fps", type=int, default=20)
    ap.add_argument("--gif", metavar="FILE")
    ap.add_argument("--frame", action="store_true", help="print one frame and exit")
    ap.add_argument("--no-color", action="store_true")
    a = ap.parse_args()

    if a.gif:
        save_gif(a.gif, a.width, a.height, a.frames, a.fps)
        return
    if a.frame:
        print(to_text(render(0.12, a.width, a.height, STARS), not a.no_color))
        return
    sys.stdout.write("\x1b[2J\x1b[?25l")
    try:
        t0 = time.time()
        while True:
            t = ((time.time() - t0) / 4.0) % 1.0   # 4 s per rotation
            sys.stdout.write("\x1b[H" + to_text(render(t, a.width, a.height, STARS), not a.no_color) + "\n")
            sys.stdout.flush()
            time.sleep(1/30)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\n")


if __name__ == "__main__":
    main()
