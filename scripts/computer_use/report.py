def _s(v):
    """Coerce to string and escape inline-image markdown."""
    return str(v if v is not None else "").replace('![', r'!\[')


def build_markdown(mission, env, action_log, findings, status) -> str:
    # F5: _s() applied to all LLM/user-controlled interpolated fields
    lines = ["# Visuell utforsking — rapport", "",
             f"**Oppdrag:** {_s(mission)}", "",
             f"**Miljø:** {_s(env.get('platform'))} / UDID {_s(env.get('udid'))} / {_s(env.get('bundle_id'))} "
             f"/ {_s(env.get('orientation'))} / {_s(env.get('device_class'))} / safe-area: {_s(env.get('safe_area_source'))}",
             f"**Sluttstatus:** {_s(status)}", "", "## Handlingslogg", ""]
    for a in action_log:
        lines.append(f"- Steg {a['step']}: `{_s(a['action'])}` — {_s(a['intent'])} "
                     f"@ {_s(a.get('coord','-'))} → {_s(a['result'])} (skjerm fra steg {', '.join(_s(s) for s in a.get('produced_by_steps', []))})")
    lines += ["", "## Funn", ""]
    for finding in findings:
        severity = _s(finding.get('severity', ''))
        text = _s(finding.get('text', ''))
        screenshot = _s(finding.get('screenshot', ''))
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
