# FOG Auto Deployment

`fog_auto_deploy.py` automates the handoff from a completed GitHub Actions image build to a captured image in FOG. It downloads the latest build artifact, imports it into a Proxmox "golden VM", creates the corresponding FOG image and capture task, boots the VM into PXE, waits for the capture to finish, and then cleans up the temporary files.

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
GH_BRANCH = "noble"
GH_TOKEN = os.environ.get("GH_TOKEN", "your_github_read_only_token")

VM_ID = os.environ.get("VM_ID", "999")
STORAGE = os.environ.get("STORAGE", "local-lvm")
DISK_SLOT = os.environ.get("DISK_SLOT", "virtio0")

FOG_URL = os.environ.get("FOG_URL", "http://your-fog-ip/fog")
FOG_API_TOKEN = os.environ.get("FOG_API_TOKEN", "your_global_token")
FOG_USER_TOKEN = os.environ.get("FOG_USER_TOKEN", "your_user_token")
VM_MAC = os.environ.get("VM_MAC", "AA:BB:CC:DD:EE:FF")
```

The script prefers environment variables when they are set, which makes it easier to reuse the same file across different Proxmox and FOG environments.

### Configuration values

| Setting | Purpose |
| --- | --- |
| `GH_REPO` | GitHub repository that publishes the build artifact |
| `GH_WORKFLOW` | Workflow file to inspect for successful runs |
| `GH_BRANCH` | Branch that the workflow run must come from |
| `GH_TOKEN` | Fine-grained GitHub token used to download the artifact; can be supplied with the `GH_TOKEN` environment variable |
| `VM_ID` | Proxmox VM ID for the golden VM; can be supplied with the `VM_ID` environment variable |
| `STORAGE` | Proxmox storage target used by `qm disk import`; can be supplied with the `STORAGE` environment variable |
| `DISK_SLOT` | Proxmox disk interface to replace on the golden VM, such as `virtio0`; can be supplied with the `DISK_SLOT` environment variable |
| `FOG_URL` | Base URL of the FOG instance, typically `http://your-fog-ip/fog`; if `/management` is included it will be stripped automatically |
| `FOG_API_TOKEN` | FOG global API token; can be supplied with the `FOG_API_TOKEN` environment variable |
| `FOG_USER_TOKEN` | FOG user API token; can be supplied with the `FOG_USER_TOKEN` environment variable |
| `VM_MAC` | MAC address of the host record in FOG that should receive the image assignment; can be supplied with the `VM_MAC` environment variable |

## Prerequisites

Install the required packages on the Proxmox host:

```bash
apt-get install python3-requests zstd
```

Also make sure:

1. The golden VM already exists in Proxmox.
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
export VM_MAC="AA:BB:CC:DD:EE:FF"
python3 fog_auto_deploy.py
```

## How to run it

```bash
python3 fog_auto_deploy.py
```

## End-to-end deployment flow

The script performs the following sequence:

1. **Verify FOG connectivity**
   - Calls `FOG_URL/system/info` before touching Proxmox storage.
   - Fails early if the Proxmox host cannot reach FOG or the API is unavailable.
   - Normalizes `FOG_URL` so a value ending in `/management` is treated as the API base URL without that suffix.

2. **Find the latest successful build artifact**
   - Queries GitHub Actions for successful runs of `build-image.yaml` on `GH_BRANCH`.
   - Looks for an artifact whose name ends with `.qcow2.zst`.

3. **Download and extract the artifact**
   - Downloads the artifact archive to `temp.zip`.
   - Extracts the GitHub artifact wrapper with Python's built-in zip support.
   - Decompresses the `.zst` file into a raw `.qcow2`.

4. **Replace the golden VM disk in Proxmox**
   - Imports the new qcow2 into the configured Proxmox storage using `qm disk import`.
   - Detects the newly imported unused volume.
   - Reattaches that imported volume to `DISK_SLOT` on the golden VM.

5. **Create the FOG image and task**
   - Creates a new FOG image definition named from the downloaded `.qcow2.zst` filename.
   - Uses a filesystem-safe image path derived from the name.
   - Finds the FOG host record by `VM_MAC`.
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
     - `temp.zip`
     - the downloaded `.qcow2.zst`
     - the extracted `.qcow2`

## Operational notes

- The workflow assumes the latest successful GitHub Actions artifact on `GH_BRANCH` is the one you want to deploy.
- The script creates a new FOG image entry for each downloaded image filename rather than reusing an existing image definition.
- The script now fails fast on command failures, HTTP errors, missing config placeholders, and missing API fields instead of continuing with partial state.
- Cleanup happens after FOG reports that the host's capture task started and then finished, which keeps large temporary image files from accumulating on the Proxmox host.
