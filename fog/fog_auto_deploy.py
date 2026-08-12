import argparse
import io
import os
import re
import subprocess
import time
import zipfile
from collections import namedtuple
from pathlib import Path

import requests

# --- CONFIGURATION ---
GH_REPO = "Kramden/kramden-iso-builder"
GH_WORKFLOW = "build-image.yaml"
GH_NOBLE_BRANCH = os.environ.get("GH_NOBLE_BRANCH", "noble")
GH_RESOLUTE_BRANCH = os.environ.get("GH_RESOLUTE_BRANCH", "resolute")
GH_TOKEN = os.environ.get("GH_TOKEN", "your_github_read_only_token")

NOBLE_VM_ID = os.environ.get("NOBLE_VM_ID", "999")
RESOLUTE_VM_ID = os.environ.get("RESOLUTE_VM_ID", "998")
STORAGE = os.environ.get("STORAGE", "DRIVE-ZFS")
# Disk slot to attach the imported image to. Must match the VM's boot disk
# (the one in its `boot: order=...`) so the new image is what actually boots.
DISK_SLOT = os.environ.get("DISK_SLOT", "scsi0")
# Boot order applied to the VM after import. For a FOG capture the VM must
# PXE-boot first (net0) so it loads FOS and images the freshly imported disk.
BOOT_ORDER = os.environ.get("BOOT_ORDER", f"net0;{DISK_SLOT}")

FOG_URL = os.environ.get("FOG_URL", "http://192.168.14.9/fog")
FOG_API_TOKEN = os.environ.get("FOG_API_TOKEN", "your_global_token")
FOG_USER_TOKEN = os.environ.get("FOG_USER_TOKEN", "your_user_token")
NOBLE_VM_MAC = os.environ.get("NOBLE_VM_MAC", "bc:24:11:83:52:e0")
RESOLUTE_VM_MAC = os.environ.get("RESOLUTE_VM_MAC", "AA:BB:CC:DD:EE:FF")

# When set, reuse this existing FOG image ID instead of creating a new image
# record each run. This avoids the buggy /image/create code path on FOG
# servers that throw a 500 from imagemanagementpage.class.php under PHP 8.
NOBLE_IMAGE_ID = os.environ.get("NOBLE_IMAGE_ID", "")
RESOLUTE_IMAGE_ID = os.environ.get("RESOLUTE_IMAGE_ID", "")

ReleaseConfig = namedtuple("ReleaseConfig", ["name", "branch", "vm_id", "vm_mac", "image_id"])

# Each release is captured to its own golden VM (own VM_ID and thus own NIC
# MAC / FOG host record), built from its own branch of build-image.yaml.
# fog_auto_deploy.py processes one release per invocation (--release), so a
# problem with one release's pipeline can never block the other.
RELEASES = {
    "noble": ReleaseConfig("noble", GH_NOBLE_BRANCH, NOBLE_VM_ID, NOBLE_VM_MAC, NOBLE_IMAGE_ID),
    "resolute": ReleaseConfig(
        "resolute", GH_RESOLUTE_BRANCH, RESOLUTE_VM_ID, RESOLUTE_VM_MAC, RESOLUTE_IMAGE_ID
    ),
}

REQUEST_TIMEOUT = 30
POLL_INTERVAL = 30
TASK_START_TIMEOUT = 600

CONFIG_LINE_PATTERN = re.compile(r"^(?P<key>[^:]+):\s*(?P<value>.+)$")
DISK_SLOT_PATTERN = re.compile(r"^(?:scsi|sata|virtio|ide)\d+$")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

FOG_HEADERS = {
    "fog-api-token": FOG_API_TOKEN,
    "fog-user-token": FOG_USER_TOKEN,
    "Content-Type": "application/json",
}


def normalize_fog_url(url):
    normalized = url.rstrip("/")
    if normalized.endswith("/management"):
        normalized = normalized[: -len("/management")]
    return normalized


def validate_config(release):
    placeholders = {
        "GH_TOKEN": "your_github_read_only_token",
        "FOG_API_TOKEN": "your_global_token",
        "FOG_USER_TOKEN": "your_user_token",
        "FOG_URL": "http://your-fog-ip/fog",
    }

    current_values = {
        "GH_TOKEN": GH_TOKEN,
        "FOG_API_TOKEN": FOG_API_TOKEN,
        "FOG_USER_TOKEN": FOG_USER_TOKEN,
        "FOG_URL": FOG_URL,
    }

    missing = [
        name
        for name, placeholder in placeholders.items()
        if current_values[name] == placeholder
    ]

    if release.vm_mac == "AA:BB:CC:DD:EE:FF":
        missing.append(f"{release.name.upper()}_VM_MAC")

    if missing:
        raise ValueError(
            "Update the following configuration values before running: "
            + ", ".join(missing)
        )


def run_command(args, capture_output=False):
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def github_get(url, **kwargs):
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)
    response = requests.get(
        url,
        headers=GITHUB_HEADERS,
        **kwargs,
    )
    response.raise_for_status()
    return response


def resolve_artifact_download_url(api_url):
    redirect_response = github_get(api_url, allow_redirects=False)
    if redirect_response.status_code != 302:
        raise RuntimeError(
            "GitHub did not return an artifact download redirect. "
            f"Status: {redirect_response.status_code}"
        )

    download_url = redirect_response.headers.get("Location")
    if not download_url:
        raise RuntimeError("GitHub artifact download response did not include a Location header.")
    return download_url


def download_artifact_archive(download_url, destination):
    with requests.get(download_url, stream=True, timeout=300) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    if not zipfile.is_zipfile(destination):
        preview = destination.read_bytes()[:200].decode("utf-8", errors="replace").strip()
        destination.unlink(missing_ok=True)
        raise RuntimeError(
            "Downloaded GitHub artifact is not a zip archive. "
            f"Response preview: {preview or '(empty response)'}"
        )


class _HTTPRangeReader(io.RawIOBase):
    """Minimal seekable, read-only file-like object that lazily fetches byte
    ranges over HTTP. Lets zipfile.ZipFile read just a remote zip's central
    directory -- a handful of small requests near the end of the file --
    instead of downloading the whole archive, so the .qcow2.zst member name
    can be printed before committing to the real, multi-GB download."""

    def __init__(self, url, size):
        self._url = url
        self._size = size
        self._pos = 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            self._pos = offset
        elif whence == io.SEEK_CUR:
            self._pos += offset
        elif whence == io.SEEK_END:
            self._pos = self._size + offset
        else:
            raise ValueError(f"Unsupported whence: {whence}")
        return self._pos

    def tell(self):
        return self._pos

    def readinto(self, buffer):
        length = len(buffer)
        if length == 0 or self._pos >= self._size:
            return 0
        end = min(self._pos + length, self._size) - 1
        response = requests.get(
            self._url,
            headers={"Range": f"bytes={self._pos}-{end}"},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.content
        buffer[: len(data)] = data
        self._pos += len(data)
        return len(data)


def peek_qcow2_filename(download_url):
    """Best-effort: read the remote zip's central directory via HTTP Range
    requests to find the .qcow2.zst member name before downloading the full
    archive. Returns None on any failure (e.g. the storage backend doesn't
    support Range requests) -- this is purely informational and must never
    block the real download."""
    try:
        head = requests.head(download_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        head.raise_for_status()
        size = int(head.headers["Content-Length"])
        reader = _HTTPRangeReader(download_url, size)
        with zipfile.ZipFile(reader) as archive:
            zst_members = [
                member for member in archive.namelist() if member.endswith(".qcow2.zst")
            ]
        return zst_members[0] if len(zst_members) == 1 else None
    except (requests.exceptions.RequestException, zipfile.BadZipFile, KeyError, ValueError, OSError):
        return None


def fog_request(method, path, **kwargs):
    url = f"{FOG_URL.rstrip('/')}{path}"
    try:
        response = requests.request(
            method,
            url,
            headers=FOG_HEADERS,
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"FOG request failed for {method} {url}: {exc}. "
            "Check FOG_URL, network reachability from the Proxmox host, and whether the FOG API is available."
        ) from exc

    if not response.ok:
        body = response.text.strip()
        raise RuntimeError(
            f"FOG returned HTTP {response.status_code} for {method} {url}. "
            f"Response body: {body or '(empty)'}"
        )
    return response


def verify_fog_connectivity():
    print(f"[*] Verifying FOG API connectivity at {FOG_URL}...")
    fog_request("GET", "/system/info")


def extract_required(data, field_name, context):
    value = data.get(field_name)
    if value is None:
        raise RuntimeError(
            f"FOG response for {context} did not include '{field_name}'."
        )
    return value


def get_latest_artifact(branch):
    print(
        f"[*] Querying GitHub for latest successful {GH_WORKFLOW} run on {branch}..."
    )
    runs_resp = github_get(
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{GH_WORKFLOW}/runs",
        params={"branch": branch, "per_page": 10},
    )
    workflow_runs = runs_resp.json().get("workflow_runs", [])
    run = next(
        (
            item
            for item in workflow_runs
            if item.get("conclusion") == "success"
            and item.get("head_branch") == branch
        ),
        None,
    )
    if run is None:
        raise RuntimeError(
            f"No successful {GH_WORKFLOW} runs were found on branch '{branch}'."
        )

    artifacts_resp = github_get(
        f"https://api.github.com/repos/{GH_REPO}/actions/runs/{run['id']}/artifacts"
    )
    artifacts = artifacts_resp.json().get("artifacts", [])
    target = next(
        (
            artifact
            for artifact in artifacts
            if artifact.get("name") == "kramden-img"
            and not artifact.get("expired", False)
        ),
        None,
    )
    if target is None:
        available = [f"{a.get('name')} (expired={a.get('expired')})" for a in artifacts]
        raise RuntimeError(
            f"No non-expired 'kramden-img' artifact was found for run {run['id']}. "
            f"Available artifacts: {available}"
        )

    download_url = target.get("archive_download_url") or target.get("download_url")
    if not download_url:
        raise RuntimeError("GitHub did not provide a usable artifact download URL.")

    return download_url, target["name"]


def download_and_extract(url, artifact_name, temp_zip):
    print(f"[*] Downloading {artifact_name}...")
    download_artifact_archive(url, temp_zip)

    with zipfile.ZipFile(temp_zip) as archive:
        members = archive.namelist()
        zst_members = [member for member in members if member.endswith(".qcow2.zst")]
        if len(zst_members) != 1:
            raise RuntimeError(
                "Artifact zip did not contain exactly one .qcow2.zst file. "
                f"Found: {members}"
            )
        archive.extract(zst_members[0])

    temp_zip.unlink(missing_ok=True)

    zst_path = Path(zst_members[0])
    print(f"[*] Saved artifact to {zst_path.resolve()}")
    return zst_path


def decompress_artifact(zst_path):
    if zst_path.suffix != ".zst":
        raise RuntimeError(f"Expected a .zst artifact, got '{zst_path.name}'.")

    raw_qcow2 = zst_path.with_suffix("")
    print(f"[*] Decompressing {zst_path}...")
    run_command(["zstd", "-d", "-f", str(zst_path), "-o", str(raw_qcow2)])
    return raw_qcow2


def get_vm_config(vm_id):
    try:
        result = run_command(["qm", "config", vm_id], capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"'qm config {vm_id}' failed (exit {exc.returncode}). "
            f"Check that VM {vm_id} exists on this Proxmox host. "
            f"stderr: {exc.stderr.strip() if exc.stderr else '(none)'}"
        ) from exc
    config = {}
    for line in result.stdout.splitlines():
        match = CONFIG_LINE_PATTERN.match(line)
        if match:
            config[match.group("key")] = match.group("value")
    return config


def get_unused_volumes(config):
    return {
        key: value
        for key, value in config.items()
        if key.startswith("unused") and value
    }


def get_vm_status(vm_id):
    result = run_command(["qm", "status", vm_id], capture_output=True)
    parts = result.stdout.strip().split()
    return parts[-1] if parts else "unknown"


def ensure_vm_stopped(vm_id):
    if get_vm_status(vm_id) != "running":
        return
    print(f"[*] Stopping VM {vm_id} before disk swap...")
    run_command(["qm", "stop", vm_id])
    for _ in range(60):
        if get_vm_status(vm_id) != "running":
            return
        time.sleep(2)
    raise RuntimeError(f"VM {vm_id} did not stop within timeout; cannot swap disk.")


def find_disk_slots(config, vm_id):
    """Return every slot holding a storage-backed disk owned by this VM (incl.
    unused), so we can wipe the VM to a clean slate before importing. Only
    volumes named for this VM (vm-<vm_id>-...) are touched, so a foreign disk
    that happens to be attached is never destroyed. CD-ROM/cloud-init drives
    (media=cdrom) are left alone."""
    owned_marker = f"vm-{vm_id}-"
    slots = []
    for key, value in config.items():
        if not value:
            continue
        is_unused = key.startswith("unused")
        is_disk = DISK_SLOT_PATTERN.match(key) and ":" in value and "media=cdrom" not in value
        if not (is_unused or is_disk):
            continue
        if owned_marker not in value:
            print(
                f"[!] Skipping '{key}: {value}' — not a VM {vm_id} volume; "
                "not deleting it."
            )
            continue
        slots.append(key)
    return slots


def wipe_existing_disks(vm_id):
    slots = find_disk_slots(get_vm_config(vm_id), vm_id)
    if not slots:
        return
    print(f"[*] Removing existing disks from VM {vm_id}: {', '.join(slots)}")
    # --force makes unlink physically destroy attached volumes too, not just
    # detach them to an unused slot.
    run_command(
        ["qm", "disk", "unlink", vm_id, "--idlist", ",".join(slots), "--force"]
    )


def proxmox_disk_swap(qcow2_path, vm_id):
    print(f"[*] Importing disk to Proxmox VM {vm_id}...")
    ensure_vm_stopped(vm_id)
    wipe_existing_disks(vm_id)

    run_command(["qm", "disk", "import", vm_id, str(qcow2_path), STORAGE])

    new_volumes = sorted(get_unused_volumes(get_vm_config(vm_id)).values())
    if len(new_volumes) != 1:
        raise RuntimeError(
            "Expected exactly one disk after import (existing disks were wiped "
            f"first). Found unused volumes: {new_volumes or 'none'}"
        )

    imported_volume = new_volumes[0]
    run_command(["qm", "set", vm_id, f"--{DISK_SLOT}", imported_volume])
    print(f"[*] Setting boot order to '{BOOT_ORDER}'...")
    run_command(["qm", "set", vm_id, "--boot", f"order={BOOT_ORDER}"])


def host_has_mac(host, target_mac):
    target = target_mac.lower()
    candidates = []

    # FOG's host object exposes the primary MAC as "primac" and any
    # additional MACs in a "macs" list; older code expected a top-level "mac".
    for key in ("primac", "mac"):
        value = host.get(key)
        if isinstance(value, str):
            candidates.extend(value.split("|"))

    for entry in host.get("macs", []):
        if isinstance(entry, dict):
            mac = entry.get("mac")
            if mac:
                candidates.append(mac)
        elif isinstance(entry, str):
            candidates.append(entry)

    return any(candidate.strip().lower() == target for candidate in candidates)


def fog_orchestration(image_name, vm_mac, image_id):
    if image_id:
        print(f"[*] Reusing existing FOG image ID {image_id}...")
        new_img_id = image_id
    else:
        print(f"[*] Registering image '{image_name}' in FOG...")
        # imageTypeID 2 = "Multiple Partition Image - Single Disk (Not
        # Resizable)". The kramden build VM boots under OVMF/UEFI
        # (noble/autoinstall.sh), so curtin's default "direct" layout creates
        # a GPT disk with a FAT32 EFI System Partition (holding grub-efi/shim)
        # plus the ext4 root partition. imageTypeID 1 ("Single Partition")
        # only captures one partition — it drops the ESP and the deployed
        # disk has no bootloader UEFI firmware can find. osID 50 = Linux.
        img_payload = {
            "name": image_name,
            "path": image_name.replace(".", "_"),
            "imageTypeID": "2",
            "osID": "50",
            # imagePartitionTypeID 1 = "Everything" (save the partition
            # table, all partitions, and bootloaders). Like isEnabled, this
            # isn't in databaseFieldsRequired, so omitting it leaves the
            # column at its invalid default and FOG's capture script fails
            # with "No img part type passed (savePartitionTablesAndBootLoaders)".
            "imagePartitionTypeID": "1",
            # FOG's /image/create only sets fields present in the JSON body;
            # isEnabled isn't in databaseFieldsRequired, so omitting it
            # leaves the image disabled and any task against it fails with
            # "Image is not enabled".
            "isEnabled": 1,
        }
        print(f"    [debug] image/create payload: {img_payload}")
        img_resp = fog_request("POST", "/image/create", json=img_payload).json()
        new_img_id = extract_required(img_resp, "id", "image creation")

    host_data = fog_request("GET", "/host").json()
    hosts = host_data.get("hosts", [])
    host = next(
        (h for h in hosts if host_has_mac(h, vm_mac)),
        None,
    )
    if host is None:
        raise RuntimeError(f"No FOG host matched VM MAC '{vm_mac}'.")

    host_id = extract_required(host, "id", "host lookup")
    print(
        f"    [debug] matched host id={host_id} name={host.get('name')} "
        f"current imageID={host.get('imageID')} -> new imageID={new_img_id}"
    )

    cancel_stale_task(host_id)

    fog_request("PUT", f"/host/{host_id}/edit", json={"imageID": new_img_id})
    print(
        f"[*] Host {host_id} assigned image ID {new_img_id}; queuing Capture task "
        f"(taskTypeID={TASK_TYPE_CAPTURE})..."
    )
    fog_request(
        "POST", f"/host/{host_id}/task", json={"taskTypeID": TASK_TYPE_CAPTURE}
    )
    return host_id


def cancel_stale_task(host_id):
    """Clear any task FOG still considers active for this host before
    queuing a new one. A crashed or interrupted prior run (e.g. hitting the
    "Image is not enabled" error) can leave a task in a queued/imaging state
    forever, since nothing PXE-boots to consume it — and FOG refuses to
    create a new task while one is active ("Host is already a member of an
    active task"). This makes re-runs (cron or manual) self-healing instead
    of requiring a manual cancel in the FOG UI."""
    active_tasks = fog_request("GET", "/task/active").json().get("tasks", [])
    stale = next(
        (t for t in active_tasks if str(t.get("hostID")) == str(host_id)),
        None,
    )
    if stale is None:
        return
    print(
        f"[!] Host {host_id} already has an active task (id={stale.get('id')}, "
        f"{describe_task(stale)}); cancelling it before queuing a new one..."
    )
    fog_request("DELETE", f"/host/{host_id}/cancel")


# FOG taskTypeID values (from FOG's own taskTypes table: ttID=1 -> 'Deploy',
# ttID=2 -> 'Capture'). We must request a Capture here — a Deploy task pushes
# the image *already stored on the FOG server* back down onto the VM's disk
# (overwriting the freshly imported qcow2) instead of uploading the disk's
# contents into the image store, which silently defeats the whole point of
# this script while still reporting "success".
TASK_TYPE_CAPTURE = 2

# FOG task stateID values.
TASK_STATES = {
    "0": "queued",
    "1": "queued",
    "2": "checked-in",
    "3": "imaging",
    "4": "imaging",
    "5": "complete",
    "6": "cancelled",
}


def describe_task(task):
    state_id = str(task.get("stateID", ""))
    state = TASK_STATES.get(state_id, f"state {state_id}")
    percent = task.get("percent")
    if percent in (None, "", "0"):
        return state
    return f"{state} {percent}%"


def wait_for_completion(host_id):
    print("[*] Monitoring FOG capture status...")
    start_time = time.time()
    saw_active_task = False
    last_status = None
    checked_task_type = False

    while True:
        active_tasks = fog_request("GET", "/task/active").json().get("tasks", [])
        host_task = next(
            (t for t in active_tasks if str(t.get("hostID")) == str(host_id)),
            None,
        )

        if host_task is not None:
            saw_active_task = True

            if not checked_task_type:
                checked_task_type = True
                print(f"    [debug] active task raw fields: {host_task}")
                task_type_id = str(
                    host_task.get("typeID", host_task.get("taskTypeID", ""))
                )
                if task_type_id and task_type_id != str(TASK_TYPE_CAPTURE):
                    print(
                        f"    [!] WARNING: active task type is '{task_type_id}', "
                        f"expected '{TASK_TYPE_CAPTURE}' (Capture). This task will "
                        "NOT upload the new disk to FOG's image store — the "
                        "existing stored image will be left unchanged."
                    )

            status = describe_task(host_task)
            if status != last_status:
                print(f"    [~] {status}")
                last_status = status
        elif saw_active_task:
            print("[+] Capture complete. Cleaning up...")
            return
        elif time.time() - start_time >= TASK_START_TIMEOUT:
            raise RuntimeError(
                "Capture task never appeared in FOG's active task list. "
                "Check the task queue, PXE boot settings, and host registration."
            )

        time.sleep(POLL_INTERVAL)


def cleanup_temp_files(*paths):
    for path in paths:
        path.unlink(missing_ok=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Download the latest kramden image artifact for a release, "
            "deploy it to a Proxmox VM, and capture it into FOG."
        )
    )
    parser.add_argument(
        "--release",
        required=True,
        choices=sorted(RELEASES),
        help=(
            "Which release to process. Selects the GitHub branch, Proxmox "
            "VM, VM MAC (FOG host lookup), and FOG image ID to use."
        ),
    )
    parser.add_argument(
        "artifact",
        nargs="?",
        help=(
            "Path to an already-downloaded .qcow2.zst artifact for this "
            "release. If omitted, the latest successful GitHub artifact on "
            "the release's branch is downloaded into the current directory."
        ),
    )
    return parser.parse_args()


def main():
    global FOG_URL

    args = parse_args()
    release = RELEASES[args.release]

    validate_config(release)
    FOG_URL = normalize_fog_url(FOG_URL)
    verify_fog_connectivity()

    temp_zip = Path(f"temp-{release.name}.zip")

    if args.artifact:
        zst_path = Path(args.artifact)
        if not zst_path.is_file():
            raise RuntimeError(f"Artifact '{zst_path}' does not exist.")
        print(f"[*] Using existing artifact {zst_path}...")
    else:
        api_url, artifact_name = get_latest_artifact(release.branch)
        download_url = resolve_artifact_download_url(api_url)

        qcow2_name = peek_qcow2_filename(download_url)
        if qcow2_name:
            print(f"[*] Build artifact contains image '{qcow2_name}'.")
        else:
            print(
                "[!] Could not determine the image filename before "
                "downloading (peek failed); proceeding anyway."
            )

        zst_path = download_and_extract(download_url, artifact_name, temp_zip)

    raw_qcow2 = decompress_artifact(zst_path)

    proxmox_disk_swap(raw_qcow2, release.vm_id)
    host_id = fog_orchestration(zst_path.name, release.vm_mac, release.image_id)

    run_command(["qm", "start", release.vm_id])
    wait_for_completion(host_id)

    run_command(["qm", "stop", release.vm_id])
    cleanup_temp_files(temp_zip, raw_qcow2)
    print(f"[!] VM powered down. Artifact retained at {zst_path.resolve()}")


if __name__ == "__main__":
    main()
