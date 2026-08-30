import mimetypes
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.asset import Asset
from app.models.generation_job import GenerationJob
from app.models.generation_output import GenerationOutput
from app.services.comfyui_client import ComfyUIClientError, download_output, get_history
from app.services.storage_assets import asset_directory, cleanup_asset_file


class GenerationArchiveError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message); self.code = code


def _files(history: dict[str, object], prompt_id: str) -> list[dict[str, str]]:
    entry = history.get(prompt_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("outputs"), dict): return []
    found = []
    for node_id in sorted(entry["outputs"], key=lambda value: (0, int(value)) if str(value).isdigit() else (1, str(value))):
        node = entry["outputs"][node_id]
        if not isinstance(node, dict): continue
        for key in ("images", "videos"):
            items = node.get(key)
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and all(isinstance(item.get(field), str) for field in ("filename", "subfolder", "type")):
                        found.append(item)
    return found


def _safe(item: dict[str, str]) -> str:
    name, folder = item["filename"], item["subfolder"]
    if Path(name).name != name or PureWindowsPath(name).name != name or Path(folder).is_absolute() or PureWindowsPath(folder).is_absolute() or ".." in Path(folder).parts or ".." in PureWindowsPath(folder).parts:
        raise GenerationArchiveError("OUTPUT_NOT_FOUND", "ComfyUI output path is invalid")
    return name


async def archive_generation(job_id: str) -> dict[str, object]:
    session = SessionLocal(); created_paths = []
    try:
        job = session.get(GenerationJob, job_id)
        if job is None or job.comfy_prompt_id is None: raise GenerationArchiveError("OUTPUT_NOT_FOUND", "Generation output is unavailable")
        if job.outputs: return {"type":"generation.completed", "job_id":job.id,"scene_id":job.scene_id,"status":"completed"}
        history = await get_history(job.comfy_prompt_id)
        files = _files(history, job.comfy_prompt_id)
        if not files: raise GenerationArchiveError("OUTPUT_NOT_FOUND", "ComfyUI history has no outputs")
        for index, item in enumerate(files):
            name = _safe(item); suffix = Path(name).suffix.lower(); asset_type = "video" if suffix in {".mp4", ".webm", ".mov"} else "image"
            data = await download_output(name, item["subfolder"], item["type"])
            directory = asset_directory(job.project_id, asset_type); directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{uuid4().hex}{suffix}"; path.write_bytes(data); created_paths.append(path)
            relative = f"{'videos' if asset_type == 'video' else 'images'}/{path.name}"
            asset = Asset(project_id=job.project_id, scene_id=job.scene_id, type=asset_type, role="output", relative_path=relative, thumbnail_path=None, mime_type=mimetypes.guess_type(name)[0] or "application/octet-stream", width=None, height=None, duration_seconds=None, size_bytes=len(data), hash=None)
            session.add(asset); session.flush(); session.add(GenerationOutput(generation_job_id=job.id, asset_id=asset.id, output_index=index))
        job.status="completed"; session.commit()
        return {"type":"generation.completed", "job_id":job.id,"scene_id":job.scene_id,"status":"completed"}
    except (GenerationArchiveError, ComfyUIClientError) as error:
        session.rollback(); job = session.get(GenerationJob, job_id)
        if job is not None: job.status="failed"; job.error_code=error.code; job.error_message=str(error); session.commit()
        for path in created_paths: cleanup_asset_file(path)
        return {"type":"generation.failed", "job_id":job_id,"status":"failed","error_code":error.code,"message":str(error)}
    finally: session.close()

