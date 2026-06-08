"""
models.py - Data models for Pinboard clipboard manager
"""


from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class ClipEntry:
    """Represents a single clipboard entry."""
    id: Optional[int] = None
    type: str = "text"           # "text", "html", "files", "image"
    content: str = ""            # plain text / file paths joined by newline
    html_content: Optional[str] = None
    image_dib: Optional[bytes] = None
    image_path: Optional[str] = None
    pinned: bool = False
    pinned_order: Optional[int] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None
    use_count: int = 0
    favorite: bool = False

    @property
    def display_text(self) -> str:
        """Return short preview text for UI display."""
        if self.type == "image":
            return "[Image]"
        if self.type == "files":
            paths = self.content.split("\n")
            if len(paths) == 1:
                return f"📁 {paths[0]}"
            return f"📁 {paths[0]}  (+{len(paths)-1} more)"
        # text / html
        text = self.content.strip().replace("\n", " ").replace("\r", "")
        return text[:200] if len(text) > 200 else text

    @property
    def type_icon(self) -> str:
        icons = {"text": "📝", "html": "🌐", "files": "📁", "image": "🖼️"}
        return icons.get(self.type, "📋")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "html_content": self.html_content,
            "image_dib": self.image_dib,
            "image_path": self.image_path,
            "pinned": int(self.pinned),
            "pinned_order": self.pinned_order,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "favorite": int(self.favorite),
        }

    @classmethod
    def from_row(cls, row: tuple) -> "ClipEntry":
        """Create ClipEntry from a database row tuple."""
        (
            id_, type_, content, html_content, image_dib, image_path,
            pinned, pinned_order, created_at, last_used,
            use_count, favorite
        ) = row
        return cls(
            id=id_,
            type=type_,
            content=content or "",
            html_content=html_content,
            image_dib=image_dib,
            image_path=image_path,
            pinned=bool(pinned),
            pinned_order=pinned_order,
            created_at=created_at or datetime.now().isoformat(),
            last_used=last_used,
            use_count=use_count or 0,
            favorite=bool(favorite),
        )
