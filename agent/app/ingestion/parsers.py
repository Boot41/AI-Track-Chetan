from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from ..schemas.ingestion import (
    DocumentClassification,
    RawDocumentRegistration,
    SectionRecord,
)


def _make_section_id(document_id: str, section_key: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{document_id}:{section_key}"))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


@dataclass(slots=True)
class ParsedDocument:
    sections: list[SectionRecord]
    warnings: list[str]
    fallback_applied: bool


class Parser(Protocol):
    name: str

    def parse(
        self,
        registration: RawDocumentRegistration,
        classification: DocumentClassification,
        content: str,
    ) -> ParsedDocument: ...


def _paragraph_fallback(
    registration: RawDocumentRegistration,
    section_type: str,
    content: str,
    prefix: str,
) -> ParsedDocument:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    sections: list[SectionRecord] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        section_key = f"{prefix}-{index}"
        sections.append(
            SectionRecord(
                document_id=registration.document_id,
                section_id=_make_section_id(registration.document_id, section_key),
                section_key=section_key,
                title=None,
                section_type=section_type,
                content=paragraph,
                order_index=index - 1,
                source_reference=f"{registration.filename}#{section_key}",
                structure_confidence=0.35,
                metadata_json={"fallback_applied": True, "fallback_reason": "paragraph_chunk"},
            )
        )
    return ParsedDocument(
        sections=sections,
        warnings=["Structured parsing failed; paragraph fallback applied"],
        fallback_applied=True,
    )


class ScriptParser:
    name = "ScriptParser"

    _scene_pattern = re.compile(r"^## Scene (\d+)\s*-\s*(.+)$", re.MULTILINE)

    def parse(
        self,
        registration: RawDocumentRegistration,
        classification: DocumentClassification,
        content: str,
    ) -> ParsedDocument:
        matches = list(self._scene_pattern.finditer(content))
        if not matches:
            return _paragraph_fallback(registration, "script_fallback", content, "script-fallback")

        sections: list[SectionRecord] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            scene_number = match.group(1)
            scene_heading = match.group(2).strip()
            scene_body = content[start:end].strip()
            section_key = f"scene-{scene_number}"
            sections.append(
                SectionRecord(
                    document_id=registration.document_id,
                    section_id=_make_section_id(registration.document_id, section_key),
                    section_key=section_key,
                    title=f"Scene {scene_number} - {scene_heading}",
                    section_type="scene",
                    content=scene_body,
                    order_index=index,
                    source_reference=f"{registration.filename}#scene-{scene_number}",
                    structure_confidence=0.96,
                    metadata_json={
                        "scene_id": scene_number,
                        "scene_heading": scene_heading,
                        "parser": self.name,
                    },
                )
            )
        return ParsedDocument(sections=sections, warnings=[], fallback_applied=False)


class ContractParser:
    name = "ContractParser"

    _section_heading = re.compile(r"^##\s+(\d+)\.\s+(.+)$", re.MULTILINE)
    _clause_line = re.compile(r"^-\s+\*\*(\d+(?:\.\d+)*)\.?\s*([^*:]*?)[:]?\*\*\s*(.+)$")

    def parse(
        self,
        registration: RawDocumentRegistration,
        classification: DocumentClassification,
        content: str,
    ) -> ParsedDocument:
        headings = list(self._section_heading.finditer(content))
        if not headings:
            return _paragraph_fallback(
                registration,
                "contract_fallback",
                content,
                "contract-fallback",
            )

        sections: list[SectionRecord] = []
        for heading_index, heading in enumerate(headings):
            section_number = heading.group(1)
            section_title = heading.group(2).strip()
            start = heading.end()
            end = headings[heading_index + 1].start() if heading_index + 1 < len(headings) else len(content)
            body = content[start:end].strip()
            body_lines = body.splitlines()
            clause_matches: list[tuple[str, str, str]] = []
            first_clause_line_index: int | None = None
            for line_index, line in enumerate(body_lines):
                clause_match = self._clause_line.match(line.strip())
                if clause_match:
                    if first_clause_line_index is None:
                        first_clause_line_index = line_index
                    clause_matches.append(
                        (
                            clause_match.group(1),
                            clause_match.group(2).strip() or section_title.title(),
                            clause_match.group(3).strip(),
                        )
                    )
            if clause_matches:
                intro_lines = body_lines[: first_clause_line_index or 0]
                intro_text = "\n".join(line.strip() for line in intro_lines if line.strip())
                if intro_text:
                    intro_key = f"clause-{section_number}"
                    sections.append(
                        SectionRecord(
                            document_id=registration.document_id,
                            section_id=_make_section_id(registration.document_id, intro_key),
                            section_key=intro_key,
                            title=f"{section_number}. {section_title}",
                            section_type="clause",
                            content=intro_text,
                            order_index=len(sections),
                            source_reference=f"{registration.filename}#clause-{section_number}",
                            structure_confidence=0.88,
                            clause_id=section_number,
                            metadata_json={"parser": self.name, "parent_clause": section_number},
                        )
                    )
                for clause_index, (clause_id, clause_title, clause_text) in enumerate(clause_matches):
                    section_key = f"clause-{clause_id}"
                    sections.append(
                        SectionRecord(
                            document_id=registration.document_id,
                            section_id=_make_section_id(registration.document_id, section_key),
                            section_key=section_key,
                            title=f"{clause_id} {clause_title}".strip(),
                            section_type="clause",
                            content=clause_text,
                            order_index=len(sections),
                            source_reference=f"{registration.filename}#clause-{clause_id}",
                            structure_confidence=0.95,
                            clause_id=clause_id,
                            metadata_json={
                                "parent_clause": section_number,
                                "parser": self.name,
                                "clause_index": clause_index,
                            },
                        )
                    )
            else:
                section_key = f"clause-{section_number}"
                sections.append(
                    SectionRecord(
                        document_id=registration.document_id,
                        section_id=_make_section_id(registration.document_id, section_key),
                        section_key=section_key,
                        title=f"{section_number}. {section_title}",
                        section_type="clause",
                        content=body,
                        order_index=len(sections),
                        source_reference=f"{registration.filename}#clause-{section_number}",
                        structure_confidence=0.72,
                        clause_id=section_number,
                        metadata_json={"parser": self.name, "parent_clause": section_number},
                    )
                )

        return ParsedDocument(sections=sections, warnings=[], fallback_applied=False)


class DeckParser:
    name = "DeckParser"

    _slide_pattern = re.compile(r"^# Slide (\d+):\s*(.+)$", re.MULTILINE)

    def parse(
        self,
        registration: RawDocumentRegistration,
        classification: DocumentClassification,
        content: str,
    ) -> ParsedDocument:
        matches = list(self._slide_pattern.finditer(content))
        if not matches:
            return _paragraph_fallback(registration, "deck_fallback", content, "deck-fallback")

        sections: list[SectionRecord] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            slide_number = match.group(1)
            slide_title = match.group(2).strip()
            slide_body = content[start:end].strip()
            section_key = f"slide-{slide_number}"
            sections.append(
                SectionRecord(
                    document_id=registration.document_id,
                    section_id=_make_section_id(registration.document_id, section_key),
                    section_key=section_key,
                    title=slide_title,
                    section_type="slide",
                    content=slide_body,
                    order_index=index,
                    source_reference=f"{registration.filename}#slide-{slide_number}",
                    structure_confidence=0.94,
                    metadata_json={
                        "slide_number": int(slide_number),
                        "parser": self.name,
                    },
                )
            )
        return ParsedDocument(sections=sections, warnings=[], fallback_applied=False)


class ReportParser:
    name = "ReportParser"

    _heading_pattern = re.compile(r"^(#{2,6})\s+(.+)$", re.MULTILINE)

    def parse(
        self,
        registration: RawDocumentRegistration,
        classification: DocumentClassification,
        content: str,
    ) -> ParsedDocument:
        matches = list(self._heading_pattern.finditer(content))
        if not matches:
            return _paragraph_fallback(registration, "report_fallback", content, "report-fallback")

        sections: list[SectionRecord] = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            heading_level = len(match.group(1))
            heading_title = match.group(2).strip()
            section_body = content[start:end].strip()
            section_key = f"heading-{index + 1}-{_slug(heading_title)}"
            if not section_body:
                continue
            sections.append(
                SectionRecord(
                    document_id=registration.document_id,
                    section_id=_make_section_id(registration.document_id, section_key),
                    section_key=section_key,
                    title=heading_title,
                    section_type="memo_section" if classification.doc_type.value == "memo" else "report_section",
                    content=section_body,
                    order_index=index,
                    source_reference=f"{registration.filename}#{section_key}",
                    structure_confidence=0.9 if heading_level <= 3 else 0.82,
                    metadata_json={"heading_level": heading_level, "parser": self.name},
                )
            )
        if not sections:
            return _paragraph_fallback(registration, "report_fallback", content, "report-fallback")
        return ParsedDocument(sections=sections, warnings=[], fallback_applied=False)


class ParserRouter:
    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {
            "ScriptParser": ScriptParser(),
            "ContractParser": ContractParser(),
            "DeckParser": DeckParser(),
            "ReportParser": ReportParser(),
        }

    def get_parser(self, classification: DocumentClassification) -> Parser:
        return self._parsers[classification.parser_used]
