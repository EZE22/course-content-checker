"""Build the rules named in the settings and run them over the source files."""

from content_checker.rules import RULE_REGISTRY, MissingSectionRule

UNREADABLE = "unreadable"


def build_rules(settings):
    """Return rule instances in the order of settings.rules.

    MissingSectionRule receives settings.required_sections.
    """
    rules = []
    for name in settings.rules:
        rule_class = RULE_REGISTRY[name]
        if rule_class is MissingSectionRule:
            rules.append(rule_class(settings.required_sections))
        else:
            rules.append(rule_class())
    return rules


def run_rules(source_files, rules):
    """Run every rule on every readable file and return (path, Finding) pairs.

    Unreadable files are skipped. The result is sorted by path, then line, then rule.
    """
    results = []
    for source in source_files:
        if source.kind == UNREADABLE:
            continue
        for rule in rules:
            for finding in rule.check(source.text, source.kind):
                results.append((source.path, finding))
    return sorted(results, key=lambda pair: (pair[0], pair[1].line, pair[1].rule))
