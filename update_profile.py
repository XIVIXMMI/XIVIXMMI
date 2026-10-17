"""Regenerate dark_mode.svg / light_mode.svg with live GitHub stats.

Runs daily via GitHub Actions. Stdlib only, no dependencies.
"""
import html
import json
import os
import urllib.request
from datetime import date, datetime, timezone

USER = "XIVIXMMI"
BIRTHDAY = date(2001, 9, 14)
JOINED_YEAR = 2022  # account creation year, never changes
W = 56  # info column width in characters

# ── Edit your info here ──────────────────────────────────────────────────────
# Each section is (title, [(key, value), ...]). Title None = no heading line.
# Dots and the right-aligned values are computed automatically; just keep
# len(key) + len(value) <= W - 5 (the script stops with an error otherwise).
# "{uptime}" is replaced with your age in years.
SECTIONS = [
    (None, [
        ("OS", "macOS, Ubuntu"),
        ("Uptime", "{uptime}"),
        ("Host", "Ho Chi Minh City, VN"),
        ("Kernel", "Back-End Developer"),
        ("Editor", "Vim, VS Code"),
    ]),
    (None, [
        ("Languages.Programming", "Java, Python"),
        ("Languages.Real", "Vietnamese, English, Japanese"),
        ("Hobbies", "Gym"),
    ]),
    (None, [
        ("Stack.Backend", "Spring Boot, FastAPI"),
        ("Stack.Database", "Postgres, Redis"),
        ("Stack.Tools", "Docker, Linux, Git"),
    ]),
    ("Goal", [
        ("Now", "Backend @ fintech / banking"),
        ("Next", "DevOps / SRE"),
    ]),
    ("Contact", [
        ("Email", "nguyen.le.programmer@gmail.com"),
        ("LinkedIn", "in/nguyen-le-dev"),
    ]),
]
# ─────────────────────────────────────────────────────────────────────────────

ART = r"""
          :---===+=::.  .
        -=++=--:-=----:..
      .-===----::::-:-:..::.
     .:----:-::-----:::-:--:
    .:=-.:..:-::--:::.====:=.
    :==-::-=-=+++-.-+:-===:-:
    .-=-===++##=-:=#%*:-=-:
    +%*++#@@@@+*#%@@@@%=-+#%+
    *@%#%@@%%%@@@@@%%%%@###@*
     +%%##@@@@@@@@@@@@@%###+.
         :%@@@@@@@@@@@@-
          :*%@@@@@@@@*-
             =+*##*+=:
            =%##**#%+%=
      .--.:.*@@@@@@%%@%...-:
     *%@+..:=@#=*#+:-%*.: +@%#-
   .#@@@=-:--=   :....---.-@@@%:
   *@@@@=:.:::::: :::-::..:@@@@#
  =@@@@@-.:::.. .....:..   %@@@@+
"""

# GITHUB_TOKEN (Actions) counts public + private contributions; an optional
# ACCESS_TOKEN (PAT with repo scope) also sees private repos for repos/stars/LOC.
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN") or ""
PRIV_TOKEN = os.environ.get("ACCESS_TOKEN") or TOKEN


def gh(url, payload=None, token=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": f"Bearer {token or TOKEN}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or "{}")


def graphql(query, variables=None, token=None):
    resp = gh("https://api.github.com/graphql", {"query": query, "variables": variables or {}}, token)
    if resp.get("errors"):
        raise RuntimeError(resp["errors"])
    return resp["data"]


def years_old(b, t):
    return t.year - b.year - ((t.month, t.day) < (b.month, b.day))


def fetch_stats():
    yr_aliases = "\n".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y + 1}-01-01T00:00:00Z")'
        " { totalCommitContributions restrictedContributionsCount }"
        for y in range(JOINED_YEAR, datetime.now(timezone.utc).year + 1)
    )
    contrib = graphql(f'query {{ user(login: "{USER}") {{ {yr_aliases} }} }}')["user"]
    commits = sum(
        v["totalCommitContributions"] + v["restrictedContributionsCount"]
        for v in contrib.values()
    )
    u = graphql(f"""
    query {{
      user(login: "{USER}") {{
        id
        followers {{ totalCount }}
        repositories(first: 100, ownerAffiliations: OWNER) {{
          totalCount
          nodes {{ name stargazerCount isFork }}
        }}
        repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) {{
          totalCount
        }}
      }}
    }}""", token=PRIV_TOKEN)["user"]
    stats = {
        "followers": u["followers"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "commits": commits,
    }
    stats.update(loc([n["name"] for n in u["repositories"]["nodes"] if not n["isFork"]], u["id"]))
    return stats


LOC_QUERY = """
query($owner: String!, $name: String!, $id: ID!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { target { ... on Commit {
      history(first: 100, author: {id: $id}, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes { additions deletions }
      }
    } } }
  }
}"""


def loc(repo_names, user_id):
    # walk own commits on each default branch; REST stats/contributors keeps answering 202 in Actions
    add = rem = 0
    for name in repo_names:
        cursor = None
        try:
            while True:
                ref = graphql(LOC_QUERY, {"owner": USER, "name": name, "id": user_id, "cursor": cursor}, token=PRIV_TOKEN)["repository"]["defaultBranchRef"]
                if ref is None:
                    break  # empty repo
                h = ref["target"]["history"]
                add += sum(n["additions"] for n in h["nodes"])
                rem += sum(n["deletions"] for n in h["nodes"])
                if not h["pageInfo"]["hasNextPage"]:
                    break
                cursor = h["pageInfo"]["endCursor"]
        except Exception as e:
            print(f"loc {name}: {e}")
    return {"loc_add": add, "loc_del": rem, "loc": add - rem}


PALETTES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "art": "#8b949e", "h": "#58a6ff",
             "k": "#ffa657", "v": "#a5d6ff", "d": "#484f58", "g": "#3fb950", "r": "#f85149"},
    "light": {"bg": "#ffffff", "border": "#d0d7de", "art": "#57606a", "h": "#0969da",
              "k": "#953800", "v": "#0a3069", "d": "#afb8c1", "g": "#1a7f37", "r": "#cf222e"},
}


def kv(key, val, width=W):
    dots = "." * max(width - len(key) - len(str(val)) - 3, 1)
    return [(f"{key}: ", "k"), (dots + " ", "d"), (str(val), "v")]


def kv2(k1, v1, k2, v2):
    return kv(k1, v1, 30) + [(" | ", "d")] + kv(k2, v2, 23)


def rule(title=""):
    label = f"─ {title} " if title else ""
    return [(label, "h"), ("─" * (W - len(label)), "d")]


def info_lines(s):
    n = lambda x: f"{x:,}"
    uptime = f"{years_old(BIRTHDAY, date.today())} years"
    lines = [[(f"{USER.lower()}@github ", "h"), ("─" * (W - len(USER) - 8), "d")]]
    for title, rows in SECTIONS:
        lines.append([])
        if title:
            lines.append(rule(title))
        lines += [kv(k, v.replace("{uptime}", uptime)) for k, v in rows]
    return lines + [
        [],
        rule("GitHub Stats"),
        kv2("Repos", f"{s['repos']} {{Contributed: {s['contributed']}}}", "Stars", n(s["stars"])),
        kv2("Commits", n(s["commits"]), "Followers", n(s["followers"])),
        [("Lines of Code: ", "k"), (n(s["loc"]), "v"), (" ( ", "d"),
         (n(s["loc_add"]) + "++", "g"), (", ", "d"), (n(s["loc_del"]) + "--", "r"), (" )", "d")],
    ]


INFO_TOP, INFO_LH, ART_LH = 40, 19, 15


def render(mode, stats):
    p = PALETTES[mode]
    info = info_lines(stats)
    art = ART.strip("\n").split("\n")
    height = INFO_TOP + len(info) * INFO_LH + 10
    art_top = (height - len(art) * ART_LH) // 2 + 10  # vertically centre the art
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="840" height="{height}" viewBox="0 0 840 {height}" '
        f'font-family="Consolas, Menlo, monospace" font-size="13px">',
        f'<rect x="0.5" y="0.5" width="839" height="{height - 1}" rx="10" fill="{p["bg"]}" stroke="{p["border"]}"/>',
    ]
    for i, line in enumerate(art):
        out.append(f'<text x="25" y="{art_top + i * ART_LH}" fill="{p["art"]}" xml:space="preserve">{html.escape(line)}</text>')
    for i, segs in enumerate(info):
        if not segs:
            continue
        spans = "".join(f'<tspan fill="{p[c]}">{html.escape(t)}</tspan>' for t, c in segs)
        out.append(f'<text x="390" y="{INFO_TOP + i * INFO_LH}" xml:space="preserve">{spans}</text>')
    out.append("</svg>")
    return "\n".join(out)


def selfcheck():
    assert years_old(date(2001, 9, 14), date(2026, 9, 13)) == 24
    assert years_old(date(2001, 9, 14), date(2026, 9, 14)) == 25
    for _, rows in SECTIONS:
        for k, v in rows:
            if len(k) + len(v) > W - 5:
                raise SystemExit(f"Too long for one line ({len(k) + len(v)} > {W - 5} chars): {k}: {v}")


if __name__ == "__main__":
    selfcheck()
    stats = fetch_stats()
    print("stats:", stats)
    for mode in PALETTES:
        with open(f"{mode}_mode.svg", "w", encoding="utf-8") as f:
            f.write(render(mode, stats))
    print("wrote dark_mode.svg, light_mode.svg")
