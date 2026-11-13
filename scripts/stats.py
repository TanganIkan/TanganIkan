#!/usr/bin/env python3
"""Render flat black/gray Y2K GitHub cards: stats.svg and defrag.svg (contribution calendar).

Usage: GITHUB_TOKEN=... python3 scripts/stats.py <github_login> <output_dir>
Runs in the "Generate profile assets" workflow; needs no third-party service.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

BG, PANEL, BAR = "#0a0a0a", "#121212", "#262626"
LINE, BORDER, DIM, MID = "#2e2e2e", "#3d3d3d", "#6e6e6e", "#9c9c9c"
TEXT, WHITE = "#d6d6d6", "#f4f4f4"
DISPLAY = "'Arial Black', 'Arial Bold', Gadget, Impact, sans-serif"
MONO = "'Courier New', Courier, 'Lucida Console', monospace"
LEVELS = {"NONE": "#1c1c1c", "FIRST_QUARTILE": "#3d3d3d", "SECOND_QUARTILE": "#6e6e6e",
          "THIRD_QUARTILE": "#a8a8a8", "FOURTH_QUARTILE": WHITE}

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositoriesContributedTo(contributionTypes: [COMMIT, PULL_REQUEST, ISSUE, REPOSITORY], first: 1) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}"""


# ------------------------------------------------------------------ data
def gql(login, token, after=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login, "after": after}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GraphQL error: {data['errors']}")
    return data["data"]["user"]


def streaks(days):
    """Current and longest streak (in days) inside the calendar window."""
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    current = 0
    rest = list(days)
    if rest and not rest[-1]["contributionCount"]:  # today may still be empty
        rest = rest[:-1]
    for d in reversed(rest):
        if not d["contributionCount"]:
            break
        current += 1
    return current, longest


def fetch(login, token):
    user = gql(login, token)
    repos = list(user["repositories"]["nodes"])
    page = user["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        nxt = gql(login, token, page["endCursor"])
        repos += nxt["repositories"]["nodes"]
        page = nxt["repositories"]["pageInfo"]

    langs = {}
    for repo in repos:
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in top) or 1

    cc = user["contributionsCollection"]
    cal = cc["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)
    return {
        "stats": [
            ("total stars", sum(r["stargazerCount"] for r in repos)),
            ("commits (1y)", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
            ("pull requests", cc["totalPullRequestContributions"]),
            ("public repos", user["repositories"]["totalCount"]),
            ("contributed to", user["repositoriesContributedTo"]["totalCount"]),
            ("current streak", f"{cur}d"),
            ("longest streak", f"{longest}d"),
        ],
        "langs": [(n, v / total) for n, v in top],
        "weeks": cal["weeks"],
        "year_total": cal["totalContributions"],
    }


# ------------------------------------------------------------------ svg helpers
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt(n):
    if isinstance(n, str):
        return n
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


DEFS = f"""
  <defs>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity="0.035"/></pattern>
    <pattern id="dither" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="1" height="1" fill="{BORDER}"/><rect x="2" y="2" width="1" height="1" fill="{BORDER}"/>
    </pattern>
    <pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="#1c1c1c"/><rect width="3" height="6" fill="{TEXT}"/>
    </pattern>
    <pattern id="check" width="4" height="4" patternUnits="userSpaceOnUse">
      <rect width="4" height="4" fill="#1c1c1c"/><rect width="2" height="2" fill="{MID}"/><rect x="2" y="2" width="2" height="2" fill="{MID}"/>
    </pattern>
    <pattern id="dots" width="5" height="5" patternUnits="userSpaceOnUse">
      <rect width="5" height="5" fill="#1c1c1c"/><rect x="1" y="1" width="2" height="2" fill="{TEXT}"/>
    </pattern>
    <path id="spark" d="M0,-1 C0.1,-0.1 0.1,-0.1 1,0 C0.1,0.1 0.1,0.1 0,1 C-0.1,0.1 -0.1,0.1 -1,0 C-0.1,-0.1 -0.1,-0.1 0,-1Z"/>
  </defs>"""
LANG_FILLS = [WHITE, "url(#hatch)", MID, "url(#check)", DIM, "url(#dots)"]


def spark(x, y, size, color, begin):
    lo = size * 0.25
    return (f'  <g transform="translate({x} {y})"><g transform="scale({size})">'
            f'<animateTransform attributeName="transform" type="scale" values="{lo};{size};{lo}" '
            f'dur="2.4s" begin="{begin}s" repeatCount="indefinite"/><use xlink:href="#spark" fill="{color}"/></g></g>')


def bevel(x, y, w, h, fill=PANEL, inset=False):
    hi, lo = ("#000000", "#4a4a4a") if inset else ("#4a4a4a", "#000000")
    return (f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'
            f'<path d="M{x},{y + h} L{x},{y} L{x + w},{y}" fill="none" stroke="{hi}" stroke-width="2"/>'
            f'<path d="M{x + w},{y} L{x + w},{y + h} L{x},{y + h}" fill="none" stroke="{lo}" stroke-width="2"/>')


def open_svg(w, h, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}">\n  <title>{esc(label)}</title>{DEFS}')


def window(x, y, w, h, title):
    out = [f"""  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
  <rect x="{x + 4}" y="{y + 4}" width="{w - 8}" height="30" fill="{BAR}"/>
  <rect x="{x + 4}" y="{y + 4}" width="{w - 8}" height="30" fill="url(#dither)"/>
  <g transform="translate({x + 20} {y + 19})"><use xlink:href="#spark" transform="scale(7)" fill="{WHITE}"/></g>
  <text x="{x + 36}" y="{y + 24}" font-family="{MONO}" font-size="15" font-weight="bold" fill="{WHITE}" letter-spacing="1">{esc(title)}</text>"""]
    for i, kind in enumerate(("min", "max", "close")):
        cx, cy = x + w - 96 + i * 28, y + 8
        out.append(bevel(cx, cy, 22, 20, fill="#2f2f2f"))
        out.append({"min": f'<line x1="{cx + 7}" y1="{cy + 15}" x2="{cx + 15}" y2="{cy + 15}" stroke="{WHITE}" stroke-width="2"/>',
                    "max": f'<rect x="{cx + 6}" y="{cy + 5}" width="10" height="9" fill="none" stroke="{WHITE}" stroke-width="1.6"/>',
                    "close": f'<path d="M{cx + 6.5},{cy + 5.5} L{cx + 15.5},{cy + 14.5} M{cx + 15.5},{cy + 5.5} L{cx + 6.5},{cy + 14.5}" stroke="{WHITE}" stroke-width="2"/>'}[kind])
    return "\n".join(out)


def panel(x, y, w, h, title):
    return bevel(x, y, w, h) + f"""
  <text x="{x + 20}" y="{y + 32}" font-family="{MONO}" font-size="17" font-weight="bold" fill="{WHITE}" letter-spacing="2">{esc(title)}</text>
  <line x1="{x + 20}" y1="{y + 46}" x2="{x + w - 20}" y2="{y + 46}" stroke="{BORDER}" stroke-width="2" stroke-dasharray="4 4"/>"""


# ------------------------------------------------------------------ stats card
def render_stats(d, login):
    W, H = 1200, 560
    wx, wy, ww, wh = 10, 10, 1180, 540
    out = [open_svg(W, H, f"GitHub stats for {login}"),
           window(wx, wy, ww, wh, f"stats.dat — C:\\{login.upper()}\\github")]

    px, py, pw, ph = 30, 60, 560, 296
    out.append(panel(px, py, pw, ph, "★ github_stats"))
    for i, (k, v) in enumerate(d["stats"]):
        yy = py + 82 + i * 30
        out.append(f"""  <text x="{px + 24}" y="{yy}" font-family="{MONO}" font-size="17" fill="{MID}">{esc(k)}</text>
  <text x="{px + 220}" y="{yy}" font-family="{MONO}" font-size="17" fill="{BORDER}">{'.' * 22}</text>
  <text x="{px + pw - 24}" y="{yy}" text-anchor="end" font-family="{DISPLAY}" font-size="19" fill="{WHITE}">{esc(fmt(v))}</text>""")

    lx, lw = 610, 560
    out.append(panel(lx, py, lw, ph, "★ top_languages"))
    bx, by, bw = lx + 24, py + 70, lw - 48
    out.append(bevel(bx - 3, by - 3, bw + 6, 24, fill="#050505", inset=True))
    cur = bx
    for i, (name, frac) in enumerate(d["langs"]):
        w = frac * bw
        out.append(f'  <rect x="{cur:.1f}" y="{by}" width="{max(w - 2, 0):.1f}" height="18" fill="{LANG_FILLS[i]}"/>')
        cur += w
    for i, (name, frac) in enumerate(d["langs"]):
        col, row = i % 2, i // 2
        xx, yy = bx + col * 262, by + 66 + row * 50
        out.append(f"""  <rect x="{xx}" y="{yy - 14}" width="16" height="16" fill="{LANG_FILLS[i]}" stroke="{BORDER}"/>
  <text x="{xx + 26}" y="{yy}" font-family="{MONO}" font-size="17" fill="{TEXT}">{esc(name)}</text>
  <text x="{xx + 240}" y="{yy}" text-anchor="end" font-family="{MONO}" font-size="16" fill="{DIM}">{frac * 100:.1f}%</text>""")

    ax, ay, aw, ah = 30, 372, 1140, 162
    out.append(panel(ax, ay, aw, ah, "★ weekly_activity"))
    out.append(f'  <text x="{ax + aw - 20}" y="{ay + 32}" text-anchor="end" font-family="{MONO}" font-size="15" fill="{MID}">'
               f'{fmt(d["year_total"])} contributions in the last year</text>')
    counts = [sum(day["contributionCount"] for day in w["contributionDays"]) for w in d["weeks"]] or [0]
    peak = max(counts) or 1
    rows, bh, gap = 8, 8, 3
    gx, gbottom = ax + 24, ay + ah - 16
    colw = (aw - 48) / len(counts)
    for i, c in enumerate(counts):
        lit = 0 if c == 0 else max(1, round(c / peak * rows))
        x = gx + i * colw
        for r in range(rows):
            y = gbottom - (r + 1) * (bh + gap) + gap
            fill = "#1a1a1a" if r >= lit else (WHITE if r == lit - 1 else DIM)
            out.append(f'  <rect x="{x:.1f}" y="{y}" width="{colw - 4:.1f}" height="{bh}" fill="{fill}"/>')

    out.append(spark(1150, 88, 9, WHITE, 0.4))
    out.append(f'  <rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" fill="url(#scan)"/>\n</svg>\n')
    return "\n".join(out)


# ------------------------------------------------------------------ defrag card
def render_defrag(d, login):
    W, H = 1200, 350
    wx, wy, ww, wh = 10, 10, 1180, 330
    weeks = d["weeks"]
    out = [open_svg(W, H, f"Contribution calendar for {login} drawn as a disk defragmenter"),
           window(wx, wy, ww, wh, "defrag.exe — drive C:\\contributions")]

    out.append(f"""  <text x="32" y="70" font-family="{MONO}" font-size="15" fill="{MID}">drive C: ── {fmt(d['year_total'])} contributions in the last year</text>
  <text x="1168" y="70" text-anchor="end" font-family="{MONO}" font-size="15" fill="{WHITE}">defragmenting...<animate attributeName="opacity" values="1;0.25;1" dur="1.4s" repeatCount="indefinite"/></text>""")

    cell, gap = 17, 3
    step = cell + gap
    gw = len(weeks) * step - gap
    gx = 30 + (1140 - gw) / 2
    gy = 116
    out.append(bevel(30, 84, 1140, 186, fill="#050505", inset=True))

    last_month = None
    for i, w in enumerate(weeks):
        days = w["contributionDays"]
        if not days:
            continue
        month = dt.date.fromisoformat(days[0]["date"]).strftime("%b").lower()
        if month != last_month and i < len(weeks) - 2:
            out.append(f'  <text x="{gx + i * step}" y="{gy - 10}" font-family="{MONO}" font-size="12" fill="{DIM}">{month}</text>')
            last_month = month
        start = dt.date.fromisoformat(days[0]["date"]).isoweekday() % 7  # first week can start mid-week
        for j, day in enumerate(days):
            row = start + j if i == 0 else j
            out.append(f'  <rect x="{gx + i * step:.1f}" y="{gy + row * step}" width="{cell}" height="{cell}" '
                       f'fill="{LEVELS.get(day["contributionLevel"], LEVELS["NONE"])}"/>')

    n = len(weeks)
    xs = ";".join(f"{gx + i * step - 3:.1f}" for i in range(n))
    out.append(f"""  <rect x="{gx - 3:.1f}" y="{gy - 3}" width="{cell + 6}" height="{7 * step + 3}" fill="none" stroke="{WHITE}" stroke-width="2">
    <animate attributeName="x" calcMode="discrete" values="{xs}" dur="{n * 0.12:.2f}s" repeatCount="indefinite"/>
  </rect>""")

    ly = 300
    items = [("unused", "NONE"), ("low", "FIRST_QUARTILE"), ("medium", "SECOND_QUARTILE"),
             ("high", "THIRD_QUARTILE"), ("max", "FOURTH_QUARTILE")]
    x = 32
    for label, lvl in items:
        out.append(f'  <rect x="{x}" y="{ly - 13}" width="15" height="15" fill="{LEVELS[lvl]}" stroke="{BORDER}"/>'
                   f'<text x="{x + 22}" y="{ly}" font-family="{MONO}" font-size="14" fill="{MID}">{label}</text>')
        x += 40 + len(label) * 9 + 22

    bx, bw, segs = 780, 388, 24
    sw = (bw - (segs - 1) * 3) / segs
    out.append(bevel(bx - 4, ly - 18, bw + 8, 26, fill="#050505", inset=True))
    vals = ";".join(f"{(sw + 3) * k:.1f}" for k in range(segs + 1)) + ";0"
    kts = ";".join(f"{k / segs * 0.9:.3f}" for k in range(segs + 1)) + ";1"
    out.append(f"""  <clipPath id="prog"><rect x="{bx}" y="{ly - 14}" width="{bw}" height="18">
    <animate attributeName="width" calcMode="discrete" values="{vals}" keyTimes="{kts}" dur="{n * 0.12:.2f}s" repeatCount="indefinite"/>
  </rect></clipPath>
  <g fill="{WHITE}" clip-path="url(#prog)">""")
    out.append("".join(f'<rect x="{bx + k * (sw + 3):.1f}" y="{ly - 14}" width="{sw:.1f}" height="18"/>' for k in range(segs)))
    out.append("  </g>")

    out.append(spark(1176, 88, 8, WHITE, 0.6))
    out.append(f'  <rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" fill="url(#scan)"/>\n</svg>\n')
    return "\n".join(out)


def write_all(d, login, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, svg in (("stats.svg", render_stats(d, login)), ("defrag.svg", render_defrag(d, login))):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", os.path.join(out_dir, name))


if __name__ == "__main__":
    login, out_dir = sys.argv[1], sys.argv[2]
    write_all(fetch(login, os.environ["GITHUB_TOKEN"]), login, out_dir)
