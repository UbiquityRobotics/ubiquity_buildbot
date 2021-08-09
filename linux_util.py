import os, sys
import subprocess
import crypt

from typing import List


def create_user(username: str, password: str, display_name="Ubuntu User"):
    hashed_password = crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))

    subprocess.run(
        [
            "adduser",
            "--gecos",
            "Ubuntu User",
            "--add_extra_groups",
            "--disabled-password",
            username,
        ],
        check=True,
    )
    subprocess.run(
        [
            "usermod",
            "-p",
            hashed_password,
            username,
        ]
    )
    subprocess.run(["chown", "-R", f"{username}:{username}", f"/home/{username}"])


def du_mb(path: str) -> int:
    string_size = subprocess.run(
        ["du", "-sh", "--block-size=1MiB", path],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.split()[0]

    return int(string_size)


def add_user_sudo(username: str):
    subprocess.run(["usermod", "-a", "-G", "sudo", username])


def make_executable(path: str):
    mode = os.stat(path).st_mode
    mode |= (mode & 0o444) >> 2  # copy R bits to X
    os.chmod(path, mode)


def run_as_user(user: str, command: List[str], **kwargs):
    cmd = ["sudo", "-u", user]
    cmd.extend(command)
    subprocess.run(cmd, **kwargs)
