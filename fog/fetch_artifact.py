import os
import zipfile
from pathlib import Path

import requests

# --- CONFIGURATION ---
GH_REPO = "Kramden/kramden-iso-builder"
GH_WORKFLOW = "build-image.yaml"
GH_BRANCH = "noble"
GH_TOKEN = os.environ.get("GH_TOKEN", "")

REQUEST_TIMEOUT = 30
TEMP_ZIP = Path("temp.zip")

GITHUB_HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def github_get(url, **kwargs):
    response = requests.get(
        url,
        headers=GITHUB_HEADERS,
        timeout=REQUEST_TIMEOUT,
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


def get_latest_artifact():
    print(f"[*] Querying GitHub for latest successful {GH_WORKFLOW} run on {GH_BRANCH}...")
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
        available = [
            f"{a.get('name')} (expired={a.get('expired')})" for a in artifacts
        ]
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
    raw_qcow2 = zst_path.with_suffix("")
    print(f"[*] Decompressing {zst_path} -> {raw_qcow2}...")
    import subprocess
    subprocess.run(["zstd", "-d", str(zst_path), "-o", str(raw_qcow2)], check=True)
    zst_path.unlink()

    print(f"[+] Done: {raw_qcow2}")
    return raw_qcow2


def main():
    if not GH_TOKEN:
        raise ValueError("Set the GH_TOKEN environment variable before running.")

    download_url, artifact_name = get_latest_artifact()
    download_and_extract(download_url, artifact_name)


if __name__ == "__main__":
    main()
