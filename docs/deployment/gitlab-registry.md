# GitLab Container Registry

This repository builds four runtime images:

- `carpayin-backend`
- `mock-card`
- `mock-pg`
- `pms`

Default GitLab registry base for the current `origin` remote:

```text
registry.gitlab.com/car-pay-in/car-pay-in-test
```

Final image names:

```text
registry.gitlab.com/car-pay-in/car-pay-in-test/carpayin-backend:<tag>
registry.gitlab.com/car-pay-in/car-pay-in-test/mock-card:<tag>
registry.gitlab.com/car-pay-in/car-pay-in-test/mock-pg:<tag>
registry.gitlab.com/car-pay-in/car-pay-in-test/pms:<tag>
```

Use semantic version tags that match the Kubernetes manifests:

```text
0.0.1, 0.0.2, 0.1.0, ...
```

`latest` is also pushed for the newest release image.

## Local Push

Create a GitLab personal access token or deploy token with `write_registry`.
Then run from the repository root:

```powershell
$env:GITLAB_REGISTRY_USER = "<gitlab-username-or-deploy-token-user>"
$env:GITLAB_REGISTRY_TOKEN = "<token>"

.\scripts\build-push-images.ps1 -Tag "0.0.1"
```

This publishes both `:0.0.1` and `:latest`.

To publish the next version:

```powershell
.\scripts\build-push-images.ps1 -Tag "0.0.2"
```

To push only one service:

```powershell
.\scripts\build-push-images.ps1 -Services carpayin-backend -Tag "0.0.2"
```

To publish a version without moving `latest`, add `-NoLatest`.

## GitLab CI

`.gitlab-ci.yml` builds and pushes all four images when a Git tag that looks
like `0.0.1`, `0.0.2`, or `0.1.0` is pushed. After the build jobs finish, the
`deploy:local-compose` job can deploy those registry images on a local machine
that runs a GitLab Runner tagged `local-deploy`.

Create and push a release tag:

```powershell
git tag 0.0.1
git push origin 0.0.1
```

Each image is pushed with:

- `$CI_COMMIT_TAG`, for example `0.0.1`
- `latest`

## Local GitLab Runner Deploy

The automatic local deploy job assumes:

- GitLab Runner is installed on the local deploy machine.
- The runner uses the Shell executor on Windows PowerShell.
- The runner has the tag `local-deploy`.
- Docker Desktop is running on that machine.
- Runtime environment variables are available to the job.

Register a local runner with a tag like:

```powershell
gitlab-runner register
```

During registration, use:

```text
executor: shell
tag: local-deploy
```

The deploy job runs:

```powershell
.\scripts\deploy-from-registry.ps1 -Tag $env:CI_COMMIT_TAG
```

That script overlays `docker-compose.registry.yaml`, pulls these images from
GitLab Registry, and restarts the local compose stack without rebuilding:

```powershell
docker compose -f docker-compose.yaml -f docker-compose.registry.yaml pull carpayin-backend mock-card mock-pg pms
docker compose -f docker-compose.yaml -f docker-compose.registry.yaml up -d --no-build
```

For the deploy job, set required runtime secrets in GitLab project CI/CD
variables or in the runner machine environment:

```text
PUBLIC_BASE_URL
HYUNDAI_CLIENT_ID
HYUNDAI_CLIENT_SECRET
HYUNDAI_AUTHORIZE_URL
HYUNDAI_TOKEN_URL
HYUNDAI_USER_INFO_URL
HYUNDAI_VEHICLE_LIST_URL
PG_PUBLIC_BASE_URL
MOLIT_VERIFY_ENABLED
MOCK_PG_ALLOW_FAKE_CARD_ON_VERIFY_FAILURE
```

At minimum for local Hyundai OAuth, `PUBLIC_BASE_URL`, `HYUNDAI_CLIENT_ID`, and
`HYUNDAI_CLIENT_SECRET` must exist.

You can also test the deploy step manually after pushing images:

```powershell
.\scripts\deploy-from-registry.ps1 -Tag 0.0.1
```

GitLab provides these registry variables automatically:

- `CI_REGISTRY`
- `CI_REGISTRY_IMAGE`
- `CI_REGISTRY_USER`
- `CI_REGISTRY_PASSWORD`

The runner must support Docker-in-Docker with privileged mode enabled.

## AWS Pull

For AWS or a server pulling these images, create a GitLab deploy token with
`read_registry`, then login:

```bash
docker login registry.gitlab.com \
  -u "<deploy-token-user>" \
  -p "<deploy-token>"
```

Then pull a specific tag:

```bash
docker pull registry.gitlab.com/car-pay-in/car-pay-in-test/carpayin-backend:0.0.1
docker pull registry.gitlab.com/car-pay-in/car-pay-in-test/mock-card:0.0.1
docker pull registry.gitlab.com/car-pay-in/car-pay-in-test/mock-pg:0.0.1
docker pull registry.gitlab.com/car-pay-in/car-pay-in-test/pms:0.0.1
```

For AWS production, inject runtime secrets through AWS Secrets Manager,
Parameter Store, ECS task secrets, or the deployment system. Do not bake `.env`
or Hyundai credentials into the images.
