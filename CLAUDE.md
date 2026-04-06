# Superpowers + GStack Manual

## About
This repo contains the combined workflow manual for using Superpowers and GStack with Claude Code.

## Update monitoring
Run `./scripts/check-updates.sh` to check for updates to GStack, Superpowers, or Claude Code.

To set up daily checks in a Claude Code session:
```
Set up daily update checks for this project using the cron at 09:17 daily — run ./scripts/check-updates.sh and report if changes are found.
```

The cron auto-expires after 7 days. Re-create it in new sessions as needed.

## When updates are detected
1. Review what changed (the script reports new commits/versions)
2. Update relevant sections in the manual
3. Update VERSIONS.md with new version numbers
4. Commit and push
