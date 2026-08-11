from pydantic import BaseModel


class VisionContextResult(BaseModel):
    scene_description: str
    visible_text_or_graphics: str | None = None
    notable_entities: list[str] = []
