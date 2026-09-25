#!/usr/bin/env python3
"""Checks that every language Kodrix offers can still be installed.

For each Termux-sourced entry (in versions.json and in the app's built-in catalog),
resolves its packages plus all dependencies against the live Termux package index for
every CPU architecture Kodrix ships. Also checks that each Termux mirror answers.
Exits 1 and prints a Markdown report when something is broken.

Nothing here needs updating for new versions: versions come from the live index.
"""
import json, os, re, sys, urllib.request

ARCHES = ["aarch64", "arm", "x86_64", "i686"]
IGNORED = {"termux-tools", "termux-exec", "termux-keyring", "termux-am", "termux-am-socket",
           "termux-core", "termux-licenses", "apt", "dpkg"}
CATALOG_URL = os.environ.get("KODRIX_CATALOG_URL") or ("https://raw.githubusercontent.com/Zohaib8090/KodrixIDE/main/shared/src/androidMain/"
               "kotlin/com/kodrix/zohaib/runtime/BuiltinCatalog.kt")


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "kodrix-registry-check"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def parse_index(text):
    pkgs, provides, cur = {}, {}, {}
    def flush():
        if "Package" in cur:
            deps = ",".join(x for x in (cur.get("Pre-Depends"), cur.get("Depends")) if x)
            alts = [[re.sub(r"\(.*?\)", "", a).strip() for a in d.split("|")] for d in deps.split(",") if d.strip()]
            pkgs[cur["Package"]] = {"version": cur.get("Version", ""), "deps": alts}
            for p in cur.get("Provides", "").split(","):
                p = re.sub(r"\(.*?\)", "", p).strip()
                if p:
                    provides.setdefault(p, cur["Package"])
        cur.clear()
    for line in text.splitlines():
        if not line:
            flush()
        elif line[0] not in " \t" and ":" in line:
            k, v = line.split(":", 1)
            cur[k] = v.strip()
    flush()
    return pkgs, provides


def resolve(index, roots):
    pkgs, provides = index
    seen, missing, stack = set(), [], list(roots)
    while stack:
        name = stack.pop()
        if name in IGNORED or name in seen:
            continue
        real = name if name in pkgs else provides.get(name)
        if real is None:
            missing.append(name)
            continue
        seen.add(name); seen.add(real)
        for alts in pkgs[real]["deps"]:
            alts = [a for a in alts if a]
            if not alts or any(a in IGNORED for a in alts):
                continue
            pick = next((a for a in alts if a in pkgs or a in provides), alts[0])
            stack.append(pick)
    return missing


def termux_entries(tools, origin):
    for tool, obj in tools.items():
        if tool.startswith("_") or not isinstance(obj, dict):
            continue
        for v in obj.get("versions", []):
            if v.get("source") == "termux" and v.get("status", "available") != "unavailable":
                yield origin, tool, v["packages"]


def main():
    registry = json.load(open("versions.json"))
    mirrors = registry.get("_config", {}).get("termuxMirrors", ["https://packages-cf.termux.dev/apt/termux-main"])
    entries = list(termux_entries(registry, "versions.json"))

    catalog_note = ""
    try:
        src = fetch(CATALOG_URL)
        body = src.split('"""', 2)[1]
        catalog = json.loads(body.replace("%install%", "${install}").replace("%node%", "${node}"))
        for t in catalog.values():
            for v in t.get("versions", []):
                v.setdefault("source", "termux")
        entries += [e for e in termux_entries(catalog, "app catalog")]
    except Exception as e:  # repo private or file moved: report, but still check the rest
        catalog_note = f"\n_Couldn't read the app's built-in catalog ({e}); only versions.json was checked._\n"

    problems = []
    dead = []
    for m in mirrors:
        try:
            fetch(f"{m}/dists/stable/Release", timeout=30)
        except Exception as e:
            dead.append(f"- `{m}`: {e}")
    if len(dead) == len(mirrors):
        problems.append("**No package mirror answered.**\n" + "\n".join(dead))

    indexes = {}
    for arch in ARCHES:
        for m in mirrors:
            try:
                indexes[arch] = parse_index(fetch(f"{m}/dists/stable/main/binary-{arch}/Packages"))
                break
            except Exception:
                continue
        else:
            problems.append(f"**Couldn't download the package index for {arch} from any mirror.**")

    seen = set()
    not_offered = {}
    for origin, tool, packages in entries:
        key = (tool, tuple(packages))
        if key in seen:
            continue
        seen.add(key)
        for arch, index in indexes.items():
            main_pkg = packages[0]
            if arch != "aarch64" and main_pkg not in index[0] and main_pkg not in index[1]:
                # Not built for this CPU at all: the app simply doesn't offer it there.
                not_offered.setdefault(tool, []).append(arch)
                continue
            missing = resolve(index, packages)
            if missing:
                problems.append(f"- **{tool}** ({origin}) on {arch}: missing package(s) {', '.join(sorted(set(missing)))} "
                                f"(asked for {', '.join(packages)})")

    checked = f"Checked {len(seen)} language entries on {', '.join(indexes)}."
    if not_offered:
        checked += "\n\nNot available on some CPUs (hidden there by the app, nothing to fix): " + "; ".join(
            f"{t} ({', '.join(a)})" for t, a in sorted(not_offered.items()))
    if dead and len(dead) < len(mirrors):
        checked += "\n\nMirrors not answering (others did):\n" + "\n".join(dead)
    if problems:
        print("## Some Kodrix runtimes can't be installed\n\n" + "\n".join(problems) + "\n\n" + checked + catalog_note)
        sys.exit(1)
    print("All runtimes resolve. " + checked + catalog_note)


if __name__ == "__main__":
    main()
