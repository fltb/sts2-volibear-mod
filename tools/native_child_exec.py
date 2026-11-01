#!/usr/bin/env python3
"""POSIX exec boundary used inside xvfb-run; not a game launcher on import.

The outer process owns one session. This helper records its own PID and process
group immediately before exec, so the save oracle can bind receipts to the real
game PID instead of mistaking xvfb-run's shell for the game. No game data is read
or modified and the PID file is created exclusively in the current run directory.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid-file', type=Path, required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if os.name == 'nt' or not command or not args.token:
        parser.error('A POSIX exec command and invocation token are required')
    executable = Path(command[0])
    if not executable.is_absolute() or not executable.is_file():
        parser.error('The executable must be an existing absolute file')
    path = args.pid_file
    if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
        parser.error('PID receipt must have an existing absolute unredirected parent')
    receipt = {'schema': 1, 'token': args.token, 'pid': os.getpid(),
               'process_group': os.getpgrp(), 'executable': str(executable.resolve())}
    with path.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, separators=(',', ':'))
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.execv(str(executable), command)
    return 127  # exec never returns on success.


if __name__ == '__main__':
    raise SystemExit(main())
