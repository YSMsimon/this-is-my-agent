from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Optional


class SkillManifest(BaseModel):
    name: str
    description: str
    path: Path

    class Config:
        arbitrary_types_allowed = True


class Skill(BaseModel):
    manifest: SkillManifest
    body: str

    class Config:
        arbitrary_types_allowed = True


class SkillManager:
    def __init__(self, skill_dir: Path):
        self.skill_dir = Path(skill_dir)
        self.skills: Dict[str, Skill] = {}

    def _parse_frontmatter(self, content: str) -> tuple[dict, str]:
        if not content.startswith('---'):
            return {}, content
        end = content.find('---', 3)
        if end == -1:
            return {}, content
        frontmatter_text = content[3:end].strip()
        body = content[end + 3:].strip()
        meta = {}
        for line in frontmatter_text.splitlines():
            if ':' in line:
                key, _, value = line.partition(':')
                meta[key.strip()] = value.strip()
        return meta, body

    def load_skills(self):
        if not self.skill_dir.exists():
            return
        for path in sorted(self.skill_dir.rglob("SKILL.md")):
            try:
                content = path.read_text(encoding='utf-8')
                meta, body = self._parse_frontmatter(content)
                name = meta.get('name', path.parent.name)
                description = meta.get('description', '')
                manifest = SkillManifest(name=name, description=description, path=path)
                self.skills[name] = Skill(manifest=manifest, body=body)
            except Exception as e:
                print(f"Warning: could not load skill at {path}: {e}")

    def list_skills(self) -> List[str]:
        return [
            f"- **{name}**: {skill.manifest.description}"
            for name, skill in self.skills.items()
        ]

    def preview_skill(self, name: str) -> Optional[str]:
        skill = self.skills.get(name)
        if not skill:
            available = ', '.join(self.skills.keys()) or 'none'
            return f"Skill '{name}' not found. Available: {available}"
        non_empty = [l for l in skill.body.splitlines() if l.strip()][:6]
        preview = '\n'.join(non_empty)
        return f"**{skill.manifest.name}**\n{skill.manifest.description}\n\n{preview}\n..."

    def get_skill(self, name: str) -> Optional[str]:
        print(f"Attempting to load skill: {name}")
        skill = self.skills.get(name)
        if not skill:
            available = ', '.join(self.skills.keys()) or 'none'
            return f"Skill '{name}' not found. Available: {available}"
        print(f"Loading skill: {name}")
        return f"# Skill: {skill.manifest.name}\n\n{skill.body}"

    def format_for_system_prompt(self) -> str:
        if not self.skills:
            return ""
        lines = ["## Available Skills", ""]
        for name, skill in self.skills.items():
            lines.append(f"- **{name}**: {skill.manifest.description}")
        lines += [
            "",
            "Use `list_skills` to see all skills, `preview_skill` for a short summary, "
            "or `get_skill` to load full instructions before attempting a skill-based task.",
        ]
        return '\n'.join(lines)
