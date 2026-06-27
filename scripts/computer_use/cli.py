import argparse
import importlib.util
import json
import pathlib
import sys
import time


def _load(n):
    s = importlib.util.spec_from_file_location(n, pathlib.Path(__file__).resolve().parent / f"{n}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def journal_to_action_log(journal):
    """Transform loop journal entries to action_log shape for report.build_markdown.

    Loop journal entry: {"step", "state", "raw", "result", "screenshot"}
    where raw = {"name", "arguments": {...}, "id", ...}

    Action log entry: {"step", "action", "intent", "coord", "result", "produced_by_steps", "screenshot"}
    """
    log = []
    for e in journal:
        raw = e.get("raw") or {}
        args = raw.get("arguments") or {}

        # Infer coordinate string from action type
        if "x" in args:
            # click, tap-like actions
            coord = f"({args.get('x')},{args.get('y')})"
        elif "start_x" in args:
            # drag_and_drop, swipe-like actions
            coord = f"({args.get('start_x')},{args.get('start_y')})->({args.get('end_x')},{args.get('end_y')})"
        else:
            # scroll, input, or other actions without coordinates
            coord = "-"

        log.append({
            "step": e.get("step"),
            "action": raw.get("name", "?"),
            "intent": args.get("intent", ""),
            "coord": coord,
            "result": e.get("result", ""),
            "produced_by_steps": [e.get("step")],
            "screenshot": e.get("screenshot"),
        })
    return log


def parse_args(argv):
    p = argparse.ArgumentParser(prog="ios-visual-explore")
    p.add_argument("--udid", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("mission")
    p.add_argument("--max-steps", type=int, default=25, dest="max_steps")
    p.add_argument("--out", default=None, help="output directory (default: computer-use-runs/run-<ts>)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    p.add_argument("--orientation", choices=["portrait", "landscape"], default="portrait")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    preflight, executor_idb = _load("preflight"), _load("executor_idb")
    loop = _load("loop")
    dedup, report, critic, gemini = _load("dedup"), _load("report"), _load("critic"), _load("gemini")

    if args.dry_run:
        # single-turn planning probe (no actions executed)
        env = preflight.preflight(args.udid, args.bundle, args.orientation)
        executor = executor_idb.IdbExecutor(args.udid)
        client = gemini.ComputerUseClient()
        turn = client.start(args.mission, executor.screenshot())
        print(json.dumps({"dry_run": True, "planned": turn.action, "done": turn.done},
                         ensure_ascii=False, indent=2))
        return

    # F1: default env and result before setup so report can always be written
    env = {"platform": "ios", "udid": args.udid, "bundle_id": args.bundle,
           "orientation": args.orientation, "device_class": "unknown", "safe_area_source": "n/a"}
    result = {"journal": [], "status": "error", "baseline_screenshot": None}

    # F10: nanosecond timestamp avoids same-second run-dir collisions
    out = pathlib.Path(args.out or f"computer-use-runs/run-{time.time_ns()}")
    shots = out / "screenshots"
    out.mkdir(parents=True, exist_ok=True)
    shots.mkdir(parents=True, exist_ok=True)

    # F1: wrap setup AND loop.run in one guard so any failure still produces a report
    try:
        env = preflight.preflight(args.udid, args.bundle, args.orientation)
        executor = executor_idb.IdbExecutor(args.udid)
        safe = env["safe_area"]
        client = gemini.ComputerUseClient()
        result = loop.run(args.mission, executor, client, max_steps=args.max_steps,
                          safe_area=safe, screenshot_dir=str(shots),
                          foreground_check=lambda: preflight.is_app_foreground(
                              args.udid, env["baseline_app_label"], env["baseline_full_width"]))
    except Exception as exc:
        print(f"setup/loop failed: {exc}", file=sys.stderr)

    # Always build and write the report, even on abnormal failure
    try:
        journal = result["journal"]
        retained = []
        if result.get("baseline_screenshot"):
            retained.append(result["baseline_screenshot"])
        # F12: index-based first/last check — robust to copy/serialize
        for i, e in enumerate(journal):
            if e.get("screenshot") and dedup.should_retain(
                    e.get("result", "success"), i == 0, i == len(journal) - 1):
                retained.append(e["screenshot"])

        findings = critic.criticize(retained, client=gemini.VisionCritic()) if retained else []
        action_log = journal_to_action_log(journal)
        report_path = out / "report.md"
        report_path.write_text(report.build_markdown(args.mission, env, action_log, findings, result["status"]))
        print(report.text_summary(findings, str(report_path), str(shots), status=result["status"]))
    except Exception as exc:
        print(f"report generation failed: {exc}", file=sys.stderr)
