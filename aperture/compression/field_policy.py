"""Field-level keep/drop policy.

Replaces the static `_OBVIOUS_API_FIELDS` denial list with a layered, context-
aware decision per field. Resolution is cheapest-first; each tier can promote
a field to KEEP, but only the static denial list and a missing decision can
DROP. That asymmetry is intentional — when in doubt, we keep the field.

Tiers:
    1. Required signal (explicit dot-path or substring) → KEEP
    2. User ask mentions the field name (regex word match, case-insensitive,
       handles snake_case and camelCase) → KEEP
    3. Optional model-assisted promotion (`classifier_keeps`) → KEEP
    4. Static denial list (URL / id / image bookkeeping) → DROP
    5. Default → KEEP

Every decision carries a `reason` so the dashboard can render the trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


# Genuinely low-signal fields. Same set the engine used to inline-check; now
# the policy owns it so we have one source of truth.
_OBVIOUS_API_FIELDS: frozenset[str] = frozenset({
    # GitHub bookkeeping URLs
    "node_id", "gravatar_id", "avatar_url",
    "followers_url", "following_url", "gists_url", "starred_url",
    "subscriptions_url", "organizations_url", "repos_url", "events_url",
    "received_events_url", "labels_url", "comments_url", "repository_url",
    "commits_url", "statuses_url", "pull_request_url", "archive_url",
    "assignees_url", "blobs_url", "branches_url", "clone_url",
    "collaborators_url", "compare_url", "contents_url", "contributors_url",
    "deployments_url", "downloads_url", "forks_url", "git_commits_url",
    "git_refs_url", "git_tags_url", "hooks_url", "issue_comment_url",
    "issue_events_url", "issues_url", "keys_url", "merges_url",
    "milestones_url", "notifications_url", "pulls_url", "releases_url",
    "stargazers_url", "tags_url", "teams_url", "trees_url", "ssh_url",
    "svn_url", "mirror_url", "languages_url", "subscribers_url",
    "subscription_url", "raw_url", "preview_url", "upload_url", "git_url",
    # Generic API bookkeeping URL
    "url",
    # Slack / Gmail bookkeeping
    "image_24", "image_32", "image_48", "image_72", "image_192", "image_512",
    "avatar_hash", "size_estimate", "sizeEstimate", "internalDate",
    "internal_date", "history_id", "historyId", "client_msg_id",
    "permalink_public",
})

DecisionTag = Literal[
    "explicit",          # required_signals contained this field exactly
    "explicit_descendant",  # a required_signals path passes through this field
    "ask",               # the user's ask mentions this field name
    "model",             # the optional classifier promoted it
    "denial_list",       # field is in the static drop set
    "default",           # fell off the end → keep
]


@dataclass(frozen=True)
class FieldDecision:
    name: str
    full_path: str
    decision: Literal["keep", "drop"]
    reason: DecisionTag


_WORD_BOUNDARY = re.compile(r"[\s,.;:!?\"'`/\\()\[\]{}<>]+")
_CAMEL_SPLIT = re.compile(r"(?<!^)(?=[A-Z])")

# Distinctive leaf terms — `avatar_url` → also match bare "avatar".
# Bare "url"/"id"/"name" alone would over-match in normal speech, so they're
# blocked.
_LEAF_BLOCKLIST: frozenset[str] = frozenset({
    "url", "id", "uri", "key", "name", "type", "size", "data",
    "node", "href", "self", "ref", "value",
})


def _split_parts(name: str) -> list[str]:
    """Split `historyId` / `avatar_url` / `OAuth-Token` into lowercased parts."""
    if "_" in name:
        return [p.lower() for p in name.split("_") if p]
    if any(c.isupper() for c in name):
        return [p.lower() for p in _CAMEL_SPLIT.split(name) if p]
    return [name.lower()]


def _alternate_forms(name: str) -> set[str]:
    """Generate substring forms an ask might use to reference a field.

    `assignee_login`  → {"assignee_login", "assignee login", "assignee.login",
                         "assignee", "login"}
    `avatar_url`      → {"avatar_url", "avatar url", "avatar.url", "avatar"}
                        (not "url" — too generic alone)
    `historyId`       → {"historyid", "history id", "history_id", "history"}
    """
    if not name:
        return set()
    lower = name.lower()
    forms: set[str] = {lower}

    if "_" in lower:
        forms.add(lower.replace("_", " "))
        forms.add(lower.replace("_", "."))
    if any(c.isupper() for c in name) and "_" not in name:
        snake = "_".join(part.lower() for part in _CAMEL_SPLIT.split(name) if part)
        if snake:
            forms.add(snake)
            forms.add(snake.replace("_", " "))

    # Distinctive parts — but skip generic leaves alone.
    for part in _split_parts(name):
        if part not in _LEAF_BLOCKLIST and len(part) >= 4:
            forms.add(part)

    return {f for f in forms if len(f) >= 3}


def _ask_mentions(ask: str | None, field_name: str) -> bool:
    if not ask:
        return False
    haystack = " " + _WORD_BOUNDARY.sub(" ", ask.lower()) + " "
    for form in _alternate_forms(field_name):
        if f" {form} " in haystack:
            return True
    return False


@dataclass
class FieldPolicy:
    """Per-tool keep/drop decisions with telemetry.

    Attributes:
        required_signals: Substrings or dot-paths the agent's downstream
            answer must contain. Exact match or path-prefix match wins.
        ask: Optional user ask text. Word-bounded mentions promote a field.
        classifier_keeps: Optional set of names the model classifier added
            for this run. Asymmetric — never demotes anything.
        decisions: All recorded decisions, in the order the engine asked
            for them. Useful for the dashboard explain view.
    """

    required_signals: set[str] = field(default_factory=set)
    ask: str | None = None
    classifier_keeps: set[str] = field(default_factory=set)
    decisions: list[FieldDecision] = field(default_factory=list)

    def decide(self, field_name: str, parent_path: str = "") -> FieldDecision:
        full_path = f"{parent_path}.{field_name}" if parent_path else field_name

        # Tier 1 — explicit (exact or path passes through)
        if field_name in self.required_signals or full_path in self.required_signals:
            d = FieldDecision(field_name, full_path, "keep", "explicit")
            self._record(d)
            return d
        for sig in self.required_signals:
            if sig.startswith(f"{full_path}.") or sig.startswith(f"{field_name}."):
                d = FieldDecision(field_name, full_path, "keep", "explicit_descendant")
                self._record(d)
                return d

        # Tier 2 — ask mentions
        if _ask_mentions(self.ask, field_name):
            d = FieldDecision(field_name, full_path, "keep", "ask")
            self._record(d)
            return d

        # Tier 3 — classifier promotion (only adds keeps)
        if field_name in self.classifier_keeps or full_path in self.classifier_keeps:
            d = FieldDecision(field_name, full_path, "keep", "model")
            self._record(d)
            return d

        # Tier 4 — static denial list
        if field_name in _OBVIOUS_API_FIELDS:
            d = FieldDecision(field_name, full_path, "drop", "denial_list")
            self._record(d)
            return d

        # Tier 5 — default
        d = FieldDecision(field_name, full_path, "keep", "default")
        self._record(d)
        return d

    def is_dropped(self, field_name: str, parent_path: str = "") -> bool:
        return self.decide(field_name, parent_path).decision == "drop"

    def _record(self, d: FieldDecision) -> None:
        # Cap to avoid memory blowup on huge schemas — first ~500 are plenty
        # for the dashboard explain view.
        if len(self.decisions) < 500:
            self.decisions.append(d)

    # ---- Telemetry helpers -------------------------------------------------

    def reason_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.decisions:
            out[d.reason] = out.get(d.reason, 0) + 1
        return out

    def promotions(self) -> list[FieldDecision]:
        """Decisions where a tier OTHER than the static list saved the field."""
        return [d for d in self.decisions if d.reason in ("explicit", "explicit_descendant", "ask", "model")]

    def drops(self) -> list[FieldDecision]:
        return [d for d in self.decisions if d.decision == "drop"]


def make_policy(
    required_signals: list[str] | set[str] | None = None,
    ask: str | None = None,
    classifier_keeps: set[str] | None = None,
) -> FieldPolicy:
    """Convenience constructor."""
    return FieldPolicy(
        required_signals=set(required_signals or []),
        ask=ask,
        classifier_keeps=set(classifier_keeps or []),
    )
