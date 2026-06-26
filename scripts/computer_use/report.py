def build_markdown(mission, env, action_log, findings, status) -> str:
    lines = ["# Visuell utforsking — rapport", "",
             f"**Oppdrag:** {mission}", "",
             f"**Miljø:** {env.get('platform')} / UDID {env.get('udid')} / {env.get('bundle_id')}",
             f"**Sluttstatus:** {status}", "", "## Handlingslogg", ""]
    for a in action_log:
        lines.append(f"- Steg {a['step']}: `{a['action']}` — {a['intent']} "
                     f"@ {a.get('coord','-')} → {a['result']} (skjerm fra steg {', '.join(str(s) for s in a.get('produced_by_steps', []))})")
    lines += ["", "## Funn", ""]
    for finding in findings:
        lines.append(f"- **{finding['severity']}** {finding['text']} — `{finding['screenshot']}`")
    return "\n".join(lines) + "\n"


def text_summary(findings, report_path, screenshot_dir) -> str:
    head = [f"Visuell utforsking ferdig. Full rapport: {report_path}",
            f"Skjermbilder: {screenshot_dir}", f"{len(findings)} funn:"]
    body = [f"- {f['severity']} {f['text'].replace('![', r'!\[')} ({f['screenshot'].replace('![', r'!\[')})" for f in findings]
    return "\n".join(head + body)
