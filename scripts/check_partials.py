#!/usr/bin/env python3
"""
Checks every modm-ext/* and modm-io/* submodule of a modm checkout:
- was the repository moved (then .gitmodules needs the new URL)?
- did its Update workflow (if any) run recently and succeed?
- what source files changed on its default branch since the commit modm pins,
  and does that change look like upstream moved files away?

Usage: check_partials.py <modm checkout>
Writes report.md and appends `flagged=` and `changed=` to $GITHUB_OUTPUT.
"""
import configparser, datetime, json, os, re, subprocess, sys

STALE_DAYS = 9  # Update jobs run weekly
# Update machinery, not sources. Keep in sync with bump.sh!
NO_SOURCE = re.compile(r"(update\.py|partial\.py|README\.md|\.gitignore|\.github/|tests?/|docs/|tools/)")
# Partials without an Update workflow on purpose
MANUAL = {
    "modm-ext/vl53-partial": "the ST zips are behind the myST login",
}


def gh(*args):
    out = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    if out.returncode:
        print(f"gh api {args[0]}: {out.stderr.strip()}", file=sys.stderr)
        return None
    return json.loads(out.stdout)


def partials(modm):
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(modm, ".gitmodules"))
    for section in cfg.sections():
        url, path = cfg[section]["url"], cfg[section]["path"]
        if re.search(r"github\.com/modm-(ext|io)/", url):
            repo = url.removesuffix(".git").split("github.com/")[1]
            sha = subprocess.check_output(["git", "-C", modm, "rev-parse", f"HEAD:{path}"], text=True).strip()
            yield repo, path, sha


def check(repo, sha):
    problems, notes = [], []
    info = gh(f"repos/{repo}")
    if info is None:
        return [f"repository {link(repo)} not found"], notes, 0
    if info["full_name"] != repo:
        problems.append(f"moved to {link(info['full_name'])}, update .gitmodules")
        repo = info["full_name"]
    branch = info["default_branch"]

    flows = gh(f"repos/{repo}/actions/workflows") or {"workflows": []}
    update = next((w for w in flows["workflows"] if w["path"] == ".github/workflows/update.yml"), None)
    if repo in MANUAL:
        notes.append(f"updated by hand: {MANUAL[repo]}")
    elif not update:
        notes.append("no Update workflow")
    else:
        if update["state"] != "active":
            problems.append(f"Update workflow {update['state']}")
        runs = gh(f"repos/{repo}/actions/workflows/{update['id']}/runs?per_page=1&branch={branch}")
        run = runs["workflow_runs"][0] if runs and runs["workflow_runs"] else None
        if not run:
            problems.append("no Update runs at all")
        else:
            age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(run["created_at"])
            if run["conclusion"] not in ("success", None):
                problems.append(f"[last run {run['conclusion']}]({run['html_url']})")
            if age.days > STALE_DAYS:
                problems.append(f"last run {age.days} days ago, schedule disabled?")

    cmp = gh(f"repos/{repo}/compare/{sha}...{branch}")
    if cmp is None:
        problems.append(f"cannot compare pinned {sha[:8]} with {branch}")
        return problems, notes, 0
    # changes of the update machinery and file mode only changes are not bumped in modm (see bump.sh)
    files = [f for f in cmp.get("files", []) if not NO_SOURCE.match(f["filename"])
             and not (f["status"] == "modified" and f["changes"] == 0)]
    if not files:
        return problems, notes, 0
    removed = [f["filename"] for f in files if f["status"] == "removed"]
    renamed = [f"{f['previous_filename']} -> {f['filename']}" for f in files if f["status"] == "renamed"]
    adds = sum(f["additions"] for f in files)
    dels = sum(f["deletions"] for f in files)
    if removed:
        problems.append(f"{len(removed)} files removed: " + ", ".join(removed[:10]))
    if renamed:
        problems.append(f"{len(renamed)} files renamed: " + ", ".join(renamed[:10]))
    if dels > 200 and dels > 3 * adds:
        problems.append(f"mostly deletions: +{adds} -{dels}")
    msgs = "; ".join(f"[{c['commit']['message'].splitlines()[0]}]({c['html_url']})" for c in cmp["commits"][-5:])
    notes.append(f"[{cmp['ahead_by']} commits]({cmp['html_url']}), {len(files)} files, +{adds} -{dels}: {msgs}")
    return problems, notes, cmp["ahead_by"]


def link(repo, sha=None):
    if sha:
        return f"[`{sha[:8]}`](https://github.com/{repo}/commit/{sha})"
    return f"[{repo}](https://github.com/{repo})"


def main(modm):
    lines, flagged, changed = ["# modm submodules", ""], False, False
    for repo, path, sha in sorted(partials(modm)):
        problems, notes, ahead = check(repo, sha)
        flagged |= bool(problems)
        changed |= bool(ahead)
        status = "❌" if problems else ("🔄" if ahead else "✅")
        lines.append(f"- {status} **{link(repo)}** (`{path}` @ {link(repo, sha)})")
        lines += [f"  - {p}" for p in problems + notes]
    report = "\n".join(lines) + "\n"
    open("report.md", "w").write(report)
    print(report)
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as f:
            f.write(f"flagged={str(flagged).lower()}\nchanged={str(changed).lower()}\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
