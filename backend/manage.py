#!/usr/bin/env python
"""Точка входа для команд управления Django."""

import os
import sys

from django.core.management import execute_from_command_line


def main():
    """Настраивает окружение и выполняет переданную команду Django."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
