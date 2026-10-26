from content_checker.rules import MissingSectionRule

REQUIRED = {"article": ["Comprehension Check"], "lab": []}


def check(text):
    return MissingSectionRule(REQUIRED).check(text, "article")


def test_heading_inside_backtick_fence_does_not_count():
    text = "# Title\n\n```\n## Comprehension Check\n```\n"
    findings = check(text)
    assert len(findings) == 1
    assert "Comprehension Check" in findings[0].message


def test_heading_inside_tilde_fence_does_not_count():
    text = "# Title\n\n~~~\n## Comprehension Check\n~~~\n"
    findings = check(text)
    assert len(findings) == 1
    assert "Comprehension Check" in findings[0].message


def test_real_heading_outside_fence_counts_with_fake_inside():
    text = (
        "# Title\n\n## Comprehension Check\n\n"
        "```\n## Comprehension Check\n```\n"
    )
    assert check(text) == []


def test_heading_after_closed_fence_counts():
    text = "# Title\n\n```\ncode\n```\n\n## Comprehension Check\n"
    assert check(text) == []


def test_seven_hashes_is_not_a_heading():
    text = "# Title\n\n####### Comprehension Check\n"
    assert len(check(text)) == 1


def test_no_space_after_hashes_is_not_a_heading():
    text = "# Title\n\n##Comprehension Check\n"
    assert len(check(text)) == 1


def test_python_comment_inside_fence_does_not_count():
    text = "# Title\n\n```python\n# Comprehension Check\nprint('hi')\n```\n"
    assert len(check(text)) == 1
