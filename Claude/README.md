# Claude

Working folder for work done with Claude Code in cloud sessions.

Anything kept here is committed to the repository, so it survives after a cloud
session's container is reclaimed. Files left outside the repository — in `/tmp`
or elsewhere on the session VM — are lost when the session expires.

## The plan-file workflow

For work that should run while the computer is off.

1. **Write the plan.** Copy `plans/TEMPLATE.md` to `plans/<name>.md` and fill it
   in. Be specific about what is out of scope — nobody is watching while it runs.
2. **Commit and push it to `main`.** This must happen *before* the session
   starts. The session VM clones from GitHub, not from the local machine, so an
   unpushed plan does not exist as far as the session is concerned.
3. **Start a cloud session** pointed at the plan:
   - From claude.ai/code: new session on this repo, then
     `Execute the plan in Claude/plans/<name>.md`
   - From a terminal: `claude --cloud "Execute the plan in Claude/plans/<name>.md"`
4. **Close the laptop.** The session keeps running; it has no connection to the
   local machine.
5. **Come back and review.** Check the pushed branch and the
   `plans/<name>-result.md` summary, then merge if it looks right.

### What this workflow does and does not do

- A session runs the plan, pushes, and then **stops**. It does not keep working
  or pick up new work on its own.
- Sessions stop after a period of inactivity and the VM is reclaimed. Conversation
  history is restored on reopening, but the disk is not — hence step 2 and the
  push requirement in every plan.
- For work that should recur on a schedule rather than run once, use a Routine
  (`/schedule`) instead of a plan file.

## Notes

- This repository is a **public** GitHub Pages site. Everything committed here
  is publicly visible, including plans. Do not put private research data,
  credentials, or unpublished work in it.
