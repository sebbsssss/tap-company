# Surfacing the Finance Quickstart inside Paperclip

The quickstart is a markdown file in the imported company package, but Finance staff won't naturally browse to `docs/finance-quickstart.md` on disk. You need to make it discoverable from inside Paperclip's web UI. Three patterns, from simplest to most polished:

## Option 1 — Standing "📖 Read Me" issue (recommended, simplest)

Create one long-lived issue that's the first thing every Finance user sees in their Paperclip issue list. Pin it if Paperclip supports pinning.

**Setup (one-time, ~2 minutes):**

1. In Paperclip web UI, create a new issue:
   - **Title:** `📖 Finance Quickstart — Read me first`
   - **Assignee:** leave unassigned (it's documentation, not work)
   - **Status:** keep as Open forever
   - **Body:** copy-paste the entire contents of `docs/finance-quickstart.md` into the issue body. Markdown renders natively in Paperclip's issue view.
2. (If your Paperclip version supports it) **Pin the issue** so it stays at the top of the issue list.
3. (If your Paperclip version supports labels) Add a `documentation` label so it's filterable.

**Maintenance:** when the quickstart updates (e.g. new template added), edit the issue body to match. Or just paste a single line saying "see latest at [link to the markdown file on the VM or GitHub]" and keep the doc canonical.

**Why this works:** every Finance user opens Paperclip and lands on the issue list. They see the pinned read-me at the top with the open-book icon. One click to read. Zero new infrastructure.

## Option 2 — Company description (most "official-feeling")

Every Paperclip company has a description field on the Company Settings page. Most users see this on first visit.

**Setup:**

1. **Company Settings → Edit description**
2. Paste a short version of the quickstart — the "I want to..." lookup table is the most useful 30-second view
3. Link to the full quickstart issue from Option 1, or to the markdown file path on the VM

**Pros:** feels like canonical org documentation. Shows up on the Company page that everyone sees.
**Cons:** Company description is usually a short field — won't fit the full quickstart. So this is best PAIRED with Option 1.

## Option 3 — Paperclip Project with the quickstart as the project description

If Paperclip's "Projects" feature lets you write a long description, create a Project called "Finance Workflows" and put the quickstart in its description.

**Setup:**

1. **Projects → New Project**
2. Name: `Finance Workflows`
3. Goal: `Make settlements, bank rec, CFO briefs, and AR chases predictable and reviewable.`
4. Description: paste the quickstart
5. Add Yee Chin, AR, settlements staff as project members

Project pages give you a permanent landing spot AND let you scope issues to the project (so the Finance team has its own issue queue separate from Ops or strategic CEO issues).

**Pros:** organisational — clean separation of Finance work from everything else. Long description supported.
**Cons:** depends on whether your Paperclip version has Projects with description fields — verify in your install before committing.

## My recommendation

**Do Option 1 first** (5 minutes, definitely works). When you've used it for a week and know what Finance actually looks at, decide whether you also want Option 2 (Company description) or Option 3 (Project) as a more polished home for it.

## Bonus — make the CEO agent maintain the read-me

If you want zero maintenance: add a HEARTBEAT step to the CEO agent that:
1. Reads `docs/finance-quickstart.md` on each heartbeat
2. Compares it to the body of the "📖 Finance Quickstart" issue
3. If they differ, updates the issue body to match the markdown file

This way, the markdown file in git (or on the VM) stays canonical, and the in-Paperclip read-me is always in sync. Add this snippet to `agents/ceo/HEARTBEAT.md` under a new step:

```markdown
## 9. Sync read-me docs to standing issues

Once per day (e.g. only if hour-of-day == 6):
- Read `${COMPANY_ROOT}/docs/finance-quickstart.md`
- Compare to the body of the standing issue titled "📖 Finance Quickstart — Read me first"
- If different, update the issue body via `POST /api/issues/{id}` with the new body
- Same pattern for `docs/issue-templates.md` → "📋 Issue templates — copy from here"
- Same for `docs/xero-export-guide.md` → "📊 Xero export guide"

Three standing issues, one heartbeat sync. No human maintenance.
```

## What about issue templates inside Paperclip?

Some Paperclip versions let you save issue templates that pre-fill the body when a user creates a new issue (similar to GitHub issue templates). If yours does:

1. **Settings → Issue templates → New template**
2. Name each one after a workflow: "Settlement request", "Bank rec triage", "CFO Brief", "AR Chase batch", etc.
3. Paste the corresponding template from `docs/issue-templates.md` into the body
4. When Yee Chin clicks "New Issue", she picks a template from a dropdown and the body is pre-filled

This is the smoothest UX — no copy-paste from a separate doc, just pick the template and fill in the placeholders. **If your Paperclip version has this feature, use it.** If not, Option 1's standing read-me issue is the next best thing.

## Quickstart for the Finance team to find their way in

Once everything's wired:

1. Yee Chin / AR / Faisal log in to Paperclip web UI
2. Land on issue list — first thing they see is `📖 Finance Quickstart — Read me first` (pinned)
3. Open it, see the "I want to..." lookup
4. Pick the workflow, copy the template from the body (or pick from the New Issue template dropdown if you've set those up)
5. Paste into a new issue, fill placeholders, submit
6. Wait for Finance Lead's heartbeat (or hit "Run Heartbeat" on the agent page if you want it now)
7. Read the response, approve/reject/edit

No bookmarks, no separate docs site, no slack pings asking "where's that template again?" Everything's in Paperclip's UI.
