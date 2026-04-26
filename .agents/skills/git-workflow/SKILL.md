---
name: git-workflow
description: Git workflow rules — branching, commits, merge to debug, main protection, auto-commit.
---

# Git Workflow

## General Rules

- Hosting: **GitHub**
- Main working branch: **debug** (all features merge here)
- Production branch: **main** (merge from debug only after verification)
- **Direct push to main is FORBIDDEN** — only via merge from debug

---

## 1. Branch Naming Convention

Format: `type/short-description`

| Prefix | When to use | Example |
|---|---|---|
| `feature/` | New functionality | `feature/mac-pool-import` |
| `bugfix/` | Bug fix | `bugfix/qc-passed-duplicate` |
| `hotfix/` | Urgent production fix | `hotfix/admin-auth-bypass` |
| `refactor/` | Refactoring without behavior change | `refactor/workflow-cleanup` |

Rules:
- Latin characters only, lowercase, hyphens
- As brief as possible, but clear
- Don't use ticket numbers without description

---

## 2. Commit Messages

Format: **component: what changed** (brief, in English or Russian)

```
git commit -m "workflow: dynamic cooldown from project route instead of hardcoded 5 min"
git commit -m "admin_api: added ADMIN/ROOT role check in create_user, update_user, toggle_user_active"
git commit -m "scan: restoreState now preserves timer across page reloads"
```

Rules:
- First word — file or component (without extension)
- After colon — what exactly changed
- Single line, up to ~120 characters
- If many changes in one commit — list separated by commas

---

## 3. Workflow

```
1. git checkout debug
2. git pull origin debug
3. git checkout -b feature/feature-name
4. ... work on code ...
5. git add .
6. git commit -m "component: what changed"
7. git push -u origin feature/feature-name
8. git checkout debug
9. git merge feature/feature-name
10. git push origin debug
```

### Merge to main (only after debug verification)

```
git checkout main
git pull origin main
git merge debug
git push origin main
```

---

## 4. Main Branch Protection

- **NEVER** commit directly to main
- **NEVER** do `git push origin main` without prior merge from debug
- If the agent detects current branch is main, it must:
  1. Stop
  2. Warn the user
  3. Suggest creating a branch

---

## 5. Conflicts

When conflicts arise, the agent must:
- **Stop** and not try to resolve conflicts automatically
- **Show** the list of conflicting files
- **Show** specific conflict blocks (`<<<<<<<`, `=======`, `>>>>>>>`)
- **Suggest** resolution options for each conflict
- Wait for user's decision

---

## 6. Auto-Commit

The agent **always commits automatically** after making changes:
- Group related changes into one commit (e.g., all audit fixes — one commit)
- Form a meaningful message per format from section 2
- Do `git add .` + `git commit` right after completing the task
- Push only on user request or at session end

---

## 7. .gitignore

The repository must NOT contain:
- `.env` — secrets, passwords, keys
- `dump.sql` — database dumps
- `*.sql` dumps in project root

If these files are not yet in `.gitignore` — add them before the first commit.
