def _s(v):
    """Coerce to string and escape inline-image markdown."""
    return str(v if v is not None else "").replace('![', r'!\[')


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
        severity = str(finding.get('severity', ''))
        text = str(finding.get('text', ''))
        screenshot = str(finding.get('screenshot', ''))
        lines.append(f"- **{severity}** {text} — `{screenshot}`")
    return "\n".join(lines) + "\n"


def text_summary(findings, report_path, screenshot_dir, status=None) -> str:
    head = []
    if status is not None:
        head.append(f"Status: {_s(status)}")
    head += [f"Visuell utforsking ferdig. Full rapport: {report_path}",
             f"Skjermbilder: {screenshot_dir}", f"{len(findings)} funn:"]
    body = [f"- {_s(f.get('severity',''))} {_s(f.get('text',''))} ({_s(f.get('screenshot',''))})" for f in findings]
    return "\n".join(head + body)
