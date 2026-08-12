# FOG Auto Deployment

`fog_auto_deploy.py` automates the handoff from a completed GitHub Actions image build to a captured image in FOG. It downloads the latest build artifact, imports it into a Proxmox "golden VM", creates the corresponding FOG image and capture task, boots the VM into PXE, waits for the capture to finish, and then cleans up the temporary files.

It processes one release per invocation, selected with `--release {noble,resolute}`. Each release has its own branch, golden VM, VM MAC (used to find its FOG host record), and optional FOG image ID, so a problem with one release's pipeline can never block the other.

## Where to run it

Run this script directly on the **Proxmox hypervisor**.

That is required because the workflow depends on:

- `qm` for local disk import and VM control
- local access to Proxmox storage
- network access to both GitHub and the FOG server
- `zstd` for artifact extraction

## What the script expects

Before running `fog_auto_deploy.py`, update the configuration block at the top of the script:

```python
GH_REPO = "Kramden/kramden-iso-builder"
GH_WORKFLOW = "build-image.yaml"
GH_NOBLE_BRANCH = os.environ.get("GH_NOBLE_BRANCH", "noble")
GH_RESOLUTE_BRANCH = os.environ.get("GH_RESOLUTE_BRANCH", "resolute")
GH_TOKEN = os.environ.get("GH_TOKEN", "your_github_read_only_token")

NOBLE_VM_ID = os.environ.get("NOBLE_VM_ID", "999")
RESOLUTE_VM_ID = os.environ.get("RESOLUTE_VM_ID", "998")
STORAGE = os.environ.get("STORAGE", "local-lvm")
DISK_SLOT = os.environ.get("DISK_SLOT", "virtio0")

FOG_URL = os.environ.get("FOG_URL", "http://your-fog-ip/fog")
FOG_API_TOKEN = os.environ.get("FOG_API_TOKEN", "your_global_token")
FOG_USER_TOKEN = os.environ.get("FOG_USER_TOKEN", "your_user_token")
NOBLE_VM_MAC = os.environ.get("NOBLE_VM_MAC", "bc:24:11:83:52:e0")
RESOLUTE_VM_MAC = os.environ.get("RESOLUTE_VM_MAC", "AA:BB:CC:DD:EE:FF")
```

The script prefers environment variables when they are set, which makes it easier to reuse the same file across different Proxmox and FOG environments.

### Configuration values

| Setting | Purpose |
| --- | --- |
| `GH_REPO` | GitHub repository that publishes the build artifact |
| `GH_WORKFLOW` | Workflow file to inspect for successful runs |
| `GH_NOBLE_BRANCH` / `GH_RESOLUTE_BRANCH` | Branch each release's workflow run must come from; can be supplied with the like-named environment variable |
| `GH_TOKEN` | Fine-grained GitHub token used to download the artifact; can be supplied with the `GH_TOKEN` environment variable |
| `NOBLE_VM_ID` / `RESOLUTE_VM_ID` | Proxmox VM ID for each release's golden VM; can be supplied with the like-named environment variable |
| `STORAGE` | Proxmox storage target used by `qm disk import`; can be supplied with the `STORAGE` environment variable |
| `DISK_SLOT` | Proxmox disk interface to replace on the golden VM, such as `virtio0`; can be supplied with the `DISK_SLOT` environment variable |
| `FOG_URL` | Base URL of the FOG instance, typically `http://your-fog-ip/fog`; if `/management` is included it will be stripped automatically |
| `FOG_API_TOKEN` | FOG global API token; can be supplied with the `FOG_API_TOKEN` environment variable |
| `FOG_USER_TOKEN` | FOG user API token; can be supplied with the `FOG_USER_TOKEN` environment variable |
| `NOBLE_VM_MAC` / `RESOLUTE_VM_MAC` | MAC address of each release's golden VM, used to find its FOG host record; can be supplied with the like-named environment variable. `NOBLE_VM_MAC` defaults to a real working MAC; `RESOLUTE_VM_MAC` must be set before running `--release resolute` |
| `NOBLE_IMAGE_ID` / `RESOLUTE_IMAGE_ID` | Optional: reuse an existing FOG image ID for that release instead of creating a new one each run; can be supplied with the like-named environment variable |

## Prerequisites

Install the required packages on the Proxmox host:

```bash
apt-get install python3-requests zstd
```

Also make sure, for each release you plan to run:

1. Its golden VM already exists in Proxmox.
2. Its boot order is set to prefer **network/PXE**.
3. The VM's MAC address matches the host entry in FOG.
4. The correct boot disk interface is reflected in `DISK_SLOT`.
5. The Proxmox storage name in `STORAGE` is correct.
6. The Proxmox host can reach GitHub and the FOG server.

## Token setup

### GitHub token

Create a **fine-grained personal access token** with read-only access to the `Kramden/kramden-iso-builder` repository:

1. Go to **GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens**.
2. Grant repository access to `Kramden/kramden-iso-builder`.
3. Set **Actions: Read** and **Metadata: Read**.
4. Provide it either by exporting `GH_TOKEN` or by editing the fallback value in the script.

### FOG tokens

You need both FOG API tokens:

1. **Global token:** In FOG, go to **FOG Configuration > FOG Settings > API System**, enable the API if needed, and copy `FOG_API_TOKEN`.
2. **User token:** In FOG, go to **User Management > [Your User] > API Settings**, ensure API access is enabled for the user, and copy `FOG_USER_TOKEN`.

### Recommended environment variable setup

Export the tokens before running the script:

```bash
export GH_TOKEN="your_github_read_only_token"
export FOG_URL="http://your-fog-ip/fog"
export FOG_API_TOKEN="your_global_token"
export FOG_USER_TOKEN="your_user_token"
export NOBLE_VM_MAC="bc:24:11:83:52:e0"
export RESOLUTE_VM_MAC="AA:BB:CC:DD:EE:FF"
python3 fog_auto_deploy.py --release noble
```

## How to run it

```bash
python3 fog_auto_deploy.py --release noble
python3 fog_auto_deploy.py --release resolute
```

An optional positional argument overrides the artifact with an
already-downloaded `.qcow2.zst`, scoped to the selected release:

```bash
python3 fog_auto_deploy.py --release noble ./my-test-build.qcow2.zst
```

## Running from cron

Copy `env.sh.example` to `env.sh` and fill in real values (`env.sh` is
git-ignored since it holds credentials), then use `run_fog_auto_deploy.sh` to
source it and invoke the script. It runs both releases in sequence, one
process per release, so a failure in one doesn't prevent the other from
running. Add a weekly crontab entry to run it every Sunday at 2 AM:

```
0 2 * * 0 /root/kramden-iso-builder/fog/run_fog_auto_deploy.sh >> /var/log/fog_auto_deploy.log 2>&1
```

## End-to-end deployment flow

The script performs the following sequence:

1. **Verify FOG connectivity**
   - Calls `FOG_URL/system/info` before touching Proxmox storage.
   - Fails early if the Proxmox host cannot reach FOG or the API is unavailable.
   - Normalizes `FOG_URL` so a value ending in `/management` is treated as the API base URL without that suffix.

2. **Find the latest successful build artifact**
   - Queries GitHub Actions for successful runs of `build-image.yaml` on the selected release's branch (`GH_NOBLE_BRANCH` or `GH_RESOLUTE_BRANCH`).
   - Looks for an artifact whose name ends with `.qcow2.zst`.

3. **Download and extract the artifact**
   - Peeks at the remote zip's central directory via HTTP Range requests (a handful of small requests, not the full archive) and prints the `.qcow2.zst` filename before the real download starts, so you can confirm it's the build you expect.
   - Downloads the artifact archive to `temp-<release>.zip`.
   - Extracts the GitHub artifact wrapper with Python's built-in zip support.
   - Decompresses the `.zst` file into a raw `.qcow2`.

4. **Replace the golden VM disk in Proxmox**
   - Imports the new qcow2 into the configured Proxmox storage using `qm disk import`.
   - Detects the newly imported unused volume.
   - Reattaches that imported volume to `DISK_SLOT` on the release's golden VM (`NOBLE_VM_ID` or `RESOLUTE_VM_ID`).

5. **Create the FOG image and task**
   - Creates a new FOG image definition named from the downloaded `.qcow2.zst` filename.
   - Uses a filesystem-safe image path derived from the name.
   - Finds the FOG host record by the release's VM MAC (`NOBLE_VM_MAC` or `RESOLUTE_VM_MAC`).
   - Assigns the new image to that host.
   - Creates a **capture task** for the host.

6. **Boot the VM into PXE**
   - Starts the Proxmox VM with `qm start`.
   - The VM boots from the network, checks in with FOG, and begins the capture task.

7. **Wait for completion**
   - Polls `FOG_URL/task/active` every 30 seconds.
   - Waits for the host to appear in the active task list before treating the task as started.
   - Treats the capture as complete only after that active task later disappears.

8. **Clean up**
   - Stops the VM with `qm stop`.
   - Deletes the temporary files:
     - `temp-<release>.zip`
     - the downloaded `.qcow2.zst`
     - the extracted `.qcow2`

## Operational notes

- The workflow assumes the latest successful GitHub Actions artifact on the selected release's branch is the one you want to deploy.
- The script creates a new FOG image entry for each downloaded image filename rather than reusing an existing image definition, using `imageTypeID: 2` ("Multiple Partition Image - Single Disk, Not Resizable") and `osID: 50` (Linux). The kramden build VM boots under OVMF/UEFI, so curtin gives the disk a GPT table with a FAT32 EFI System Partition (holding grub-efi/shim) plus the ext4 root partition — a single-partition image type would silently drop the ESP and produce a capture that's unbootable on UEFI-only target hardware.
- If you're reusing an existing image via `NOBLE_IMAGE_ID`/`RESOLUTE_IMAGE_ID`, make sure that image's type in the FOG UI (Image Management > *image* > Type) is also "Multiple Partition Image" — the script can't change the type of an image it didn't create.
- The script now fails fast on command failures, HTTP errors, missing config placeholders, and missing API fields instead of continuing with partial state.
- Cleanup happens after FOG reports that the host's capture task started and then finished, which keeps large temporary image files from accumulating on the Proxmox host.
- `--release` is required; there's no default and no way to process both releases in a single invocation. This keeps each release's failure mode fully independent -- see `run_fog_auto_deploy.sh` for how cron runs both.
