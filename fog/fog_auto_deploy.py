import os
import time
import requests
import subprocess
import json

# --- CONFIGURATION ---
GH_REPO = "Kramden/kramden-iso-builder"
GH_WORKFLOW = "build-image.yaml"
GH_TOKEN = "your_github_read_only_token"

VM_ID = "999"
STORAGE = "local-lvm"

FOG_URL = "http://your-fog-ip/fog"
FOG_API_TOKEN = "your_global_token"
FOG_USER_TOKEN = "your_user_token"
VM_MAC = "AA:BB:CC:DD:EE:FF"

HEADERS = {
    "fog-api-token": FOG_API_TOKEN,
    "fog-user-token": FOG_USER_TOKEN,
    "Content-Type": "application/json",
}


def get_latest_artifact():
    print(f"[*] Querying GitHub for latest successful {GH_WORKFLOW} run...")
    api_url = (
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{GH_WORKFLOW}/runs"
    )
    r = requests.get(api_url, params={"status": "success", "per_page": 1})
    run_id = r.json()["workflow_runs"][0]["id"]

    art_url = f"https://api.github.com/repos/{GH_REPO}/actions/runs/{run_id}/artifacts"
    arts = requests.get(art_url).json()
    target = next(a for a in arts["artifacts"] if a["name"].endswith(".qcow2.zst"))
    return target["download_url"], target["name"]


def download_and_extract(url, filename):
    print(f"[*] Downloading {filename}...")
    subprocess.run(
        ["curl", "-L", "-H", f"Authorization: token {GH_TOKEN}", "-o", "temp.zip", url]
    )
    subprocess.run(["unzip", "-o", "temp.zip"])

    zst_file = filename + ".zst"
    raw_qcow2 = filename.replace(".zst", "")

    print(f"[*] Decompressing {zst_file}...")
    subprocess.run(["zstd", "-d", zst_file, "-o", raw_qcow2])
    return raw_qcow2


def proxmox_disk_swap(qcow2_path):
    print(f"[*] Importing disk to Proxmox VM {VM_ID}...")
    subprocess.run(["qm", "disk", "import", VM_ID, qcow2_path, STORAGE])
    disk_name = f"{STORAGE}:vm-{VM_ID}-disk-0"
    subprocess.run(["qm", "set", VM_ID, "--virtio0", disk_name])


def fog_orchestration(image_name):
    print(f"[*] Registering image '{image_name}' in FOG...")
    img_payload = {
        "name": image_name,
        "path": image_name.replace(".", "_"),
        "imageTypeID": "1",
        "osID": "1",
    }
    img_resp = requests.post(
        f"{FOG_URL}/image/create", headers=HEADERS, json=img_payload
    )
    new_img_id = img_resp.json()["id"]

    host_resp = requests.get(f"{FOG_URL}/host", headers=HEADERS)
    host = next(
        h for h in host_resp.json()["hosts"] if h["mac"].lower() == VM_MAC.lower()
    )
    host_id = host["id"]

    requests.put(
        f"{FOG_URL}/host/{host_id}/edit", headers=HEADERS, json={"imageID": new_img_id}
    )
    requests.post(
        f"{FOG_URL}/host/{host_id}/task", headers=HEADERS, json={"taskTypeID": 1}
    )
    return host_id


def wait_for_completion(host_id):
    print("[*] Monitoring FOG Capture status...")
    while True:
        # Check active tasks
        tasks_resp = requests.get(f"{FOG_URL}/task/active", headers=HEADERS)
        active_tasks = tasks_resp.json().get("tasks", [])

        # If our host is no longer in the active task list, the capture is done
        is_active = any(str(t.get("hostID")) == str(host_id) for t in active_tasks)

        if not is_active:
            print("[+] Capture Complete. Cleaning up...")
            break

        time.sleep(30)  # Poll every 30 seconds


def main():
    download_url, filename = get_latest_artifact()
    raw_qcow2 = download_and_extract(download_url, filename)

    proxmox_disk_swap(raw_qcow2)
    host_id = fog_orchestration(filename)

    subprocess.run(["qm", "start", VM_ID])

    # New Polling Logic
    wait_for_completion(host_id)

    # Cleanup
    subprocess.run(["qm", "stop", VM_ID])
    os.remove("temp.zip")
    os.remove(filename + ".zst")
    os.remove(raw_qcow2)
    print("[!] All temporary files removed and VM powered down.")


if __name__ == "__main__":
    main()
