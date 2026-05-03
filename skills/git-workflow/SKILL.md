---
name: git-workflow
description: Guide git workflows including writing commit messages, structuring branches, writing PR descriptions, resolving merge conflicts, squashing commits, rebasing, tagging releases, and undoing mistakes. Use this skill whenever the user wants help with a commit message, pull request, branching strategy, git history, rebasing, undoing a commit, stashing, or anything git-related. Trigger on phrases like "write a commit message", "help me PR this", "how should I branch", "clean up my commits", "git conflict", "undo", "revert", "stash", or any git command question.
---

# Git Workflow

Help the user work effectively with git — from individual commits to full branching strategies and pull request descriptions. Clean history communicates intent to future readers, makes bisecting bugs possible, and makes code reviews easier.

---

## Commit messages — Conventional Commits

Follow **Conventional Commits**. This is the standard that tools like semantic-release, auto-changelogs, and many CI pipelines depend on.

### Format
```
<type>(<scope>): <short summary>

<optional body — explain WHY, not what>

<optional footer>
```

### Types
| Type | When to use |
|---|---|
| `feat` | New user-facing feature |
| `fix` | Bug fix |
| `refactor` | Code restructuring, no behaviour change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `docs` | Documentation only |
| `chore` | Build, deps, tooling — nothing users see |
| `style` | Whitespace, formatting |
| `ci` | CI/CD pipeline |
| `revert` | Reverting a previous commit |

### Rules
- Summary: max 50 chars, imperative mood ("add" not "added"), no trailing period
- Blank line between summary and body
- Body: explain *why* — the diff shows *what*
- Wrap body at 72 characters
- Reference issues in footer: `Closes #42`, `Fixes #17`

### Examples

**Good:**
```
feat(memory): add background profile extraction after each turn

Profile updates were blocking the conversation response loop,
making the agent feel slow on every exchange. Running the
extractor in a daemon thread keeps it transparent to the user.

Closes #34
```

```
fix(db): index foreign key on llm_memory.user_id

PostgreSQL does not automatically index foreign keys. Sequential
scans on llm_memory were causing 800ms+ query times with >10k rows.

Fixes #41
```

```
chore: upgrade psycopg2-binary to 2.9.9
```

**Bad:**
```
fixed stuff
updated code
wip
asdfasdf
```

---

## Branching strategy

### GitHub Flow (default — simple projects, CI/CD)
```
main        ──●──────────────●──────────────●
              │               │               │
feature/x   ──┘               │               │
                  fix/login ──┘               │
                               feature/y ─────┘
```
- `main` is always deployable
- Branch for every feature or fix
- PR → review → merge to `main`
- Deploy from `main`

**Branch naming:**
```
feature/jwt-refresh
fix/profile-update-race
chore/upgrade-dependencies
docs/add-readme
```

### Git Flow (versioned releases, larger teams)
```
main       ──────────────────────────●────── (tagged v1.0)
                                    /
release/1.0 ────────────────────────
                                   /
develop    ──●────●────●──────────●────●────
             │         │
feature/x ───┘   fix/y─┘
```
- `main`: production only, always tagged
- `develop`: integration branch
- `feature/*`: from develop, back to develop
- `release/*`: from develop when prepping a release
- `hotfix/*`: from main for urgent prod fixes, merge back to both main and develop

---

## Pull request descriptions

A PR description answers: **what changed**, **why**, and **how to verify**.

```markdown
## What
One-paragraph summary of the change.

## Why
The motivation — what problem or requirement does this address?
Link to issue: Closes #42

## Changes
- Add background thread for `_update_profile`
- Store `_last_user_message` on Agent instance
- Profile model now configurable via `PROFILE_MODEL` env var

## How to test
1. Run the agent: `python3 my_agent_loop.py`
2. Tell it your name: "my name is Alice"
3. After the response, check the profile: `/profile`
4. Expected: name field populated within a few seconds

## Notes for reviewer
The threading approach uses daemon threads — if the process exits
mid-update, the profile update is silently dropped. Acceptable
tradeoff vs blocking the conversation loop.
```

---

## Cleaning up history

### Squash WIP commits before merging
```bash
# Interactive rebase — squash last 4 commits
git rebase -i HEAD~4

# In the editor that opens:
# pick abc1234 feat(auth): start JWT implementation
# squash def5678 wip
# squash ghi9012 fix typo
# squash jkl3456 almost done

# Result: one clean commit with a new message you write
```

### Amend the last commit
```bash
git add forgotten_file.py
git commit --amend --no-edit         # add staged changes to last commit
git commit --amend -m "better message"  # rewrite the message
```
⚠️ Only amend commits that haven't been pushed to a shared remote.

### Rebase onto main (linear history)
```bash
git fetch origin
git rebase origin/main

# If conflicts:
# 1. Fix the conflict in the file
# 2. git add <resolved-file>
# 3. git rebase --continue
# To abort: git rebase --abort
```

### Squash merge (keep main clean)
```bash
git checkout main
git merge --squash feature/my-branch
git commit -m "feat(auth): add JWT refresh token rotation"
git branch -d feature/my-branch
```

---

## Undoing mistakes

```bash
# Undo last commit, keep changes staged
git reset --soft HEAD~1

# Undo last commit, keep changes unstaged
git reset HEAD~1

# Undo last commit, DISCARD changes (⚠ destructive)
git reset --hard HEAD~1

# Revert a pushed commit (creates a new "undo" commit — safe for shared branches)
git revert abc1234

# Unstage a file (keep changes in working dir)
git restore --staged myfile.py

# Discard unstaged changes to a file (⚠ destructive)
git restore myfile.py

# Recover a deleted branch
git reflog                    # find the commit hash
git checkout -b recovered-branch abc1234
```

---

## Stashing

```bash
git stash                          # stash all uncommitted changes
git stash push -m "wip: auth work" # stash with a label
git stash list                     # list all stashes
git stash pop                      # apply last stash and remove it
git stash apply stash@{2}          # apply specific stash, keep it in list
git stash drop stash@{0}           # delete a stash
git stash branch new-branch        # create branch from stash
```

---

## Release tagging

```bash
# Annotated tag (recommended — includes message)
git tag -a v1.2.0 -m "Release v1.2.0: JWT rotation, profile auto-update"
git push origin v1.2.0

# Push all tags
git push origin --tags

# List tags
git tag -l "v1.*"

# Delete a tag locally and remotely
git tag -d v1.2.0
git push origin --delete v1.2.0
```

**Semantic Versioning:**
- `MAJOR.MINOR.PATCH` → e.g. `2.1.3`
- MAJOR: breaking change
- MINOR: new feature, backwards compatible
- PATCH: bug fix, backwards compatible

---

## Common issues and fixes

### "Rejected — non-fast-forward"
```bash
# Someone else pushed to the branch since you last pulled
git pull --rebase origin main      # rebase your commits on top of theirs
# If you must overwrite (⚠ only on your own feature branch):
git push --force-with-lease        # safer than --force: fails if someone else pushed
```

### Merge conflict
```bash
git status                         # shows conflicted files
# Edit each file, resolve between <<<< ==== >>>>
git add <resolved-file>
git merge --continue               # or git rebase --continue
```

Conflict markers:
```
<<<<<<< HEAD (your changes)
result = old_value
=======
result = new_value
>>>>>>> feature/new-calculation (incoming)
```
Delete the markers and keep what's correct.

### "Detached HEAD"
```bash
# You're on a commit, not a branch
git branch                         # no branch is checked out
git checkout -b new-branch         # create a branch here to save your work
# or just: git switch main
```

### Accidentally committed to main
```bash
git log --oneline -5               # find the commit hash
git checkout -b fix/accidentally-on-main    # save work on new branch
git checkout main
git reset --hard HEAD~1            # remove the commit from main (⚠ if not pushed)
# If already pushed, coordinate with team — don't force push main
```

### Committed .env or secrets
```bash
# Remove from current commit
git rm --cached .env
echo ".env" >> .gitignore
git commit -m "chore: remove .env from tracking"

# Remove from ALL history (nuclear — rewrites history)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env' \
  --prune-empty --tag-name-filter cat -- --all

# After that: rotate ALL secrets that were exposed — they're in GitHub's cache
```

### See what changed
```bash
git diff                           # unstaged changes
git diff --staged                  # staged changes
git diff main..feature/my-branch   # diff between branches
git log --oneline -10              # recent commits
git log --oneline --graph --all    # visual branch graph
git show abc1234                   # show a specific commit
git blame myfile.py                # who changed each line
```

---

## When the user provides context

If the user shares a diff or describes their changes, **write the commit message directly** — don't just explain the format. Use their actual content.

If they show a messy branch history, recommend the exact rebase commands with the real commit count.

If they describe a PR, write the full description using the template above.
