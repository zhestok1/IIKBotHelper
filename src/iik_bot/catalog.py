import json
import re
from datetime import date
from importlib.resources import files
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Link(Model):
    label: str
    target: str


class Source(Model):
    label: str
    url: str

    @model_validator(mode="after")
    def valid_url(self) -> "Source":
        url = urlsplit(self.url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Источник должен иметь публичный HTTPS URL без учётных данных")
        return self


class Contact(Model):
    title: str
    details: str


class Card(Model):
    title: str
    text: str
    steps: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    children: list[Link] = Field(default_factory=list)
    contact_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    checked_at: date | None = None
    campaign_year: int | None = None
    expires_on: date | None = None

    def expired(self, today: date) -> bool:
        return bool(
            (self.expires_on and today > self.expires_on)
            or (self.campaign_year is not None and self.campaign_year != today.year)
        )


Role = Literal["applicant", "student"]


class Catalog(Model):
    schema_version: Literal[1]
    document_title: str
    document_review_date: date
    sections: list[str]
    student_order: list[str]
    sources: dict[str, Source]
    contacts: dict[str, Contact]
    cards: dict[str, Card]

    @model_validator(mode="after")
    def validate_graph(self) -> "Catalog":
        if len(self.sections) != 8 or len(set(self.sections)) != 8:
            raise ValueError("Главное меню должно содержать восемь разных разделов")
        if set(self.student_order) != set(self.sections) or len(self.student_order) != 8:
            raise ValueError("Оба меню должны включать все восемь разделов")
        for key in [*self.sections, "contacts"]:
            if key not in self.cards:
                raise ValueError(f"Отсутствует карточка {key}")
        for key, card in self.cards.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", key):
                raise ValueError(f"Недопустимый ID {key}")
            for link in card.children:
                if link.target not in self.cards:
                    raise ValueError(f"{key}: неизвестный переход {link.target}")
            if set(card.contact_ids) - self.contacts.keys():
                raise ValueError(f"{key}: неизвестный контакт")
            if set(card.source_ids) - self.sources.keys():
                raise ValueError(f"{key}: неизвестный источник")
        reachable: set[str] = set()

        def visit(key: str) -> None:
            if key in reachable:
                return
            reachable.add(key)
            for link in self.cards[key].children:
                visit(link.target)

        for key in [*self.sections, "contacts"]:
            visit(key)
        if missing := self.cards.keys() - reachable:
            raise ValueError(f"Карточки недоступны из меню: {sorted(missing)}")
        return self

    def menu(self, role: Role | None) -> list[str]:
        return self.student_order if role == "student" else self.sections

    def search(self, query: str, limit: int = 8) -> list[str]:
        # Короткие основы позволяют искать «общежитие» и «общежития» одинаково.
        def words(value: str) -> set[str]:
            return {
                w[:6]
                for w in re.findall(r"[а-яa-z0-9]+", value.lower().replace("ё", "е"))
                if len(w) > 2
            }

        terms = words(query[:300]) - {"как", "где", "для", "мне", "что", "это", "или", "нужен"}
        if not terms:
            return []
        scored = []
        for key, card in self.cards.items():
            title = words(card.title + " " + " ".join(card.keywords))
            body = words(card.text + " " + " ".join(card.documents + card.steps))
            score = 4 * len(terms & title) + len(terms & body)
            if score:
                scored.append((score, key))
        return [key for _, key in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]]


def load_catalog(path: Path | None = None) -> Catalog:
    raw = (
        path.read_text(encoding="utf-8")
        if path
        else (files("iik_bot").joinpath("content/catalog.json").read_text(encoding="utf-8"))
    )
    return Catalog.model_validate(json.loads(raw))
