<p align="center">
  <img src="assets/banner.png" alt="Task Management API" width="800">
</p>

![Repo size](https://img.shields.io/github/repo-size/vladislav-devops/task-management?color=d67429)
![Last commit](https://img.shields.io/github/last-commit/vladislav-devops/task-management?color=d67429)
![Stars](https://img.shields.io/github/stars/vladislav-devops/task-management?style=flat&color=d67429)

**English** · [Русский](README.ru.md)

# Task Management API

<p align="center">
  <img src="assets/ProjectExample1.png" alt="Example 1" width="45%">
  <img src="assets/ProjectExample2.png" alt="Example 2" width="45%">
</p>

## Table of contents

1. [About](#about)
2. [Usage](#usage)
3. [Install and run](#install-and-run)
4. [Configuration](#configuration)
5. [CI/CD variables](#cicd-variables)
6. [How to push](#how-to-push)

## About

Task Management API, a REST API for managing tasks.

Stack: Python, FastAPI, PostgreSQL, Redis.

The application consists of source code and a dependencies file (`requirements.txt`).

## Usage

The API provides:
- Create, read, update, delete tasks (CRUD)
- Filter tasks by status
- Simple statistics
- Health endpoint for liveness checks

After startup, all endpoints are available in interactive Swagger UI:

http://localhost:8000/docs

Alternative documentation view (ReDoc):

http://localhost:8000/redoc

## Install and run

1. Clone the repository:

```bash
git clone https://github.com/vladislav-devops/task-management.git
cd task-management
```

2. Copy the env template:

```bash
cp .env.example .env
```

Adjust values in `.env` if needed (passwords, ports) - see [Configuration](#configuration).

3. Start the stack:

```bash
docker compose up -d --build
```

On first run, compose builds the image from the `Dockerfile`.

4. Wait ~30 seconds for services to come up. Check status:

```bash
docker compose ps
```

All containers should be `Up` or `Up (healthy)`.

5. Open in browser:

- API: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health: [http://localhost:8000/health](http://localhost:8000/health)
- Grafana (logs): [http://localhost:3000](http://localhost:3000)

6. Stop:

```bash
docker compose down
```

To wipe data (DB, logs) as well, use the `-v` flag:

```bash
docker compose down -v
```

## Configuration


All settings are passed through environment variables in the `.env` file. The repository contains a `.env.example` template with all available variables and defaults.

The `.env` file is not committed (it's in `.gitignore`) since it may contain sensitive data. Create it from the template before running:

```bash
cp .env.example .env
```

Main variables:

- `APP_PORT` - port the app listens on. Default 8000.
- `LOG_LEVEL` - logging level (DEBUG, INFO, WARNING, ERROR). Default INFO.
- `POSTGRES_USER` - DB user name.
- `POSTGRES_PASSWORD` - DB password.
- `POSTGRES_DB` - DB name.
- `POSTGRES_PORT` - PostgreSQL port inside the compose network. Default 5432.
- `REDIS_HOST` - Redis host. Inside docker compose it's `redis`. If running outside compose, use `localhost`.
- `REDIS_PORT` - Redis port. Default 6379.
- `GRAFANA_ADMIN_PASSWORD` - Grafana admin password. It MUST be changed (`admin` in .env.example).

After changing `.env`, restart the stack to pick up the new values:

```bash
docker compose up -d --force-recreate
```

## CI/CD variables

For the deploy stage to work, GitLab needs these variables. Go to **Settings -> CI/CD -> Variables** in the project and add:

- `DEPLOY_SSH_KEY_B64` - private SSH key for connecting to the server, base64-encoded. Generate a keypair and get the value:

```bash
ssh-keygen -t ed25519 -f deploy_key -N ""
base64 -w 0 < deploy_key
```

Variable type: **Variable** (not File). Paste the base64 output as the value.

- `DEPLOY_HOST` - IP or hostname of the deploy target server.
- `DEPLOY_USER` - user on the server. Must be in the `docker` group.

The public key (`deploy_key.pub`) needs to be placed on the server in `~/.ssh/authorized_keys` of `DEPLOY_USER`:

```bash
cat deploy_key.pub
# copy the output, on the server run:
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA..." >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Also 
**Setting up `APP_ENV_B64` in GitLab**

1. Make sure you have a real `.env` file locally with actual values (passwords, ports, etc).
2. Base64-encode it:
```bash
base64 -w 0 < .env
```
Copy the entire output.

3. Open GitLab in browser.
4. Left sidebar → **Settings** → **CI/CD**.
5. Expand the **Variables** section.
6. Click **Add variable**.
7. Fill in:
   - **Key:** `APP_ENV_B64`
   - **Value:** paste the base64 output from step 2
   - **Type:** Variable
   - **Flags:** check Protected, leave Expanded as is
   - **Environments:** All (default)
8. Click **Add variable**.
9. Done. Next pipeline run will use this value to write `/opt/junior-task/.env` on the server.

To update `.env` later: re-do `base64 -w 0 < .env`, edit the variable in GitLab, re-trigger pipeline

The server also needs:
- Docker and Docker Compose installed
- The `DEPLOY_USER` user must be in the `docker` group

P.S.
On the server, add the user to the `docker` group:

```bash
sudo usermod -aG docker <your user>
```

After this, reconnect over SSH so the group membership applies. Check:

```bash
groups <your user>
```

The output should contain `docker`.

## How to push

1. Make changes to code or configuration.

2. Stage the changed files:

```bash
git add .
```

3. Commit with a clear message:

```bash
git commit -m "what was done"
```

4. Push to the repository:

```bash
git push
```

After pushing to `main`, the CI/CD pipeline in GitLab runs automatically:

1. Tests run (`pytest`).
2. Docker image is built with Buildah.
3. Image is published to the GitLab Container Registry.
4. App is deployed to the server: rsync configs, `docker compose pull`, `docker compose up -d`.

Pipeline status is visible in GitLab: CI/CD -> Pipelines.

P.S. pushing to any branch other than `main` only runs the test stage. Build and deploy trigger from `main` only.

---
© 2026 Made by Vladislav Levchenko. Licensed under the MIT License. .
