import argparse
import json
import logging
import os
import re
import sys
import textwrap
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from itertools import pairwise
from operator import itemgetter
from pathlib import Path

import docx
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.enum.text import WD_LINE_SPACING
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import parse_xml
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.document_loaders import BaseBlobParser, Blob
from langchain_core.documents import Document
from langchain_core.prompt_values import PromptValue
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from langchain_openai import ChatOpenAI
from openai import OpenAIError
from pydantic import BaseModel, Field

from hw01 import REQUIREMENTS

MEMORY_FILE = Path(__file__).parent / "memory.json"
LOG_DIR = Path(__file__).parent / "logs" / "hw02"
EXIT_COMMAND = "/exit"
TITLE_PAGE_LIMIT = 2000
DRAWINGML = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
ALIGNMENTS = {"start": "left", "end": "right", "both": "justify"}

ASK_FILE = "Укажите путь к файлу ВКР в формате .docx."
ASK_NEXT_FILE = "Чтобы проверить другой файл, укажите путь к нему."
NOT_DOCX = "Прочитать могу только .docx: сохраните файл в этом формате."
NO_SUCH_FILE = "Файл {path} не найден."
ASK_FACTS = "На титульном листе не нашёл {missing}. Напишите, пожалуйста."
ASK_FIX = "Напишите правильные вуз и институт."
NO_REQUIREMENTS = "Требований для «{institute}» у меня пока нет."
CONFIRM = "{university}, {institute}. Проверю по документам: {documents}. Начать анализ?"
PROBLEMS_FOUND = "Нашёл нарушения:"
NO_PROBLEMS = "Нарушений не нашёл."
NOT_CHECKED = "Не проверял: {text} ({source})."

MESSAGES = {
    "margin": "{side} поле: {actual} мм, нужно {expected} мм",
    "section_margin": "{side} поле в разделе документа {section}: {actual} мм, нужно {expected} мм",
    "text": "{property}: {actual}, нужно {expected}; абзацев {count}, например {example}",
    "bold": "полужирный шрифт; абзацев {count}, например {example}",
    "missing_section": "нет раздела «{name}»",
    "no_main_sections": "нет пронумерованных разделов основной части",
    "heading_period": "точка в конце заголовка {example}",
    "heading_lowercase": "заголовок со строчной буквы {example}",
    "heading_size": "размер шрифта заголовка {example}: {actual} пт, нужно {expected} пт",
    "heading_numbered": "заголовок {example} не нумеруется",
    "section_unnumbered": "раздел без номера {example}",
    "subsection_number": "номер подраздела {example} не из номеров раздела и подраздела",
    "few_sources": "источников: {actual}, нужно не менее {expected}",
    "unnumbered_sources": "источники без номера: {count}, например {example}",
    "foreign_first": "иностранный источник перед русскими: {example}",
    "order": "нарушен алфавитный порядок: {example} перед {following}",
}
FACT_NAMES = {"university": "вуз", "institute": "институт"}
SIDES = {"left": "левое", "right": "правое", "top": "верхнее", "bottom": "нижнее"}
TEXT_PROPERTIES = {
    "font": "шрифт",
    "size": "размер шрифта",
    "color": "цвет шрифта",
    "line_spacing": "междустрочный интервал",
    "first_line_indent": "отступ первой строки",
    "alignment": "выравнивание",
}
ALIGNMENT_NAMES = {
    "left": "по левому краю",
    "center": "по центру",
    "right": "по правому краю",
    "justify": "по ширине",
}

log = logging.getLogger(__name__)


def words(text: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", text.lower().replace("ё", "е")).split()


def stated(value: str, text: str) -> bool:
    """The words of the value occur in the text in a row."""
    return bool(words(value)) and f" {' '.join(words(value))} " in f" {' '.join(words(text))} "


def without_number(text: str) -> str:
    return re.sub(r"^\s*\d+(\.\d+)*[.)]?\s*", "", text).strip()


def number(value: float) -> str:
    return f"{value:g}".replace(".", ",")


class Facts(BaseModel):
    """Facts about the student; the university and institute decide the requirements."""

    university: str | None = Field(None, description="вуз")
    institute: str | None = Field(None, description="институт или факультет")
    department: str | None = Field(None, description="кафедра")

    @property
    def missing(self) -> list[str]:
        """Facts the requirements depend on that are not known yet."""
        return [name for name in ("university", "institute") if getattr(self, name) is None]


class Consent(BaseModel):
    agrees: bool = Field(description="the student agrees to start the analysis")


@dataclass
class Problem:
    """A place where the thesis breaks a rule; `kind` names its line in MESSAGES."""

    kind: str
    values: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return MESSAGES[self.kind].format(**self.values)


class JsonStore:
    """Values under namespaces and keys, as in a LangGraph store, kept in a JSON file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def get(self, namespace: tuple[str, ...], key: str) -> dict | None:
        node = self.data
        for part in namespace:
            node = node.get(part, {})
        return node.get(key)

    def put(self, namespace: tuple[str, ...], key: str, value: dict) -> None:
        node = self.data
        for part in namespace:
            node = node.setdefault(part, {})
        node[key] = value
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


class Memory:
    """What the agent knows about a user: for now, the facts under the user's id."""

    def __init__(self, store: JsonStore, user_id: str) -> None:
        self.store = store
        self.namespace = (user_id,)

    def facts(self) -> Facts:
        return Facts.model_validate(self.store.get(self.namespace, "facts") or {})

    def learn(self, inputs: dict) -> Facts:
        """Chain step that saves new facts: adds them to the known ones, a correction replaces
        them. Returns everything known."""
        known = self.facts().model_dump(exclude_none=True)
        new = inputs["facts"].model_dump(exclude_none=True)
        facts = Facts.model_validate(known | new if inputs["correct"] else new | known)
        self.store.put(self.namespace, "facts", facts.model_dump(exclude_none=True))
        return facts


class Formatting:
    """Formatting that Word applies to a paragraph (ECMA-376, 17.7.2): direct formatting first,
    then the character style, the paragraph style and the styles it is based on, then the
    document defaults."""

    def __init__(self, document) -> None:
        styles = document.styles.element
        self.paragraph_defaults = next(iter(styles.xpath("w:docDefaults/w:pPrDefault/w:pPr")), None)
        self.run_defaults = next(iter(styles.xpath("w:docDefaults/w:rPrDefault/w:rPr")), None)
        self.theme_fonts = {}
        try:
            theme = parse_xml(document.part.part_related_by(RT.THEME).blob)
        except KeyError:
            return
        for kind in ("major", "minor"):
            path = f"a:themeElements/a:fontScheme/a:{kind}Font/a:latin/@typeface"
            self.theme_fonts[kind] = next(iter(theme.xpath(path, namespaces=DRAWINGML)), None)

    def describe(self, paragraph: Paragraph) -> dict:
        chain = self.chain(paragraph._p.pPr, paragraph.style, "pPr", self.paragraph_defaults)
        spacing = next((p for p in chain if p.spacing_line is not None), None)
        if spacing is None:
            line_spacing = 1.0
        elif spacing.spacing_lineRule in (None, WD_LINE_SPACING.MULTIPLE):
            line_spacing = round(spacing.spacing_line.pt / 12, 2)
        else:
            line_spacing = f"{spacing.spacing_line.pt:g} пт"
        outline = self.first(
            chain, lambda p: p.outlineLvl.val if p.outlineLvl is not None else None
        )
        numbering = self.first(chain, lambda p: p.xpath("w:numPr/w:numId/@w:val") or None)
        indent = self.first(chain, lambda p: p.first_line_indent)
        # read as text: python-docx knows no "start" and "end", which newer Word writes
        alignment = self.first(chain, lambda p: next(iter(p.xpath("w:jc/@w:val")), None), "left")
        runs = [self.run(paragraph, run) for run in paragraph.runs if run.text.strip()]
        return {
            "style": paragraph.style.name,
            "heading": outline + 1 if outline is not None and outline < 9 else None,
            "list": numbering not in (None, ["0"]) or paragraph.style.name.startswith("List"),
            "math": bool(paragraph._p.xpath(".//m:oMath")),
            "drawing": bool(paragraph._p.xpath(".//w:drawing")),
            "alignment": ALIGNMENTS.get(alignment, alignment),
            "line_spacing": line_spacing,
            "first_line_indent": round(indent.cm, 2) if indent is not None else 0.0,
            "page_break_before": self.first(chain, lambda p: p.pageBreakBefore_val, False),
            "fonts": sorted({font for font, _, _, _ in runs if font}),
            "sizes": sorted({size for _, size, _, _ in runs}),
            "bold": any(bold for _, _, bold, _ in runs),
            "colors": sorted({color for _, _, _, color in runs}),
        }

    def run(self, paragraph: Paragraph, run) -> tuple[str | None, float, bool, str]:
        chain = self.chain(run._r.rPr, run.style, "rPr")
        chain += self.chain(None, paragraph.style, "rPr", self.run_defaults)
        size = self.first(chain, lambda r: r.sz_val)
        return (
            self.first(chain, self.font),
            size.pt if size is not None else 10.0,
            self.first(chain, lambda r: r.b.val if r.b is not None else None, False),
            str(self.first(chain, lambda r: r.color.val if r.color is not None else None, "auto")),
        )

    def font(self, properties) -> str | None:
        """A theme font wins over the font named next to it, as in Word."""
        fonts = properties.rFonts
        if fonts is None:
            return None
        theme = fonts.get(qn("w:asciiTheme"))
        return self.theme_fonts.get(theme[:5]) if theme else fonts.get(qn("w:ascii"))

    @staticmethod
    def chain(direct, style, part: str, defaults=None) -> list:
        """Properties from the most specific level to the least: direct, styles, defaults."""
        levels = [direct]
        while style is not None:
            levels.append(getattr(style.element, part))
            style = style.base_style
        return [level for level in [*levels, defaults] if level is not None]

    @staticmethod
    def first(chain: list, get, default=None):
        """The value from the first level of the chain that sets it."""
        return next((value for level in chain if (value := get(level)) is not None), default)


class DocxParser(BaseBlobParser):
    """Sections and blocks of a docx with the formatting Word applies to each paragraph.

    A paragraph is marked `new_page` when the file itself starts a page there: a typed page break,
    a section break or "page break before". Pages count the breaks Word marks when it lays the
    document out or, in a file without them, those explicit starts. A page that text simply flows
    onto may have no break, so the page number serves to find the title page and nothing more.
    """

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        with blob.as_bytes_io() as file:
            document = docx.Document(file)
        for index, section in enumerate(document.sections, 1):
            margins = {
                side: round(getattr(section, f"{side}_margin").mm, 1)
                for side in ("left", "right", "top", "bottom")
            }
            landscape = section.orientation == WD_ORIENT.LANDSCAPE
            metadata = {"kind": "section", "number": index, "landscape": landscape, **margins}
            yield Document(page_content="", metadata=metadata)
        formatting = Formatting(document)
        laid_out = bool(document.element.body.xpath(".//w:lastRenderedPageBreak"))
        page, pending, seen = 1, False, False
        for block in self.blocks(document, document.element.body):
            if isinstance(block, Table):
                text = "\n".join(dict.fromkeys(c.text for row in block.rows for c in row.cells))
                yield Document(page_content=text, metadata={"kind": "table", "page": page})
                if laid_out:
                    page += len(block._tbl.xpath(".//w:lastRenderedPageBreak"))
                continue
            info = formatting.describe(block)
            before, after = self.typed_breaks(block)
            pending = pending or before or info["page_break_before"]
            content = bool(block.text.strip()) or info["drawing"]
            new_page, pending = (pending, False) if content else (False, pending)
            rendered = block.rendered_page_breaks if laid_out else []
            starts = bool(rendered) and rendered[0].preceding_paragraph_fragment is None
            page += starts if laid_out else new_page and seen
            metadata = {"kind": "paragraph", "page": page, "new_page": new_page, **info}
            yield Document(page_content=block.text, metadata=metadata)
            page += len(rendered) - starts
            section = block._p.pPr.sectPr if block._p.pPr is not None else None
            ends_section = section is not None and section.start_type != WD_SECTION_START.CONTINUOUS
            pending = pending or after or ends_section
            seen = seen or content

    @staticmethod
    def typed_breaks(paragraph: Paragraph) -> tuple[bool, bool]:
        """Whether a typed page break comes before the paragraph's text and whether after it;
        python-docx has no API for these breaks."""
        before = after = text = False
        for run in paragraph._p.xpath("./w:r"):
            if run.xpath("./w:br[@w:type='page']"):
                before, after = before or not text, after or text
            text = text or bool("".join(run.xpath("./w:t/text()")).strip())
        return before, after

    def blocks(self, document, parent) -> Iterator[Paragraph | Table]:
        """Paragraphs and tables in order, including those in content controls."""
        for child in parent.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, document)
            elif child.tag == qn("w:tbl"):
                yield Table(child, document)
            elif (
                child.tag == qn("w:sdt") and (content := child.find(qn("w:sdtContent"))) is not None
            ):
                yield from self.blocks(document, content)


class Thesis:
    """A parsed thesis: page setup, blocks in order and the parts of the text the checks need."""

    def __init__(self, blocks: list[Document]) -> None:
        self.sections = [b.metadata for b in blocks if b.metadata["kind"] == "section"]
        self.blocks = [b for b in blocks if b.metadata["kind"] != "section"]
        self.paragraphs = [
            b
            for b in self.blocks
            if b.metadata["kind"] == "paragraph"
            and not b.metadata["style"].lower().startswith("toc")
        ]
        self.titles = [self.title(b.page_content) for b in self.paragraphs]

    @classmethod
    def read(cls, path: Path) -> "Thesis":
        return cls(DocxParser().parse(Blob.from_path(path)))

    @property
    def title_page(self) -> str:
        """Text of the first page, cut short in case the file saved no break after it."""
        page = [b.page_content for b in self.blocks if b.metadata["page"] == 1]
        return "\n".join(page)[:TITLE_PAGE_LIMIT]

    def find(self, title: str) -> int | None:
        """Index of the first paragraph titled so, ignoring case, numbers and punctuation."""
        key = self.title(title)
        return self.titles.index(key) if key in self.titles else None

    def between(self, start: str, end: str | None = None) -> list[Document]:
        """Paragraphs after the one titled `start` and before the one titled `end`."""
        begin = self.find(start)
        if begin is None:
            return []
        stop = None
        if end is not None:
            key = self.title(end)
            stop = next(
                (i for i in range(begin + 1, len(self.titles)) if self.titles[i] == key), None
            )
        return self.paragraphs[begin + 1 : stop]

    def attached(self) -> set[int]:
        """Ids of the paragraphs that belong to a picture, table or formula rather than to the text:
        the caption under a picture or above a table, the explanation under a formula."""
        found, previous = set(), {}
        for block in self.blocks:
            info = block.metadata
            if info["kind"] == "table" and previous.get("kind") == "paragraph":
                found.add(previous["id"])
            elif info["kind"] == "paragraph" and (previous.get("drawing") or previous.get("math")):
                found.add(id(block))
            if info["kind"] == "table" or block.page_content.strip() or info.get("drawing"):
                previous = {"id": id(block), **info}
        return found

    @staticmethod
    def title(text: str) -> str:
        return " ".join(words(without_number(text)))

    @staticmethod
    def quote(block: Document) -> str:
        text = " ".join(block.page_content.split())
        return f"«{text[:40]}…»" if len(text) > 40 else f"«{text}»"


class Check(ABC):
    """A rule of the requirements that the code checks."""

    @abstractmethod
    def run(self, thesis: Thesis) -> list[Problem]:
        """Places where the thesis breaks the rule."""


@dataclass
class Margins(Check):
    left: float
    right: float
    top: float
    bottom: float
    tolerance: float = (
        1  # editors count a footer into the margin differently: LibreOffice adds 1 mm
    )

    def run(self, thesis: Thesis) -> list[Problem]:
        problems = []
        for section in thesis.sections:
            if section["landscape"]:
                continue  # a landscape page is turned to be read, so its sides are not the rule's
            for side, name in SIDES.items():
                expected = getattr(self, side)
                if abs(section[side] - expected) > self.tolerance:
                    kind = "section_margin" if len(thesis.sections) > 1 else "margin"
                    values = {"side": name, "actual": number(section[side])}
                    values |= {"expected": number(expected), "section": section["number"]}
                    problems.append(Problem(kind, values))
        return problems


@dataclass
class BodyText(Check):
    font: str
    size: float
    line_spacing: float
    first_line_indent: float
    alignment: str
    start: str = "Введение"
    end: str = "Список использованной литературы"

    def run(self, thesis: Thesis) -> list[Problem]:
        found = defaultdict(list)
        attached = thesis.attached()
        for block in thesis.between(self.start, self.end):
            info = block.metadata
            if not block.page_content.strip() or id(block) in attached:
                continue
            if info["heading"] is not None or info["list"] or info["math"] or info["drawing"]:
                continue
            for deviation in self.deviations(info):
                found[deviation].append(block)
        problems = []
        for (prop, actual), blocks in found.items():
            values = {"count": len(blocks), "example": Thesis.quote(blocks[0])}
            if prop == "bold":
                problems.append(Problem("bold", values))
            else:
                values |= {"property": TEXT_PROPERTIES[prop], "actual": actual}
                problems.append(Problem("text", values | {"expected": self.expected(prop)}))
        return problems

    def deviations(self, info: dict) -> Iterator[tuple[str, str]]:
        if fonts := [font for font in info["fonts"] if font != self.font]:
            yield "font", ", ".join(fonts)
        if sizes := [size for size in info["sizes"] if size != self.size]:
            yield "size", ", ".join(f"{number(size)} пт" for size in sizes)
        if info["bold"]:
            yield "bold", ""
        if colors := [color for color in info["colors"] if color not in ("auto", "000000")]:
            yield "color", ", ".join(colors)
        if info["line_spacing"] != self.line_spacing:
            spacing = info["line_spacing"]
            yield "line_spacing", number(spacing) if isinstance(spacing, float) else spacing
        if abs(info["first_line_indent"] - self.first_line_indent) > 0.05:
            yield "first_line_indent", f"{number(info['first_line_indent'])} см"
        if info["alignment"] != self.alignment:
            yield "alignment", ALIGNMENT_NAMES.get(info["alignment"], info["alignment"])

    def expected(self, prop: str) -> str:
        return {
            "font": self.font,
            "size": f"{number(self.size)} пт",
            "color": "чёрный",
            "line_spacing": number(self.line_spacing),
            "first_line_indent": f"{number(self.first_line_indent)} см",
            "alignment": ALIGNMENT_NAMES[self.alignment],
        }[prop]


@dataclass
class Structure(Check):
    sections: list[str]

    def run(self, thesis: Thesis) -> list[Problem]:
        problems = [
            Problem("missing_section", {"name": name})
            for name in self.sections
            if thesis.find(name) is None
        ]
        if not any(
            b.metadata["heading"] == 1
            and (b.metadata["list"] or without_number(b.page_content) != b.page_content.strip())
            for b in thesis.paragraphs
        ):
            problems.append(Problem("no_main_sections"))
        return problems


@dataclass
class Headings(Check):
    size: float
    plain_titles: list[str]
    start: str = "Содержание"
    main_part: tuple[str, str] = ("Введение", "Заключение")

    def run(self, thesis: Thesis) -> list[Problem]:
        plain = {Thesis.title(name) for name in self.plain_titles}
        main = {id(block) for block in thesis.between(*self.main_part)}
        problems = []
        for block in thesis.paragraphs[thesis.find(self.start) or 0 :]:
            info, text = block.metadata, block.page_content.strip()
            if info["heading"] is None or not text:
                continue
            example, name = {"example": Thesis.quote(block)}, without_number(text)
            numbered = info["list"] or name != text
            if text.endswith("."):
                problems.append(Problem("heading_period", example))
            if name[:1].islower():
                problems.append(Problem("heading_lowercase", example))
            if sizes := [size for size in info["sizes"] if size != self.size]:
                values = {"actual": ", ".join(map(number, sizes)), "expected": number(self.size)}
                problems.append(Problem("heading_size", example | values))
            if Thesis.title(name) in plain:
                if numbered:
                    problems.append(Problem("heading_numbered", example))
            elif info["heading"] == 1 and not numbered and id(block) in main:
                problems.append(Problem("section_unnumbered", example))
            elif info["heading"] == 2 and not info["list"] and not re.match(r"\d+\.\d+\s", text):
                problems.append(Problem("subsection_number", example))
        return problems


@dataclass
class Bibliography(Check):
    title: str
    min_sources: int

    def run(self, thesis: Thesis) -> list[Problem]:
        entries = []
        for block in thesis.between(self.title):
            # the list ends where the next part does: at a heading or on a new page
            if block.metadata["heading"] is not None or block.metadata["new_page"]:
                break
            if block.page_content.strip():
                entries.append(block)
        if thesis.find(self.title) is None:
            return []
        problems = []
        if len(entries) < self.min_sources:
            values = {"actual": len(entries), "expected": self.min_sources}
            problems.append(Problem("few_sources", values))
        plain = [
            e
            for e in entries
            if not e.metadata["list"] and without_number(e.page_content) == e.page_content.strip()
        ]
        if plain:
            values = {"count": len(plain), "example": Thesis.quote(plain[0])}
            problems.append(Problem("unnumbered_sources", values))
        latin = [bool(re.match(r"[a-z]", Thesis.title(e.page_content))) for e in entries]
        if True in latin and False in latin[latin.index(True) :]:
            example = Thesis.quote(entries[latin.index(True)])
            problems.append(Problem("foreign_first", {"example": example}))
        for foreign in (False, True):
            group = [e for e, is_latin in zip(entries, latin, strict=True) if is_latin == foreign]
            pair = next(
                ((a, b) for a, b in pairwise(group) if self.collation(a) > self.collation(b)), None
            )
            if pair:
                values = {"example": Thesis.quote(pair[0]), "following": Thesis.quote(pair[1])}
                problems.append(Problem("order", values))
        return problems

    @staticmethod
    def collation(block: Document) -> str:
        """Sort key where Russian letters come before Latin ones, as Russian sources come first."""
        key = Thesis.title(block.page_content)
        return "".join(chr(ord(c) + 0x1000) if "a" <= c <= "z" else c for c in key)


@dataclass
class Requirement:
    text: str
    source: str
    check: Check | None = None


@dataclass
class RequirementSet:
    """Requirements of one institute, with the names of its university and institute."""

    university: list[str]
    institute: list[str]
    requirements: list[Requirement]

    @classmethod
    def find(cls, facts: Facts) -> "RequirementSet | None":
        return next((known for known in REQUIREMENT_SETS if known.matches(facts)), None)

    def matches(self, facts: Facts) -> bool:
        return all(
            value is not None and any(stated(name, value) for name in names)
            for value, names in (
                (facts.university, self.university),
                (facts.institute, self.institute),
            )
        )

    @property
    def documents(self) -> list[str]:
        return list(dict.fromkeys(item.source.split(", ")[0] for item in self.requirements))

    def report(self, thesis: Thesis) -> str:
        lines, unchecked = [], []
        for item in self.requirements:
            if item.check is None:
                text = item.text.split(" (")[0]
                unchecked.append(NOT_CHECKED.format(text=text, source=item.source))
                continue
            problems = item.check.run(thesis)
            log.info("%s problems: %d", type(item.check).__name__, len(problems))
            lines += [f"{problem} ({item.source})" for problem in problems]
        numbered = [f"{i}. {line[0].upper()}{line[1:]}" for i, line in enumerate(lines, 1)]
        return "\n".join(([PROBLEMS_FOUND, *numbered] if numbered else [NO_PROBLEMS]) + unchecked)


SECTIONS = ["Содержание", "Введение", "Заключение", "Список использованной литературы"]

REQUIREMENT_SETS = [
    RequirementSet(
        university=["Челябинский государственный университет", "ЧелГУ"],
        institute=["Институт информационных технологий", "ИИТ"],
        requirements=[
            Requirement(
                **REQUIREMENTS["margins"][0], check=Margins(left=30, right=10, top=20, bottom=20)
            ),
            Requirement(
                **REQUIREMENTS["text"][0],
                check=BodyText(
                    font="Times New Roman",
                    size=14,
                    line_spacing=1.5,
                    first_line_indent=1.25,
                    alignment="justify",
                ),
            ),
            Requirement(**REQUIREMENTS["headings"][0], check=Structure(sections=SECTIONS)),
            Requirement(
                **REQUIREMENTS["headings"][1], check=Headings(size=14, plain_titles=SECTIONS)
            ),
            Requirement(**REQUIREMENTS["bibliography"][0]),
            Requirement(
                **REQUIREMENTS["bibliography"][1],
                check=Bibliography("Список использованной литературы", min_sources=20),
            ),
        ],
    ),
]

EXTRACT_SYSTEM = """\
Ты извлекаешь факты о выпускной работе студента из текста: её титульного листа или сообщения \
студента ассистенту, который проверяет оформление.

<fields>
{fields}
</fields>

<rules>
- Заполняй только поля, названные в тексте, остальные — null.
- Просьба или вопрос студента — не факт.
- Копируй значения так, как они написаны: все слова и их форму.
</rules>"""

# (text, facts to extract)
EXTRACT_EXAMPLES = [
    (
        "Министерство науки и высшего образования Российской Федерации\n"
        "Федеральное государственное автономное образовательное учреждение высшего образования\n"
        "«Национальный исследовательский Томский государственный университет»\n"
        "Институт прикладной математики и компьютерных наук\n"
        "Кафедра программной инженерии\n"
        "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА БАКАЛАВРА\n"
        "Сервис учёта учебной нагрузки\n"
        "Томск 2025",
        Facts(
            university="Национальный исследовательский Томский государственный университет",
            institute="Институт прикладной математики и компьютерных наук",
            department="Кафедра программной инженерии",
        ),
    ),
    (
        "«Новосибирский государственный технический университет»\n"
        "Кафедра вычислительной техники\n"
        "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА\n"
        "Новосибирск 2025",
        Facts(
            university="Новосибирский государственный технический университет",
            department="Кафедра вычислительной техники",
        ),
    ),
    ("Проверь, пожалуйста, мою ВКР.", Facts()),
    ("УрФУ, ИРИТ-РтФ.", Facts(university="УрФУ", institute="ИРИТ-РтФ")),
]

CONSENT_SYSTEM = """\
An assistant that checks thesis formatting named the student's university, institute and the \
requirement documents, then asked whether to start the analysis. Decide whether the student's \
reply means yes."""

# (student's reply, consent); yes and no alternate, or the model leans to the last answer
CONSENT_EXAMPLES = [
    ("Да", Consent(agrees=True)),
    ("Нет, институт указан неверно", Consent(agrees=False)),
    ("Давай", Consent(agrees=True)),
    ("Подожди", Consent(agrees=False)),
]


def log_step(label: str) -> Runnable:
    """Chain step that logs the value passing through it instead of showing it in the chat:
    the messages a prompt sends to the model or the model's answer."""

    def write(value: PromptValue | BaseModel) -> PromptValue | BaseModel:
        if isinstance(value, PromptValue):
            text = " | ".join(
                f"[{message.type}] {textwrap.shorten(message.content, 80, placeholder='…')}"
                for message in value.to_messages()
            )
        else:
            text = value.model_dump_json(exclude_none=True)
        log.info("%s: %s", label, text)
        return value

    return RunnableLambda(write, name=label)


class Interpreter:
    """Reads the student's texts with the model: facts from a title page or a reply, and consent."""

    def __init__(self, llm: ChatOpenAI) -> None:
        fields = "\n".join(f"- {name}: {f.description}" for name, f in Facts.model_fields.items())
        extract = self.prompt(EXTRACT_SYSTEM, EXTRACT_EXAMPLES).partial(fields=fields)
        self.extract = (
            RunnablePassthrough.assign(
                facts=extract
                | log_step("prompt")
                | llm.with_structured_output(Facts)
                | log_step("extracted")
            )
            | RunnableLambda(self.keep_stated)
            | log_step("kept")
        )
        consent = self.prompt(CONSENT_SYSTEM, CONSENT_EXAMPLES)
        self.consent = (
            consent | log_step("prompt") | llm.with_structured_output(Consent) | log_step("consent")
        )

    def agrees(self, reply: str) -> bool:
        return self.consent.invoke({"text": reply}).agrees

    @staticmethod
    def prompt(system: str, examples: list[tuple[str, BaseModel]]) -> ChatPromptTemplate:
        example = ChatPromptTemplate.from_messages([("human", "{text}"), ("ai", "{output}")])
        shots = FewShotChatMessagePromptTemplate(
            example_prompt=example,
            examples=[{"text": text, "output": out.model_dump_json()} for text, out in examples],
        )
        return ChatPromptTemplate.from_messages([("system", system)]) + shots + "{text}"

    @staticmethod
    def keep_stated(inputs: dict) -> Facts:
        """Keeps the facts the text states; a small model fills empty fields with made-up text."""
        facts = inputs["facts"].model_dump(exclude_none=True)
        return Facts(**{k: v for k, v in facts.items() if stated(v, inputs["text"])})


class Session:
    """One conversation: the file, the missing facts, consent to start and the report."""

    def __init__(self, interpreter: Interpreter, memory: Memory) -> None:
        self.interpreter = interpreter
        self.learn = (
            {"facts": interpreter.extract, "correct": itemgetter("correct")}
            | RunnableLambda(memory.learn)
            | log_step("facts")
        )
        self.facts = memory.facts()
        self.thesis: Thesis | None = None
        self.stage = "file"

    def start(self, path: Path | None) -> str:
        return self.open(path) if path else ASK_FILE

    def respond(self, message: str) -> str:
        if self.stage in ("file", "done"):
            path = Path(message.strip().strip("\"'")).expanduser()
            if not path.suffix:
                return ASK_FILE if self.stage == "file" else ASK_NEXT_FILE
            return self.open(path)
        if self.stage == "consent":
            if self.interpreter.agrees(message):
                self.stage = "done"
                return RequirementSet.find(self.facts).report(self.thesis)
            self.stage = "fix"
            return ASK_FIX
        self.facts = self.learn.invoke({"text": message, "correct": self.stage == "fix"})
        return self.ask_or_confirm()

    def open(self, path: Path) -> str:
        if path.suffix.lower() != ".docx":
            return NOT_DOCX
        if not path.is_file():
            return NO_SUCH_FILE.format(path=path)
        self.thesis = Thesis.read(path)
        log.info("opened %s: %d blocks", path.name, len(self.thesis.blocks))
        if self.facts.missing:
            self.facts = self.learn.invoke({"text": self.thesis.title_page, "correct": False})
        return self.ask_or_confirm()

    def ask_or_confirm(self) -> str:
        if self.facts.missing:
            self.stage = "facts"
            return ASK_FACTS.format(missing=" и ".join(FACT_NAMES[n] for n in self.facts.missing))
        requirements = RequirementSet.find(self.facts)
        if requirements is None:
            self.stage = "fix"
            return NO_REQUIREMENTS.format(institute=self.facts.institute)
        self.stage = "consent"
        return CONFIRM.format(
            university=self.facts.university,
            institute=self.facts.institute,
            documents=", ".join(f"«{name}»" for name in requirements.documents),
        )


def setup_logging(user_id: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / f"{user_id}.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # the SDK logs every HTTP request, which only repeats the chain's own records
    logging.getLogger("httpx2").setLevel(logging.WARNING)


def say(text: str) -> None:
    log.info("assistant: %s", text)
    print(text)


def repl(session: Session) -> None:
    while True:
        try:
            message = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if message == EXIT_COMMAND:
            return
        if not message:
            continue
        log.info("user: %s", message)
        try:
            say(session.respond(message))
        except KeyboardInterrupt:  # Ctrl+C during an answer cancels only the answer
            log.warning("answer interrupted")
            print("(interrupted)")
        except OpenAIError as e:
            log.error("request failed: %s", e)
            print(f"error: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normcontrol agent that checks a thesis in .docx and remembers the student.",
        epilog=(
            "The model is set by LLM_BASE_URL, LLM_API_KEY and LLM_MODEL. "
            f"{EXIT_COMMAND} or Ctrl+D quits."
        ),
    )
    parser.add_argument("file", nargs="?", type=Path, help="thesis in .docx; asked for if omitted")
    parser.add_argument("--user", default="student", help="user id in memory.json")
    args = parser.parse_args()

    setup_logging(args.user)
    log.info("session started, file: %s", args.file or "-")
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "local"),
        base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:8080/v1"),
        api_key=os.getenv("LLM_API_KEY", "none"),
        temperature=0.2,
        max_tokens=512,
    )
    session = Session(Interpreter(llm), Memory(JsonStore(MEMORY_FILE), args.user))
    try:
        say(session.start(args.file))
    except OpenAIError as e:
        log.error("request failed: %s", e)
        sys.exit(f"error: {e}")
    repl(session)


if __name__ == "__main__":
    main()
