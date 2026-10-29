"""Candidate PostgreSQL cluster management. Isolated: own data dir, socket dir, port.

The candidate cluster never uses the legacy endpoint (socket /tmp, port 55432).
All paths live under candidate_pg/ inside the isolated side root.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

SIDE = Path(__file__).resolve().parent
DATA_DIR = SIDE / "candidate_pg" / "data"
LOG_FILE = SIDE / "candidate_pg" / "postgres.log"
PORT = 55441
HOST = "127.0.0.1"  # TCP loopback only; unix sockets disabled (path-length limit, /tmp:55432 isolation)
SUPERUSER = "candidate_t03"

PG_BIN = Path("/opt/homebrew/opt/postgresql@16/bin")


class ClusterError(RuntimeError):
    """A candidate cluster operation failed."""


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **kwargs,  # type: ignore[arg-type]
    )
    if result.returncode != 0:
        raise ClusterError(
            f"command {' '.join(cmd)} failed ({result.returncode}): "
            f"{result.stderr.strip()[-400:]}"
        )
    return result


def _psql_base(database: str) -> list[str]:
    return [
        str(PG_BIN / "psql"),
        "-h",
        HOST,
        "-p",
        str(PORT),
        "-U",
        SUPERUSER,
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
        "-X",
        "-q",
        "-tA",
    ]


def psql(database: str, sql: str) -> subprocess.CompletedProcess[str]:
    """Run SQL with ON_ERROR_STOP; any error raises."""
    return _run(_psql_base(database) + ["-c", sql])


def psql_file(database: str, path: Path) -> subprocess.CompletedProcess[str]:
    return _run(_psql_base(database) + ["-f", str(path)])


def is_running() -> bool:
    probe = subprocess.run(
        _psql_base("postgres") + ["-c", "SELECT 1"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0


def init_cluster() -> None:
    """Initialize data dir and start the isolated cluster (idempotent)."""
    if is_running():
        return
    if not DATA_DIR.exists():
        _run(
            [
                str(PG_BIN / "initdb"),
                "-D",
                str(DATA_DIR),
                "-U",
                SUPERUSER,
                "-A",
                "trust",
                "-E",
                "UTF8",
                "--no-instructions",
            ]
        )
    _run(
        [
            str(PG_BIN / "pg_ctl"),
            "-D",
            str(DATA_DIR),
            "-o",
            f"-p {PORT} -c listen_addresses='127.0.0.1' -c unix_socket_directories=''",
            "-l",
            str(LOG_FILE),
            "start",
        ]
    )
    for _ in range(50):
        if is_running():
            return
        time.sleep(0.2)
    raise ClusterError("candidate cluster did not become ready")


def stop_cluster() -> None:
    if DATA_DIR.exists():
        subprocess.run(
            [str(PG_BIN / "pg_ctl"), "-D", str(DATA_DIR), "stop", "-m", "fast"],
            capture_output=True,
            text=True,
            check=False,
        )


def create_database(name: str) -> None:
    _run(
        [
            str(PG_BIN / "createdb"),
            "-h",
            HOST,
            "-p",
            str(PORT),
            "-U",
            SUPERUSER,
            name,
        ]
    )


def drop_database(name: str) -> None:
    _run(
        [
            str(PG_BIN / "dropdb"),
            "--if-exists",
            "-h",
            HOST,
            "-p",
            str(PORT),
            "-U",
            SUPERUSER,
            name,
        ]
    )


def database_exists(name: str) -> bool:
    probe = subprocess.run(
        _psql_base("postgres")
        + ["-tAc", f"SELECT 1 FROM pg_database WHERE datname='{name}'"],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.stdout.strip() == "1"


def server_version() -> str:
    result = psql("postgres", "SHOW server_version_num;")
    return result.stdout.strip()


def destroy_cluster() -> None:
    """Stop the cluster and remove the data dir entirely (test reset)."""
    stop_cluster()
    if (SIDE / "candidate_pg").exists():
        shutil.rmtree(SIDE / "candidate_pg")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "stop", "status", "destroy"])
    args = parser.parse_args()
    try:
        if args.action == "init":
            init_cluster()
            print(json.dumps({"status": "running", "port": PORT, "host": HOST}))
        elif args.action == "stop":
            stop_cluster()
            print(json.dumps({"status": "stopped"}))
        elif args.action == "destroy":
            destroy_cluster()
            print(json.dumps({"status": "destroyed"}))
        else:
            print(
                json.dumps(
                    {
                        "status": "running" if is_running() else "stopped",
                        "port": PORT,
                        "host": HOST,
                    }
                )
            )
    except ClusterError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
