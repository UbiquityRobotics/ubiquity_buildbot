import os
import subprocess
from contextlib import contextmanager
import shutil

import typing
from typing import Iterator


def create_image_file(path: str, boot_part_size: int, root_part_size: int):
    total_disk_size = boot_part_size + root_part_size
    print(f"Creating image file {total_disk_size} MiB")

    subprocess.run(
        ["dd", "if=/dev/zero", f"of={path}", "bs=1MiB", f"count={total_disk_size}"],
        check=True,
    )
    subprocess.run(["parted", "-s", path, "mktable", "msdos"], check=True)

    # Create a FAT32 partition
    subprocess.run(
        [
            "parted",
            "-a",
            "optimal",
            "-s",
            path,
            "mkpart",
            "primary",
            "fat32",
            "1",
            f"{boot_part_size}MiB",
        ],
        check=True,
    )

    # Create a ext4 partition starting at the end of boot part going to the end of the image
    subprocess.run(
        [
            "parted",
            "-a",
            "optimal",
            "-s",
            path,
            "mkpart",
            "primary",
            "ext4",
            f"{boot_part_size}MiB",
            "100%",
        ],
        check=True,
    )


@contextmanager
def loopdev_context_manager(image: str) -> Iterator[str]:
    loop = subprocess.run(
        ["losetup", "--show", "-f", "-P", image],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    yield loop
    subprocess.run(["losetup", "-d", loop], check=True)


@contextmanager
def mount_context_manager(device: str, mount_point: str, fs_type: str) -> Iterator[str]:
    mount_point_existed = False
    mounted = False
    if os.path.exists(mount_point):
        mount_point_existed = True
    else:
        os.makedirs(mount_point, exist_ok=True)
    try:
        subprocess.run(["mount", "-v", device, mount_point, "-t", fs_type], check=True)
        mounted = True
    except:
        print(f"Failed to mount {device} to {mount_point}")

    if mounted:
        yield mount_point
        subprocess.run(["sync"], check=True)
        subprocess.run(["umount", "-l", mount_point], check=True)

    if not mount_point_existed:
        shutil.rmtree(mount_point)
