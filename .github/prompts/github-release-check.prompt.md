---
mode: agent
description: "Check GitHub release status, Actions workflow runs, Pages deployment status, and branch/tag alignment."
---

# GitHub Release & Workflow Status Check

Inspect the GitHub repository (`RajwanYair/SchoolMeritPoints`) integration and release health:

1. Check git sync state (`git status -sb`, `git log --oneline -n 5`, `git diff --stat HEAD origin/main`).
2. Check latest GitHub release and tags (`gh release list`, `gh api repos/RajwanYair/SchoolMeritPoints/tags`) and compare the latest release tag commit against `main`.
3. Check recent GitHub Actions runs (`gh run list -L 10`) for `CI & API Tests`, `Deploy to GitHub Pages`, and `Release Package & Publish`.
4. Check GitHub Pages configuration (`gh api repos/RajwanYair/SchoolMeritPoints/pages`).
5. Summarize release readiness, workflow pass/fail status, and any commits on `main` not yet published in a tagged release.
