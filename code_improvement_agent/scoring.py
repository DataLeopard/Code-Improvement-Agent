"""Scoring and tagging system for repositories."""

from dataclasses import dataclass


@dataclass
class RepoScore:
    """Aggregate scoring for a repository."""
    quality: float = 0.0      # Code quality (clarity + functionality)
    structure: float = 0.0    # Organization and modularity
    usefulness: float = 0.0   # Completeness, usability, value
    security: float = 0.0     # Safety and best practices
    overall: float = 0.0      # Weighted composite
    tag: str = ""             # lab, biz, ops, util
    recommendation: str = ""  # archive, maintain, promote


def compute_repo_score(analyzer_results: list) -> RepoScore:
    """Compute aggregate scores from individual analyzer results."""
    scores_by_category = {}
    for r in analyzer_results:
        scores_by_category[r.analyzer_name.lower()] = r.score

    score = RepoScore()
    score.quality = round(
        (scores_by_category.get("clarity", 10) +
         scores_by_category.get("functionality", 10)) / 2, 1
    )
    score.structure = round(
        (scores_by_category.get("structure", 10) +
         scores_by_category.get("reusability", 10)) / 2, 1
    )
    score.security = round(scores_by_category.get("security", 10), 1)
    score.usefulness = round(
        (scores_by_category.get("automation", 10) + score.quality) / 2, 1
    )

    # Weighted overall: quality 30%, structure 25%, security 25%, usefulness 20%
    score.overall = round(
        score.quality * 0.30 +
        score.structure * 0.25 +
        score.security * 0.25 +
        score.usefulness * 0.20,
        1
    )

    return score


def classify_tag(file_contents: dict[str, str], repo_path: str) -> str:
    """Classify repo into a category tag based on content signals."""
    all_content = "\n".join(file_contents.values()).lower()
    repo_name = repo_path.lower()

    # Scoring signals for each tag
    signals = {
        "biz": ["customer", "invoice", "payment", "order", "checkout", "cart",
                "user", "login", "auth", "dashboard", "analytics", "revenue"],
        "ops": ["deploy", "ci", "cd", "docker", "kubernetes", "terraform",
                "ansible", "pipeline", "monitoring", "alerting", "cron", "schedule"],
        "lab": ["experiment", "test", "prototype", "demo", "example", "sandbox",
                "scratch", "try", "poc", "proof"],
        "util": ["util", "helper", "tool", "script", "automation", "cli",
                "agent", "bot", "scraper", "converter", "parser"],
    }

    tag_scores = {}
    for tag, keywords in signals.items():
        tag_scores[tag] = sum(1 for kw in keywords
                              if kw in all_content or kw in repo_name)

    best_tag = max(tag_scores, key=tag_scores.get)
    return best_tag if tag_scores[best_tag] > 0 else "util"


def recommend_action(score: RepoScore, file_count: int) -> str:
    """Suggest whether repo should be archived, maintained, or promoted."""
    if score.overall >= 7.5 and file_count > 3:
        return "promote"  # High quality, worth investing in
    elif score.overall >= 4.5:
        return "maintain"  # Decent, keep improving
    elif score.overall >= 2.5 or file_count <= 2:
        return "maintain"  # Small or rough but has potential
    else:
        return "archive"  # Low quality, consider archiving
