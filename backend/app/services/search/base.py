from abc import ABC, abstractmethod

from pydantic import BaseModel


class SearchResult(BaseModel):
    url: str
    title: str | None = None
    snippet: str = ""  # short relevant excerpt/summary as returned by the provider
    full_content: str = ""  # full extracted page text, if the provider returns it
    published_date: str | None = None
    raw: dict = {}


class SearchProvider(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[SearchResult]:
        raise NotImplementedError
