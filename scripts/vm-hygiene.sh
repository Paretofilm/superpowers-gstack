#!/usr/bin/env bash
# SessionStart hook: report VM-rig leftovers in projects that opted into the rig.
#
# Reports, never acts. The rig's own rule is that no automation stops a guest — a VM
# you did not start may be someone else's run, and killing it loses their results.
# So this prints what it sees and stops there.
#
# Silent unless .gstack/e2e-executor is exactly `vm`. It ships to every plugin user,
# and a hook that talks in projects that never opted in is a hook people disable.

set -uo pipefail

# Not a git repo, or no pin, or pin is not `vm` → nothing to say.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
[ -f .gstack/e2e-executor ] || exit 0
[ "$(tr -d '[:space:]' < .gstack/e2e-executor 2>/dev/null)" = "vm" ] || exit 0

# The rig is a separate project. If it is not installed, this project pins `vm` on a
# machine that cannot honour it — the runner already prints that at run time, and
# repeating it at every session start would be noise.
command -v vm-lease >/dev/null 2>&1 || exit 0

findings=()

# Running guests. `pgrep -f` matches the pattern itself in some shells; -l gives the
# command line so the reader can tell which guest it is.
guests=$(pgrep -fl 'lume run' 2>/dev/null | grep -v 'vm-hygiene' || true)
[ -n "$guests" ] && findings+=("Running guest(s):"$'\n'"$guests")

# Orphaned virtualisation processes: the guest is gone but the XPC service stayed.
# These hold memory and are the reason a later boot fails with no obvious cause.
orphans=$(pgrep -fl 'Virtualization.VirtualMachine.xpc' 2>/dev/null | grep -v 'vm-hygiene' || true)
[ -n "$orphans" ] && findings+=("Orphaned Virtualization XPC process(es):"$'\n'"$orphans")

# Held leases. A lease outliving its run blocks the next dispatch until it expires.
leases=$(vm-lease status 2>/dev/null | grep -i 'busy\|held\|locked' || true)
[ -n "$leases" ] && findings+=("Held lease(s):"$'\n'"$leases")

[ ${#findings[@]} -eq 0 ] && exit 0

printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
printf ' VM E2E RIG: leftovers from a previous run\n'
printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
for f in "${findings[@]}"; do printf '  %s\n\n' "$f"; done
printf 'These may be a run in progress — check before touching anything.\n'
printf 'If they are stale: `vm-stop <name>` releases a guest; a lease frees itself when\n'
printf 'its holder exits. This hook never stops a VM on its own.\n'
exit 0
