# Machine setup: prerequisites for Phase 1

> For the owner's dev machine: Windows 11 + WSL2, Ubuntu 24.04, systemd enabled. Checked on 2026-11-09.
> **Postgres is not installed on the machine.** It runs in a Docker container (`infra/docker-compose.yml`). Docker is the only DB prerequisite.
> Steps marked 🔑 need `sudo` and have to be run by you. The rest are user-space installs.

## Status at time of check (2026-11-09)

| Tool | Status |
|---|---|
| git 2.43, curl, GitHub SSH auth (`ryanalmasi`) | ✅ |
| make, Docker Engine + Compose, gh, uv, Python 3.13, Node 26 LTS, pre-commit, gitleaks | ❌ install below |

## 0. Move the repo into the Linux filesystem

**Why:** from WSL, `/mnt/c` is slow for npm and Docker, and file watchers (`uvicorn --reload`, Vite HMR) often miss changes there. **✅ Done 2026-11-09** by copying the folder. Files on `/mnt/c` all appear executable, so the copy needs its permissions reset and git's file-mode tracking turned back on:

```bash
mkdir -p ~/code
cp -r /mnt/c/Users/ryana/Documents/Github/feynman-flashcard ~/code/
cd ~/code/feynman-flashcard
find . -path ./.git -prune -o -type f -exec chmod 644 {} +   # files: rw-r--r--
find . -path ./.git -prune -o -type d -exec chmod 755 {} +   # dirs:  rwxr-xr-x
git config core.filemode true                                # /mnt/c repos default to false
git status   # should list only the new docs as untracked; no "modified" entries
```
Then rename the old folder (e.g. `feynman-flashcard-OLD`) so nobody works in it by accident, and delete it once the run is merged. **Start all future Claude Code sessions from `~/code/feynman-flashcard`.** In Windows, open it with VS Code's *WSL* extension (`code .` from the WSL shell) or via `\\wsl$\Ubuntu\home\ryana\code\feynman-flashcard`.

Optional: Claude Code's private memory is tied to the old path. To carry it over:
`mkdir -p ~/.claude/projects/-home-ryana-code-feynman-flashcard && cp -r ~/.claude/projects/-mnt-c-Users-ryana-Documents-Github-feynman-flashcard/memory ~/.claude/projects/-home-ryana-code-feynman-flashcard/`

## 1. 🔑 make and base packages
```bash
sudo apt update && sudo apt install -y make ca-certificates curl libatomic1   # libatomic1: required by the Node 26 binaries
```

## 2. 🔑 Docker Engine (inside WSL, not Docker Desktop)
Docker's official apt repo for Ubuntu:
```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```
Then restart WSL so the group change applies. In **PowerShell**: `wsl --shutdown`, then reopen Ubuntu. Check with `docker run --rm hello-world`.
*Security note:* membership in the `docker` group is effectively root on this machine. That's normal for a single-user dev box. If you prefer, rootless Docker is the alternative.

## 3. 🔑 GitHub CLI (`gh`), needed for the draft PR
```bash
sudo mkdir -p -m 755 /etc/apt/keyrings
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install -y gh
gh auth login      # GitHub.com → SSH → use your existing key → log in with a web browser
```

## 4. uv + Python 3.13 (user space)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc        # or open a new shell
uv python install 3.13
```
The system Python 3.12 stays untouched. The project's interpreter is managed by uv.

## 5. Node 26 LTS via nvm (user space)
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.41.0/install.sh | bash
source ~/.bashrc
nvm install 26 && nvm alias default 26
```

## 6. pre-commit and gitleaks (user space)
```bash
uv tool install pre-commit
mkdir -p ~/.local/bin
curl -fsSL https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
  | tar -xz -C ~/.local/bin gitleaks
```
Make sure `~/.local/bin` is on your `PATH` (the uv installer normally adds it).

## 7. Verify. The implementer runs this same block first and stops if anything fails.
```bash
fail=0
for c in git make docker gh uv node npm pre-commit gitleaks; do
  command -v "$c" >/dev/null || { echo "MISSING: $c"; fail=1; }
done
docker compose version >/dev/null 2>&1 || { echo "MISSING: docker compose plugin"; fail=1; }
docker info >/dev/null 2>&1           || { echo "Docker daemon not reachable (group/WSL restart?)"; fail=1; }
uv python find 3.13 >/dev/null 2>&1   || { echo "MISSING: Python 3.13 (uv python install 3.13)"; fail=1; }
node -v | grep -q '^v26\.'            || { echo "Node is not v26: $(node -v)"; fail=1; }
gh auth status >/dev/null 2>&1        || { echo "gh not authenticated (gh auth login)"; fail=1; }
ssh -T -o BatchMode=yes git@github.com 2>&1 | grep -q "successfully authenticated" || { echo "GitHub SSH auth failing"; fail=1; }
case "$PWD" in /mnt/*) echo "Repo is on /mnt/* — move it to ~/code (step 0)"; fail=1;; esac
[ $fail -eq 0 ] && echo "ALL PREREQUISITES OK"
```

## Not needed
- A local Postgres install or `psql` (use `docker compose exec db psql ...`).
- Redis, Docker Desktop, GitHub push protection (deferred, ADR 0006).
- Any API keys. Phase 1 uses no LLM provider.
