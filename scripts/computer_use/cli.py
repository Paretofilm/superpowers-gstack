import argparse
import importlib.util
import json
import pathlib
import time


def _load(n):
    s = importlib.util.spec_from_file_location(n, pathlib.Path(__file__).resolve().parent / f"{n}.py")
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


TOP_INSET = 50.0     # status-bar / dynamic island (punkter)
BOTTOM_INSET = 40.0  # home-indikator (punkter)


def parse_args(argv):
    p = argparse.ArgumentParser(prog="ios-visual-explore")
    p.add_argument("--udid", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("mission")
    p.add_argument("--max-steps", type=int, default=25, dest="max_steps")
    p.add_argument("--out", default=None, help="output-mappe (default: computer-use-runs/run-<ts>)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    preflight, executor_idb = _load("preflight"), _load("executor_idb")
    coords, loop = _load("coords"), _load("loop")
    dedup, report, critic, gemini = _load("dedup"), _load("report"), _load("critic"), _load("gemini")

    env = preflight.preflight(args.udid, args.bundle)   # resolve idb + launch app
    executor = executor_idb.IdbExecutor(args.udid)
    point_w, point_h = executor.coordinate_space()
    safe = coords.SafeArea(0, TOP_INSET, point_w, point_h - BOTTOM_INSET)
    client = gemini.ComputerUseClient()

    if args.dry_run:
        # single-turn planning-probe (ingen handling utføres)
        turn = client.start(args.mission, executor.screenshot())
        print(json.dumps({"dry_run": True, "planned": turn.action, "done": turn.done},
                         ensure_ascii=False, indent=2))
        return

    out = pathlib.Path(args.out or f"computer-use-runs/run-{int(time.time())}")
    shots = out / "screenshots"
    out.mkdir(parents=True, exist_ok=True)

    try:
        result = loop.run(args.mission, executor, client, max_steps=args.max_steps,
                          safe_area=safe, screenshot_dir=str(shots))
    finally:
        # teardown (spec §7): aldri destruktivt; sim-state forblir som den er.
        pass

    journal = result["journal"]
    last = len(journal)
    retained = []
    if result.get("baseline_screenshot"):
        retained.append(result["baseline_screenshot"])
    for e in journal:
        if e.get("screenshot") and dedup.should_retain(
                e.get("result", "success"), e["step"] == 1, e["step"] == last):
            retained.append(e["screenshot"])

    findings = critic.criticize(retained, client=gemini.VisionCritic()) if retained else []
    report_path = out / "report.md"
    report_path.write_text(report.build_markdown(args.mission, env, journal, findings, result["status"]))
    print(report.text_summary(findings, str(report_path), str(shots)))
