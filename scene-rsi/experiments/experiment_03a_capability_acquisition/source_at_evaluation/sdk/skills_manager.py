import io, json
import tarfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple
import logging
import random


def build_skills_archive(skill_items: list) -> bytes:
    """将选中的 (name, path) 列表打包为 tar.gz，结构为 skills/{skill_name}/...

    解压时配合 --strip-components=1 后变为 {skill_name}/SKILL.md，
    最终在容器中为 /app/.claude/skills/{skill_name}/SKILL.md
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tar:
        for name, skill_path in skill_items:
            arcname = f"skills/{name}"
            tar.add(str(skill_path), arcname=arcname)
    return buf.getvalue()


def load_swe_useful_skills(jsonl_path: Optional[str]) -> Dict[str, Path]:
    """从 swe_skills.jsonl 加载 swe_useful=true 的 skill，按 skill_name 去重（随机保留一个）。

    Returns:
        dict: {skill_name: skill_path}，已按 name 去重
    """
    if not jsonl_path:
        return {}

    by_name: Dict[str, list] = {}
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("swe_useful"):
                skill_path = Path(record["path"])
                if skill_path.is_dir():
                    name = skill_path.name
                    by_name.setdefault(name, []).append(skill_path)
    # 每个 name 随机保留一个，避免 tar 内路径冲突
    deduped = {name: random.choice(paths) for name, paths in by_name.items()}
    return deduped


class SkillManager:
    """Encapsulates skill selection and archive building."""

    _DEFAULT_STRATEGY = "none"

    def __init__(self, skill_pool: Dict[str, Path] = None, num_skills: int = 10,
                 strategy: str = _DEFAULT_STRATEGY):
        self.skill_pool: List[Tuple[str, Path]] = list((skill_pool or {}).items())
        self.num_skills = max(0, num_skills)
        self.strategy = (strategy or self._DEFAULT_STRATEGY).strip().lower()

    @classmethod
    def available_strategies(cls) -> Tuple[str, ...]:
        return ("none", "random", "sequential")

    def build_archive(self) -> Optional[bytes]:
        selected_skills = self.select_skills()
        logging.info(f"Selected {len(selected_skills)} skills using strategy '{self.strategy}'")
        if not selected_skills:
            return None
        return build_skills_archive(selected_skills)

    def select_skills(self) -> List[Tuple[str, Path]]:
        selector = self._get_selector()
        return selector()

    def _get_selector(self) -> Callable[[], List[Tuple[str, Path]]]:
        selectors = {
            "none": self._select_none,
            "random": self._select_random,
            "sequential": self._select_sequential,
        }
        if self.strategy not in selectors:
            supported = ", ".join(self.available_strategies())
            raise ValueError(f"Unknown skill strategy '{self.strategy}'. Supported strategies: {supported}")
        return selectors[self.strategy]

    def _selection_size(self) -> int:
        return min(self.num_skills, len(self.skill_pool))

    def _select_none(self) -> List[Tuple[str, Path]]:
        return []

    def _select_random(self) -> List[Tuple[str, Path]]:
        k = self._selection_size()
        return random.sample(self.skill_pool, k) if k > 0 else []

    def _select_sequential(self) -> List[Tuple[str, Path]]:
        return self.skill_pool[:self._selection_size()]
