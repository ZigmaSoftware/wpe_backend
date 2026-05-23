#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main():
    base_dir = Path(__file__).resolve().parent
    project_root = base_dir.parent
    core_system_dir = project_root / "core_system"

    for path in (base_dir, core_system_dir):
        path_string = str(path)
        if path_string not in sys.path:
            sys.path.insert(0, path_string)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grn_service.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

