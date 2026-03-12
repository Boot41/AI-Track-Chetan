from __future__ import annotations

import json
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

from app.schemas.ingestion import (
    IngestionInventory,
    IngestionInventoryItem,
    RawDocumentRegistration,
    SectioningHint,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DATA_ROOT = REPO_ROOT / "data" / "raw"
REQUIRED_MANIFEST_FIELDS = {"filename", "doc_type", "title", "sectioning_hint"}


def _document_id(content_id: str, filename: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{content_id}:{filename}"))


def list_manifest_paths(raw_root: Path = RAW_DATA_ROOT) -> list[Path]:
    return sorted(path for path in raw_root.glob("*/manifest.json") if path.is_file())


def load_manifest(manifest_path: Path) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return cast(dict[str, object], payload)


def build_ingestion_inventory(raw_root: Path = RAW_DATA_ROOT) -> IngestionInventory:
    items: list[IngestionInventoryItem] = []
    inventory_warnings: list[str] = []
    inventory_errors: list[str] = []
    manifest_paths = list_manifest_paths(raw_root)

    for manifest_path in manifest_paths:
        payload = load_manifest(manifest_path)
        content_id_raw = payload.get("content_id")
        title_raw = payload.get("title")
        if not isinstance(content_id_raw, str) or not content_id_raw.strip():
            inventory_errors.append(f"{manifest_path} is missing a valid content_id")
            continue
        if not isinstance(title_raw, str) or not title_raw.strip():
            inventory_errors.append(f"{manifest_path} is missing a valid title")
            continue
        content_id = content_id_raw
        title = title_raw
        documents = cast(list[object], payload.get("documents", []))
        warnings: list[str] = []
        errors: list[str] = []
        normalized_docs: list[RawDocumentRegistration] = []

        if not isinstance(documents, list) or not documents:
            errors.append(f"{manifest_path} has no documents")

        if manifest_path.parent.name != content_id:
            warnings.append("content_id does not match folder name")

        for entry in documents:
            if not isinstance(entry, dict):
                errors.append(f"{manifest_path} contains a non-object document entry")
                continue
            missing = REQUIRED_MANIFEST_FIELDS.difference(entry)
            if missing:
                errors.append(
                    f"{entry.get('filename', 'unknown')} missing required metadata: {sorted(missing)}"
                )
                continue

            filename = str(entry["filename"])
            source_path = manifest_path.parent / filename
            if not source_path.is_file():
                errors.append(f"{filename} listed in manifest but file is missing")
                continue

            sectioning_hint_raw = str(entry["sectioning_hint"])
            try:
                sectioning_hint = SectioningHint(sectioning_hint_raw)
            except ValueError:
                errors.append(
                    f"{filename} has invalid sectioning_hint={sectioning_hint_raw!r}"
                )
                continue
            normalized_docs.append(
                RawDocumentRegistration(
                    document_id=_document_id(content_id, filename),
                    content_id=content_id,
                    pitch_id=content_id,
                    source_path=str(source_path),
                    filename=filename,
                    title=str(entry["title"]),
                    manifest_doc_type=str(entry["doc_type"]),
                    sectioning_hint=sectioning_hint,
                    primary_use=str(entry["primary_use"]) if entry.get("primary_use") else None,
                    expected_entities=[str(value) for value in entry.get("expected_entities", [])],
                    expected_risks=[str(value) for value in entry.get("expected_risks", [])],
                    expected_signals=[str(value) for value in entry.get("expected_signals", [])],
                )
            )

        if normalized_docs:
            items.append(
                IngestionInventoryItem(
                    content_id=content_id,
                    title=title,
                    manifest_path=str(manifest_path),
                    document_count=len(normalized_docs),
                    documents=normalized_docs,
                    warnings=warnings,
                    errors=errors,
                )
            )
        else:
            inventory_errors.append(
                f"{manifest_path} has no valid document registrations after validation"
            )
            inventory_warnings.extend(warnings)
            inventory_errors.extend(errors)

    if not items and not manifest_paths:
        inventory_errors.append("No manifest.json files found under data/raw")

    comparison_dir = raw_root / "comparison_cases"
    if comparison_dir.exists() and not any(comparison_dir.glob("*.md")):
        inventory_warnings.append("comparison_cases exists but contains no markdown briefs")

    return IngestionInventory(
        raw_root=str(raw_root),
        items=items,
        warnings=inventory_warnings,
        errors=inventory_errors,
    )
