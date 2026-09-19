"""Fake worker: emulates the full download cycle without real torrents.

Usage: uv run python scripts/fake_worker.py

Cycle: register -> claim -> manifest -> heartbeat x3 -> put fake file -> complete
"""

import asyncio

import httpx

BASE_URL = "http://localhost:8000"
WORKER_NAME = "fake-worker-1"
REG_SECRET = "change-me"


async def main():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Register
        print("[1] Registering worker...")
        resp = await client.post(
            "/api/worker/register",
            json={
                "name": WORKER_NAME,
                "reg_secret": REG_SECRET,
            },
        )
        resp.raise_for_status()
        token = resp.json()["worker_token"]
        headers = {"X-Worker-Token": token}
        print(f"    Token: {token[:16]}...")

        # Claim loop
        while True:
            print("\n[2] Claiming task...")
            resp = await client.post("/api/worker/claim", headers=headers)

            if resp.status_code == 204:
                print("    No tasks in queue, waiting 10s...")
                await asyncio.sleep(10)
                continue

            resp.raise_for_status()
            task = resp.json()
            task_id = task["task_id"]
            print(f"    Got task: {task_id}")

            # Manifest (report fake files)
            print("[3] Sending manifest...")
            fake_files = [
                {"path": "movie.mkv", "size_bytes": 1024 * 1024},  # 1 MB
            ]
            resp = await client.post(
                "/api/worker/manifest",
                headers=headers,
                json={
                    "task_id": task_id,
                    "files": fake_files,
                },
            )
            resp.raise_for_status()
            manifest = resp.json()
            print(f"    Upload slots: {len(manifest['upload_slots'])}")

            # Heartbeats
            for i in range(3):
                print(f"[4] Heartbeat {i + 1}/3...")
                resp = await client.post(
                    "/api/worker/heartbeat",
                    headers=headers,
                    json={
                        "task_id": task_id,
                        "progress_pct": (i + 1) * 33,
                        "speed_bps": 1024 * 100,
                        "stage": f"downloading part {i + 1}/3",
                    },
                )
                resp.raise_for_status()
                await asyncio.sleep(1)

            # Upload fake file via presigned PUT
            print("[5] Uploading fake file...")
            for slot in manifest["upload_slots"]:
                resp = await client.put(
                    slot["put_url"],
                    content=b"\x00" * 1024,
                    headers=slot.get("headers", {}),
                )
                print(f"    PUT {slot['path']}: {resp.status_code}")

            # Complete
            print("[6] Completing task...")
            resp = await client.post(
                "/api/worker/complete",
                headers=headers,
                json={
                    "task_id": task_id,
                    "files": [
                        {"path": f["path"], "s3_key": "", "size_bytes": f["size_bytes"]}
                        for f in fake_files
                    ],
                },
            )
            resp.raise_for_status()
            print("    Task completed!")

            print("\n    Cycle done. Claiming next task...")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
