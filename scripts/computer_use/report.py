def build_markdown(mission, env, action_log, findings, status) -> str:
    lines = [f"# Visuell utforsking — rapport", "",
             f"**Oppdrag:** {mission}", "",
             f"**Miljø:** {env.get('platform')} / UDID {env.get('udid')} / {env.get('bundle_id')}",
             f"**Sluttstatus:** {status}", "", "## Handlingslogg", ""]
    for a in action_log:
        lines.append(f"- Steg {a['step']}: `{a['action']}` — {a['intent']} "
                     f"@ {a.get('coord','-')} → {a['result']} (skjerm fra steg {a.get('produced_by_steps')})")
    lines += ["", "## Funn", ""]
    for f in findings:
        lines.append(f"- **{f['severity']}** {f['text']} — `{f['screenshot']}`")
    return "\n".join(lines) + "\n"


def text_summary(findings, report_path, screenshot_dir) -> str:
    head = [f"Visuell utforsking ferdig. Full rapport: {report_path}",
            f"Skjermbilder: {screenshot_dir}", f"{len(findings)} funn:"]
    body = [f"- {f['severity']} {f['text']} ({f['screenshot']})" for f in findings]
    return "\n".join(head + body)
