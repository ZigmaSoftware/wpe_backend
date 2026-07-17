from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEET_RANGE = "A:Z"
MAX_COLUMNS = 26


class TaskTrackerSheetError(RuntimeError):
    """Raised when the Google Sheet cannot be read or written."""

    def __init__(self, message: str, *, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


def _sheet_permission_error(action: str) -> TaskTrackerSheetError:
    return TaskTrackerSheetError(
        f"Google Sheets permission denied while trying to {action}. Share the sheet with the service-account email as Editor.",
        status_code=403,
    )


def _sheet_http_error(action: str, fallback: str, exc: HttpError) -> TaskTrackerSheetError:
    if getattr(exc.resp, "status", None) == 403:
        return _sheet_permission_error(action)

    return TaskTrackerSheetError(fallback, status_code=getattr(exc.resp, "status", 500))


def _require_setting(name: str) -> Any:
    value = getattr(settings, name, None)
    if value in (None, ""):
        raise ImproperlyConfigured(f"{name} must be configured for the task tracker.")
    return value


@lru_cache(maxsize=1)
def _sheet_service():
    key_path = Path(str(_require_setting("GOOGLE_KEY_PATH"))).expanduser()
    if not key_path.is_file():
        raise ImproperlyConfigured(f"Google service-account key was not found at {key_path}.")

    credentials = service_account.Credentials.from_service_account_file(
        str(key_path),
        scopes=[GOOGLE_SHEETS_SCOPE],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _sheet_config() -> tuple[str, str, int]:
    return (
        str(_require_setting("TASK_TRACKER_SPREADSHEET_ID")),
        str(_require_setting("TASK_TRACKER_SHEET_TAB")),
        int(_require_setting("TASK_TRACKER_SHEET_GID")),
    )


def _normalize_cells(cells: list[str]) -> list[str]:
    return ["" if cell is None else str(cell) for cell in cells[:MAX_COLUMNS]]


def list_rows() -> dict[str, Any]:
    spreadsheet_id, tab_name, _sheet_gid = _sheet_config()

    try:
        response = (
            _sheet_service()
            .spreadsheets()
            .values()
            .get(
                spreadsheetId=spreadsheet_id,
                range=f"{tab_name}!{SHEET_RANGE}",
            )
            .execute()
        )
    except HttpError as exc:
        raise _sheet_http_error("read the task tracker sheet", "Unable to load the task tracker sheet.", exc) from exc

    values = response.get("values", [])
    headers = [str(cell) for cell in values[0]] if values else []
    rows = [
        {
            "_row": row_number,
            "cells": [str(cell) for cell in cells],
        }
        for row_number, cells in enumerate(values[1:], start=2)
    ]
    return {"headers": headers, "rows": rows}


def add_row(cells: list[str]) -> None:
    spreadsheet_id, tab_name, _sheet_gid = _sheet_config()

    try:
        (
            _sheet_service()
            .spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=f"{tab_name}!{SHEET_RANGE}",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [_normalize_cells(cells)]},
            )
            .execute()
        )
    except HttpError as exc:
        raise _sheet_http_error("add a task tracker row", "Unable to add a row to the task tracker sheet.", exc) from exc


def update_row(row_number: int, cells: list[str]) -> None:
    spreadsheet_id, tab_name, _sheet_gid = _sheet_config()

    try:
        (
            _sheet_service()
            .spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=f"{tab_name}!A{row_number}:Z{row_number}",
                valueInputOption="USER_ENTERED",
                body={"values": [_normalize_cells(cells)]},
            )
            .execute()
        )
    except HttpError as exc:
        raise _sheet_http_error(
            "update the selected task tracker row",
            "Unable to update the selected task tracker row.",
            exc,
        ) from exc


def delete_row(row_number: int) -> None:
    spreadsheet_id, _tab_name, sheet_gid = _sheet_config()

    try:
        (
            _sheet_service()
            .spreadsheets()
            .batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={
                    "requests": [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": sheet_gid,
                                    "dimension": "ROWS",
                                    "startIndex": row_number - 1,
                                    "endIndex": row_number,
                                }
                            }
                        }
                    ]
                },
            )
            .execute()
        )
    except HttpError as exc:
        raise _sheet_http_error(
            "delete the selected task tracker row",
            "Unable to delete the selected task tracker row.",
            exc,
        ) from exc
