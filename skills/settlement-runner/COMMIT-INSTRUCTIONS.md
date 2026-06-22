# Installing settlement-runner on Paperclip (via GitHub)

Paperclip's "Add a skill source" takes a GitHub repo URL / skills.sh command / local
path — not a file upload. So commit this folder to a Git repo, then paste the URL.

## Option A — add to the existing TAP skills repo (recommended; ask William for the repo)
Copy this folder into the repo under `skills/settlement-runner/`:

    skills/settlement-runner/
      SKILL.md
      scripts/settlement_inputs.py
      scripts/prorate.py        (deprecated stub, kept for reference)

    git add skills/settlement-runner
    git commit -m "Add settlement-runner skill (full rent, real landlord, SP-bill utilities)"
    git push

Then in Paperclip → Agents → Finance Lead → Skills → Add a skill source → paste the repo URL.

## Option B — standalone repo
Create a new GitHub repo, put SKILL.md at the root (with scripts/ beside it), push,
and paste that repo URL into the same dialog.

## Verify after install
Trigger: "Run all co-living settlements for May 2026" on Finance Lead.
Cross-check Suites @ Sophia → net must be S$42,291.83 (ties to Finance's file).
