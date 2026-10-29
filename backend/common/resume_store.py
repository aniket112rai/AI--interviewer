import asyncio
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from common.config import settings
from common.schemas.profile import Profile


_RESUME_ID = re.compile(r"^[0-9a-f]{32}$")


def resume_path(resume_id: str) -> Path:
    if not _RESUME_ID.fullmatch(resume_id):
        raise ValueError("resume_id must be a lowercase UUID hex string.")
    return settings.data_dir / "resumes" / f"{resume_id}.json"


def _write_profile_atomically(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(profile, temporary_file, ensure_ascii=False, separators=(",", ":"))
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


async def write_profile(resume_id: str, profile: Profile) -> None:
    path = resume_path(resume_id)
    payload = profile.model_dump(mode="json")
    await asyncio.to_thread(_write_profile_atomically, path, payload)


def _read_profile(path: Path) -> Profile:
    return Profile.model_validate_json(path.read_text(encoding="utf-8"))


async def read_profile(resume_id: str) -> Profile:
    return await asyncio.to_thread(_read_profile, resume_path(resume_id))


def _delete_profile(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


async def delete_profile(resume_id: str) -> None:
    await asyncio.to_thread(_delete_profile, resume_path(resume_id))
