from __future__ import annotations

from .core import ImpactCompiler as _CoreImpactCompiler


_GLOB_META = frozenset("*?[")


class ImpactCompiler(_CoreImpactCompiler):
    """Fail-safe ImpactCompiler with bounded package-root inference.

    Legacy root inference treated a single narrow subtree such as
    ``federation/orchestration/**`` as evidence that the same subsystem owned
    every sibling path beneath ``federation/``. That can suppress ProofOS's
    unmapped-production fallback for newly introduced modules.

    A package-root owner is now inferred only when exactly one subsystem has
    concrete ownership evidence spanning at least two distinct nested
    first-level directories beneath that root. Root-level files never establish
    package-wide ownership. Broad wildcard ownership does not need inference
    because it already matches explicitly. Ambiguous or weak evidence returns
    no inferred owner, causing the existing full-suite fallback to engage for
    production paths.
    """

    @staticmethod
    def _owned_root_children(root: str, patterns: tuple[str, ...]) -> set[str]:
        prefix = root + "/"
        children: set[str] = set()
        for raw_pattern in patterns:
            pattern = str(raw_pattern).replace("\\", "/")
            if not pattern.startswith(prefix):
                continue
            remainder = pattern[len(prefix):]
            if "/" not in remainder:
                continue
            child = remainder.split("/", 1)[0]
            if not child or any(meta in child for meta in _GLOB_META):
                continue
            children.add(child)
        return children

    def _unique_package_root_owner(self, path: str) -> str:
        if "/" not in path:
            return ""
        root = path.split("/", 1)[0]
        candidates = {
            rule.subsystem
            for rule in self.policy.subsystem_rules
            if len(self._owned_root_children(root, rule.patterns)) >= 2
        }
        return next(iter(candidates)) if len(candidates) == 1 else ""


__all__ = ["ImpactCompiler"]
