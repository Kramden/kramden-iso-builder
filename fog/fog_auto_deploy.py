import argparse
import os
import re
import subprocess
import time
import zipfile
from pathlib import Path

import requests

# --- CONFIGURATION ---
GH_REPO = "Kramden/kramden-iso-builder"
GH_WORKFLOW = "build-image.yaml"
GH_BRANCH = "noble"
GH_TOKEN = os.environ.get("GH_TOKEN", "your_github_read_only_token")

VM_ID = os.environ.get("VM_ID", "999")
# STORAGE = "local-lvm"
# DISK_SLOT = "virtio0"
STORAGE = "DRIVE-ZFS"
DISK_SLOT = "virtio0"

FOG_URL = os.environ.get("FOG_URL", "http://192.168.14.9/fog")
FOG_API_TOKEN = os.environ.get("FOG_API_TOKEN", "your_global_token")
FOG_USER_TOKEN = os.environ.get("FOG_USER_TOKEN", "your_user_token")
VM_MAC = os.environ.get("VM_MAC", "bc:24:11:83:52:e0")

# When set, reuse this existing FOG image ID instead of creating a new image
# record each run. This avoids the buggy /image/create code path on FOG
# servers that throw a 500 from imagemanagementpage.class.php under PHP 8.
IMAGE_ID = os.environ.get("IMAGE_ID", "")

REQUEST_TIMEOUT = 30
POLL_INTERVAL = 30
TASK_START_TIMEOUT = 600

TEMP_ZIP = Path("temp.zip")
CONFIG_LINE_PATTERN = re.compile(r"^(?P<key>[^:]+):\s*(?P<value>.+)$")

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


def validate_config():
    placeholders = {
        "GH_TOKEN": "your_github_read_only_token",
        "FOG_API_TOKEN": "your_global_token",
        "FOG_USER_TOKEN": "your_user_token",
        "FOG_URL": "http://your-fog-ip/fog",
        "VM_MAC": "AA:BB:CC:DD:EE:FF",
    }

    current_values = {
        "GH_TOKEN": GH_TOKEN,
        "FOG_API_TOKEN": FOG_API_TOKEN,
        "FOG_USER_TOKEN": FOG_USER_TOKEN,
        "FOG_URL": FOG_URL,
        "VM_MAC": VM_MAC,
    }

    missing = [
        name
        for name, placeholder in placeholders.items()
        if current_values[name] == placeholder
    ]
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


def download_artifact_archive(url, destination):
    redirect_response = github_get(url, allow_redirects=False)
    if redirect_response.status_code != 302:
        raise RuntimeError(
            "GitHub did not return an artifact download redirect. "
            f"Status: {redirect_response.status_code}"
        )

    download_url = redirect_response.headers.get("Location")
    if not download_url:
        raise RuntimeError("GitHub artifact download response did not include a Location header.")

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


def get_latest_artifact():
    print(
        f"[*] Querying GitHub for latest successful {GH_WORKFLOW} run on {GH_BRANCH}..."
    )
    runs_resp = github_get(
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{GH_WORKFLOW}/runs",
        params={"branch": GH_BRANCH, "per_page": 10},
    )
    workflow_runs = runs_resp.json().get("workflow_runs", [])
    run = next(
        (
            item
            for item in workflow_runs
            if item.get("conclusion") == "success"
            and item.get("head_branch") == GH_BRANCH
        ),
        None,
    )
    if run is None:
        raise RuntimeError(
            f"No successful {GH_WORKFLOW} runs were found on branch '{GH_BRANCH}'."
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


def download_and_extract(url, artifact_name):
    print(f"[*] Downloading {artifact_name}...")
    download_artifact_archive(url, TEMP_ZIP)

    with zipfile.ZipFile(TEMP_ZIP) as archive:
        members = archive.namelist()
        zst_members = [member for member in members if member.endswith(".qcow2.zst")]
        if len(zst_members) != 1:
            raise RuntimeError(
                "Artifact zip did not contain exactly one .qcow2.zst file. "
                f"Found: {members}"
            )
        archive.extract(zst_members[0])

    TEMP_ZIP.unlink(missing_ok=True)

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


def get_vm_config():
    try:
        result = run_command(["qm", "config", VM_ID], capture_output=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"'qm config {VM_ID}' failed (exit {exc.returncode}). "
            f"Check that VM {VM_ID} exists on this Proxmox host. "
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


def build_disk_slot_value(imported_volume, current_disk_value):
    if not current_disk_value or "," not in current_disk_value:
        return imported_volume
    current_options = [
        option
        for option in current_disk_value.split(",")[1:]
        if not option.startswith("size=")
    ]
    if not current_options:
        return imported_volume
    return f"{imported_volume},{','.join(current_options)}"


def proxmox_disk_swap(qcow2_path):
    print(f"[*] Importing disk to Proxmox VM {VM_ID}...")
    before_config = get_vm_config()
    before_unused = set(get_unused_volumes(before_config).values())

    run_command(["qm", "disk", "import", VM_ID, str(qcow2_path), STORAGE])

    after_config = get_vm_config()
    after_unused = get_unused_volumes(after_config)
    new_volumes = sorted(set(after_unused.values()) - before_unused)
    if len(new_volumes) != 1:
        raise RuntimeError(
            "Unable to identify the newly imported Proxmox volume. "
            f"New unused volumes: {new_volumes or 'none'}"
        )

    imported_volume = new_volumes[0]
    disk_slot_value = build_disk_slot_value(
        imported_volume, before_config.get(DISK_SLOT)
    )
    run_command(["qm", "set", VM_ID, f"--{DISK_SLOT}", disk_slot_value])


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


def fog_orchestration(image_name):
    if IMAGE_ID:
        print(f"[*] Reusing existing FOG image ID {IMAGE_ID}...")
        new_img_id = IMAGE_ID
    else:
        print(f"[*] Registering image '{image_name}' in FOG...")
        img_payload = {
            "name": image_name,
            "path": image_name.replace(".", "_"),
            "imageTypeID": "1",
            "osID": "1",
        }
        img_resp = fog_request("POST", "/image/create", json=img_payload).json()
        new_img_id = extract_required(img_resp, "id", "image creation")

    host_data = fog_request("GET", "/host").json()
    hosts = host_data.get("hosts", [])
    host = next(
        (h for h in hosts if host_has_mac(h, VM_MAC)),
        None,
    )
    if host is None:
        raise RuntimeError(f"No FOG host matched VM_MAC '{VM_MAC}'.")

    host_id = extract_required(host, "id", "host lookup")

    fog_request("PUT", f"/host/{host_id}/edit", json={"imageID": new_img_id})
    fog_request("POST", f"/host/{host_id}/task", json={"taskTypeID": 1})
    return host_id


def wait_for_completion(host_id):
    print("[*] Monitoring FOG capture status...")
    start_time = time.time()
    saw_active_task = False

    while True:
        active_tasks = fog_request("GET", "/task/active").json().get("tasks", [])
        is_active = any(
            str(task.get("hostID")) == str(host_id) for task in active_tasks
        )

        if is_active:
            saw_active_task = True
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
            "Download the latest kramden image artifact, deploy it to a "
            "Proxmox VM, and capture it into FOG."
        )
    )
    parser.add_argument(
        "artifact",
        nargs="?",
        help=(
            "Path to an already-downloaded .qcow2.zst artifact. If omitted, "
            "the latest successful GitHub artifact is downloaded into the "
            "current directory."
        ),
    )
    return parser.parse_args()


def main():
    global FOG_URL

    args = parse_args()

    validate_config()
    FOG_URL = normalize_fog_url(FOG_URL)
    verify_fog_connectivity()

    if args.artifact:
        zst_path = Path(args.artifact)
        if not zst_path.is_file():
            raise RuntimeError(f"Artifact '{zst_path}' does not exist.")
        print(f"[*] Using existing artifact {zst_path}...")
    else:
        download_url, artifact_name = get_latest_artifact()
        zst_path = download_and_extract(download_url, artifact_name)

    raw_qcow2 = decompress_artifact(zst_path)

    proxmox_disk_swap(raw_qcow2)
    host_id = fog_orchestration(zst_path.name)

    run_command(["qm", "start", VM_ID])
    wait_for_completion(host_id)

    run_command(["qm", "stop", VM_ID])
    cleanup_temp_files(TEMP_ZIP, raw_qcow2)
    print(f"[!] VM powered down. Artifact retained at {zst_path.resolve()}")


if __name__ == "__main__":
    main()
