# FOG Automation & Cleanup Pipeline

This script orchestrates the end-to-end lifecycle of a new Ubuntu image: from a GitHub build to a registered and captured FOG image.

### Host Environment
* **Location:** Must be executed on the **Proxmox Hypervisor**.
* **Reason:** It requires the `qm` CLI for local disk imports, which is significantly faster than using the Proxmox API for large disk operations.

### How to Obtain Tokens

#### GitHub (Read-Only)
1.  Navigate to **Settings > Developer Settings > Personal Access Tokens**.
2.  Generate a **Fine-grained token**.
3.  Grant **Read-only** access to **Actions** and **Metadata** for the `Kramden/kramden-iso-builder` repository.

#### FOG Server
1.  **Global Token:** Go to **FOG Configuration > FOG Settings > API System**. Enable it and copy the `FOG_API_TOKEN`.
2.  **User Token:** Go to **User Management > [Your User] > API Settings**. Copy the `FOG_USER_TOKEN`.

### Workflow Steps
1.  **Poll GitHub:** Identifies the latest successful `build-image.yaml` workflow on the `noble` branch.
2.  **Download & Decompress:** Downloads the `.qcow2.zst` and decompresses it to raw `.qcow2`.
3.  **Proxmox Import:** Overwrites the disk of your designated "Golden VM" (the VM configured for PXE booting).
4.  **FOG Registration:**
    * Creates a new Image definition using the filename (e.g., `kramden-24.04.4-20260411-0425-amd64`).
    * Assigns this image to your Golden VM via MAC address.
    * Creates a **Capture Task**.
5.  **Execution:** Powers on the VM.
6.  **Polling & Cleanup:** [Inference] The script enters a loop, querying the FOG API every 30 seconds. Once the task disappears from the "Active Tasks" list, the script stops the VM and deletes the downloaded `.zip`, `.zst`, and `.qcow2` files to prevent Proxmox storage bloat.

### Setup Checklist
* [ ] Python 3 installed with `requests` library.
* [ ] `zstd` and `unzip` installed on Proxmox.
* [ ] Golden VM created and MAC address updated in script.
* [ ] Proxmox Storage name (e.g., `local-lvm`) verified.
