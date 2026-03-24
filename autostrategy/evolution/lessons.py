"""Track lessons learned across iterations."""

import json
from pathlib import Path
from typing import List
from datetime import datetime


class LessonsTracker:
    """Persist lessons learned from strategy evolution."""
    
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.lessons: List[dict] = []
        self._load()
        
    def _load(self):
        """Load existing lessons if file exists."""
        if self.filepath.exists():
            with open(self.filepath, 'r') as f:
                for line in f:
                    if line.strip():
                        self.lessons.append(json.loads(line))
                        
    def add(self, lesson: str, category: str = "general"):
        """Add a new lesson."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "lesson": lesson,
            "category": category
        }
        self.lessons.append(entry)
        
        # Append to file
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, 'a') as f:
            f.write(json.dumps(entry) + "\n")
            
    def get_recent(self, n: int = 10) -> List[str]:
        """Get n most recent lessons as strings."""
        recent = self.lessons[-n:] if len(self.lessons) >= n else self.lessons
        return [l["lesson"] for l in recent]
    
    def get_by_category(self, category: str) -> List[str]:
        """Get lessons by category."""
        return [l["lesson"] for l in self.lessons if l.get("category") == category]
