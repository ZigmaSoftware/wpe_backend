#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main():
    base_dir = Path(__file__).resolve().parent
    base_dir_string = str(base_dir)
    if base_dir_string not in sys.path:
        sys.path.insert(0, base_dir_string)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_system.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

