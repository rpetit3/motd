#! /usr/bin/env python3
"""
Produce a summary of hard drives.

Inspiration is from FalconStats: https://github.com/Heholord/FalconStats
"""
from colorama import Back, Fore, Style
import executor

VERSION = "0.0.1"
RESET_ALL = Style.RESET_ALL


def execute(cmd, capture=False, capture_stderr=False, silent=False):
    """A simple wrapper around executor."""
    command = executor.ExternalCommand(
        cmd, capture=capture, capture_stderr=capture_stderr, silent=silent
    )
    command.start()

    if capture:
        return command.decoded_stdout


def has_permission(command):
    """Test if a user has permission to run a command."""
    try:
        execute(command, silent=True)
        return True
    except executor.ExternalCommandFailed as e:
        return False


def disk_usage(disks):
    print_filesystem = True
    MAX_CHARACTERS = 42
    print("Hard Disk Usage:")
    for disk in disks:
        usage = execute(f'df -h {disk["mountpoint"]}', capture=True)
        for line in usage.split('\n'):
            """
            Example Output
            Filesystem      Size  Used Avail Use% Mounted on
            /dev/sda2       190G   70G  111G  39% /
            """
            if print_filesystem and line.startswith("Filesystem"):
                print(f'  {line}')
                print_filesystem = False

            if line.endswith(disk["mountpoint"]):
                # 0 - Filesystem, 1-Size, 2-Used, 3-Avail, 4-Use%, 5-Mounted on
                cols = line.split()
                percent = int(cols[4].replace("%", ""))
                used = "=" * int(percent // (100 / MAX_CHARACTERS))
                free = "=" * (MAX_CHARACTERS - len(used))
                print(f"  {line.replace(f'{cols[0]}', cols[0])}")
                COLOR = Fore.GREEN
                if percent >= 90:
                    Fore.RED
                elif percent >= 70:
                    Fore.YELLOW
                print(f'  [{COLOR}{used}{RESET_ALL}{free}] - {disk["type"]}/{disk["raid"]}')
    print()


def hddtemp(disks):
    """
    If user has permission, print out HDD temps.
    """
    if has_permission(f'hddtemp {disks[0]}'):
        temps = []
        for disk in disks:
            output = execute(f'hddtemp {disk}', capture=True).rstrip().split(": ")
            drive = output[0].replace("/dev/", "")
            temp = int(output[2].split("°")[0])
            COLOR = Fore.BLACK
            BG_COLOR = Back.CYAN
            if temp >= 50:
                BG_COLOR = Back.RED
            elif temp >= 40:
                BG_COLOR = Back.YELLOW
            elif temp >= 25:
                BG_COLOR = Back.GREEN
            temps.append(f'  {BG_COLOR}{drive} {output[2]}{RESET_ALL}')

        print("Hard Disk Temperatures:")
        for i, temp in enumerate(temps):
            print(temp, end="")
            if (i + 1) % 5 == 0:
                print()
        print("\n")


def mdadm_status():
    """
    Check the status of mdadm managed disks.
    Example Output:

    Personalities : [raid1] [linear] [multipath] [raid0] [raid6] [raid5] [raid4] [raid10]
    md0 : active raid1 sdc1[1] sdb1[0]
          9766302720 blocks super 1.2 [2/2] [UU]
          bitmap: 0/73 pages [0KB], 65536KB chunk

    md1 : active raid1 sda1[0] sde1[1]
          1000072192 blocks super 1.2 [2/2] [UU]
          bitmap: 4/8 pages [16KB], 65536KB chunk

    unused devices: <none>
    """
    new_md = True
    md_arrays = []
    new_array = {"health": "HEALTHY"}
    for line in execute("cat /proc/mdstat", capture=True).split("\n"):
        if line:
            if line.split()[0] not in ["Personalities", "unused"]:
                if line.startswith(" "):
                    if "blocks" in line:
                        drives = line.split(" [", 1)[1]
                        total, active = drives.split("] [")[0].split("/")
                        total = int(total)
                        active = int(active)
                        status = drives.split("] [")[1].replace("]", "")
                        new_array["total_devices"] = total
                        new_array["active_devices"] = active
                        new_array["failed_devices"] = max(total - active, 0)

                        if new_array["failed_devices"]:
                            if new_array["state"] == "active":
                                new_array["health"] = "ERROR: DEGRADED!!!"
                            else:
                                new_array["health"] = "ERROR: FAILED!!!"
                else:
                    array = line.replace(":", "").split()
                    new_array["name"] = array[0]
                    new_array["state"] = array[1]
                    new_array["raid_level"] = array[2]
        else:
            if "name" in new_array:
                md_arrays.append(new_array)
            new_array = {"health": "HEALTHY"}

    if md_arrays:
        print("mdadm Managed Devices:")
        cols = ["Device", "State", "Level", "Total", "Active", "Failed",
                "Health"]
        print((
            f"  {cols[0]:<6}\t{cols[1]:>6}\t{cols[2]:>7}\t{cols[3]:>5}\t"
            f"{cols[4]:>5}\t{cols[5]:>6}\tHealth"
        ))
        for array in md_arrays:
            BG_COLOR = Back.RED
            if array["health"] == "HEALTHY":
                BG_COLOR = Back.GREEN
            print((
                f'  {array["name"]:<6}\t{array["state"]:>6}\t'
                f'{array["raid_level"]:>7}\t{array["total_devices"]:>5}\t'
                f'{array["active_devices"]:>6}\t{array["failed_devices"]:>6}\t'
                f'{BG_COLOR}{array["health"]}{RESET_ALL}'
            ))
        print()

if __name__ == '__main__':
    import argparse as ap
    import json
    import os
    import sys

    path = os.path.dirname(os.path.realpath(__file__))
    parser = ap.ArgumentParser(
        prog='disks.py',
        conflict_handler='resolve',
        description=("Produce a summary of hard drives.")
    )
    parser.add_argument('--version', action='version',
                        version='%(prog)s {0}'.format(VERSION))

    args = parser.parse_args()

    with open(f'{path}/config.json') as json_fh:
        config = json.load(json_fh)

    if config["diskspace"]["enabled"]:
        disk_usage(config["diskspace"]["disks"])

    if config["hddtemp"]["enabled"]:
        hddtemp(config["hddtemp"]["disks"])

    if config["mdstat"]["enabled"]:
        mdadm_status()
