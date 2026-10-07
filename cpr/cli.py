"""Command line: `cpr review <PR number>`."""

import argparse
import json
import os
import sys

from cpr import VERSION, checks as checks_mod, diffview, model as model_mod, render
from cpr.ingest import bundle as bundle_mod
from cpr.ingest.clone import CloneError
from cpr.ingest.github import PRNotFound
from cpr.net import NetError
from cpr.triage import triage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_report(bundle, work_dir, offline=False, log=print):
    results = checks_mod.run_all(bundle)
    tri = triage(bundle)
    number, sha = bundle["pr"]["number"], bundle["pr"]["head_sha"]
    dv_cache = os.path.join(bundle_mod.pr_dir(work_dir, number), sha, "diffview.json")
    if offline:
        if os.path.exists(dv_cache):
            with open(dv_cache) as f:
                dv = json.load(f)
        else:
            dv = diffview.unavailable("No cached diff view for this head sha (offline).")
    else:
        log("rendering diff view with ide-explain")
        dv = diffview.render(bundle, results)
        os.makedirs(os.path.dirname(dv_cache), exist_ok=True)
        with open(dv_cache, "w") as f:
            json.dump(dv, f)
    docs = render.load_docs()
    return model_mod.build(bundle, results, tri, docs, dv)


def cmd_review(args):
    work_dir = os.path.abspath(args.work_dir)
    log = (lambda *a: None) if args.quiet else (lambda m: print(f"  {m}", file=sys.stderr))
    try:
        if args.offline:
            bundle = bundle_mod.load_cached(work_dir, args.pr)
        else:
            bundle = bundle_mod.ingest(args.pr, work_dir, log=log)
            bundle_mod.save(bundle, work_dir)
        model = build_report(bundle, work_dir, offline=args.offline, log=log)
        out = args.out or os.path.join(ROOT, "reports", str(args.pr), "index.html")
        path = render.write(model, out)
    except PRNotFound as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (bundle_mod.IngestError, NetError, CloneError, render.RenderError, model_mod.ModelError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.model_out:
        with open(args.model_out, "w") as f:
            json.dump(model, f, indent=1)
    rec = model["recommendation"]
    print(f"#{args.pr}: {rec['label']} · triage {model['triage']['rating']}")
    print(path)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cpr", description="Review an apache/cassandra pull request.")
    parser.add_argument("--version", action="version", version=f"cpr {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)
    rv = sub.add_parser("review", help="review one PR and write an HTML report")
    rv.add_argument("pr", type=int, help="apache/cassandra PR number")
    rv.add_argument("--offline", action="store_true", help="re-render from the cached ingest; no network")
    rv.add_argument("--out", help="output path (default reports/<PR>/index.html)")
    rv.add_argument("--work-dir", default=os.path.join(ROOT, ".work"), help="cache and clone directory")
    rv.add_argument("--model-out", help="also write the report model JSON here")
    rv.add_argument("--quiet", action="store_true")
    rv.set_defaults(func=cmd_review)
    args = parser.parse_args(argv)
    return args.func(args)
