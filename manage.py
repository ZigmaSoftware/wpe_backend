#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent

    for project_path in (project_root / "core_system", project_root / "grn_service"):
        project_path_string = str(project_path)
        if project_path_string not in sys.path:
            sys.path.insert(0, project_path_string)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core_system.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
