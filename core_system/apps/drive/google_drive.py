from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import UploadedFile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload


GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
GOOGLE_NATIVE_MIME_PREFIX = "application/vnd.google-apps"
DOWNLOAD_SPOOL_MAX_SIZE = 10 * 1024 * 1024


class DriveServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.data = data or {}


def _require_setting(name: str) -> Any:
    value = getattr(settings, name, None)
    if value in (None, ""):
        raise ImproperlyConfigured(f"{name} must be configured for Google Drive.")
    return value


def _parse_google_error(exc: HttpError) -> tuple[str, str | None]:
    try:
        payload = json.loads(exc.content.decode("utf-8"))
    except Exception:
        return str(exc), None

    error = payload.get("error", {})
    message = error.get("message") or str(exc)
    reason = None
    for detail in error.get("errors", []):
        reason = detail.get("reason")
        if reason:
            break
    return message, reason


def _drive_http_error(action: str, fallback: str, exc: HttpError) -> DriveServiceError:
    status_code = getattr(exc.resp, "status", 500)
    message, reason = _parse_google_error(exc)

    if reason == "storageQuotaExceeded" or "storageQuotaExceeded" in message:
        return DriveServiceError(
            "Google Drive storage quota blocked this action. Move the folder into a Shared Drive and add the service account as Content manager to enable upload/delete.",
            status_code=403,
            data={"reason": "storageQuotaExceeded"},
        )

    if status_code == 403:
        return DriveServiceError(
            f"Google Drive permission denied while trying to {action}. Check the folder sharing for the Drive service account.",
            status_code=403,
        )

    if status_code == 404:
        return DriveServiceError(
            f"Google Drive item was not found while trying to {action}.",
            status_code=404,
        )

    return DriveServiceError(fallback, status_code=status_code)


@lru_cache(maxsize=1)
def _drive_service():
    key_path = Path(str(_require_setting("GOOGLE_DRIVE_KEY_PATH"))).expanduser()
    if not key_path.is_file():
        raise ImproperlyConfigured(f"Google Drive service-account key was not found at {key_path}.")

    credentials = service_account.Credentials.from_service_account_file(
        str(key_path),
        scopes=[GOOGLE_DRIVE_SCOPE],
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _folder_id() -> str:
    return str(_require_setting("GOOGLE_DRIVE_FOLDER_ID"))


def _normalize_file(file: dict[str, Any]) -> dict[str, Any]:
    mime_type = file.get("mimeType", "")
    return {
        "id": file.get("id", ""),
        "name": file.get("name", ""),
        "mimeType": mime_type,
        "size": file.get("size"),
        "modifiedTime": file.get("modifiedTime"),
        "webViewLink": file.get("webViewLink"),
        "isGoogleNative": mime_type.startswith(GOOGLE_NATIVE_MIME_PREFIX),
    }


def list_files() -> dict[str, Any]:
    try:
        response = (
            _drive_service()
            .files()
            .list(
                q=f"'{_folder_id()}' in parents and trashed = false",
                fields="files(id,name,mimeType,size,modifiedTime,webViewLink)",
                pageSize=100,
                orderBy="folder,modifiedTime desc",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise _drive_http_error("list Drive files", "Unable to load Drive files.", exc) from exc

    return {"files": [_normalize_file(file) for file in response.get("files", [])]}


def upload_file(uploaded_file: UploadedFile) -> dict[str, Any]:
    uploaded_file.file.seek(0)
    media = MediaIoBaseUpload(
        uploaded_file.file,
        mimetype=uploaded_file.content_type or "application/octet-stream",
        resumable=True,
    )

    try:
        request = (
            _drive_service()
            .files()
            .create(
                body={"name": uploaded_file.name, "parents": [_folder_id()]},
                media_body=media,
                fields="id,name,mimeType,size,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
        )
        response = None
        while response is None:
            _status, response = request.next_chunk()
    except HttpError as exc:
        raise _drive_http_error("upload a Drive file", "Unable to upload the Drive file.", exc) from exc

    return _normalize_file(response)


def delete_file(file_id: str, *, permanent: bool = True) -> None:
    try:
        if permanent:
            (
                _drive_service()
                .files()
                .delete(fileId=file_id, supportsAllDrives=True)
                .execute()
            )
            return

        (
            _drive_service()
            .files()
            .update(
                fileId=file_id,
                body={"trashed": True},
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise _drive_http_error("delete a Drive file", "Unable to delete the Drive file.", exc) from exc


def get_file_metadata(file_id: str) -> dict[str, Any]:
    try:
        file = (
            _drive_service()
            .files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,size,modifiedTime,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except HttpError as exc:
        raise _drive_http_error("load Drive file details", "Unable to load Drive file details.", exc) from exc

    return _normalize_file(file)


def download_file(file_id: str):
    file = get_file_metadata(file_id)
    if file["isGoogleNative"]:
        raise DriveServiceError(
            "This Google file type opens in Drive and cannot be downloaded as raw file bytes.",
            status_code=400,
            data={"webViewLink": file.get("webViewLink")},
        )

    output = SpooledTemporaryFile(max_size=DOWNLOAD_SPOOL_MAX_SIZE, mode="w+b")
    try:
        request = _drive_service().files().get_media(fileId=file_id, supportsAllDrives=True)
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
    except HttpError as exc:
        output.close()
        raise _drive_http_error("download a Drive file", "Unable to download the Drive file.", exc) from exc

    output.seek(0)
    return file, output
