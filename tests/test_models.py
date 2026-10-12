import pytest
from pydantic import ValidationError

from rapid_ship.models import (
    CheckResult,
    EnvironmentSpec,
    EvidenceBinding,
    ProjectConfig,
    Resources,
    ReviewDecision,
    ReviewFinding,
    TaskEvidence,
    TaskSpec,
    digest,
    paths_overlap,
    validate_task_graph,
)


def task(**overrides: object) -> TaskSpec:
    values: dict[str, object] = {
        "id": "a",
        "title": "Implement a feature",
        "description": "Create the requested behavior",
        "owned_paths": ["src/feature.py"],
        "acceptance": ["Feature behaves correctly"],
        "environment": "isolated",
        "base_sha": "abc123",
    }
    values.update(overrides)
    return TaskSpec.model_validate(values)


def binding(**overrides: object) -> EvidenceBinding:
    values: dict[str, object] = {
        "task_id": "a",
        "attempt_id": "attempt-1",
        "head_sha": "abc123",
        "base_sha": "def456",
        "policy_digest": "policy-1",
        "recipe_digest": "recipe-1",
        "environment_digest": "environment-1",
        "controller_version": "0.1.0",
    }
    values.update(overrides)
    return EvidenceBinding.model_validate(values)


@pytest.mark.parametrize(
    "path",
    [
        "",
        " ",
        "/etc/passwd",
        "../x",
        "src/../../x",
        "src/../x",
        "x\x00y",
        "C:/secret",
        "C:\\secret",
        "src\\..\\secret",
        "./x",
        "src//x",
        ".",
        "src/\nx",
    ],
)
def test_task_rejects_unsafe_owned_paths(path: str) -> None:
    with pytest.raises(ValidationError):
        task(owned_paths=[path])


@pytest.mark.parametrize("identifier", ["", ".", "..", "a/b", "a\\b", "a b", "x\n", "x:1"])
def test_task_ids_cannot_escape_namespace(identifier: str) -> None:
    with pytest.raises(ValidationError):
        task(id=identifier)


@pytest.mark.parametrize("acceptance", [[], [""], ["  "]])
def test_acceptance_requires_meaningful_criteria(acceptance: list[str]) -> None:
    with pytest.raises(ValidationError):
        task(acceptance=acceptance)


@pytest.mark.parametrize(
    "values",
    [
        {"owned_paths": []},
        {"title": ""},
        {"description": " "},
        {"timeout_seconds": 0},
        {"timeout_seconds": "12"},
        {"base_sha": "a b"},
        {"base_sha": "x\n"},
    ],
)
def test_invalid_task_input_fails_early(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        task(**values)


@pytest.mark.parametrize(
    "values",
    [
        {"memory_mb": 0},
        {"memory_mb": -1},
        {"cpu": 0.0},
        {"cpu": -1.0},
        {"cpu": float("nan")},
        {"cpu": float("inf")},
        {"memory_mb": "2048"},
        {"memory_mb": True},
        {"cpu": "1.0"},
    ],
)
def test_invalid_resources_are_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Resources.model_validate(values)


def test_configuration_cannot_grant_unrecognized_authority() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        ProjectConfig.model_validate(
            {"name": "demo", "design_path": "docs/design.md", "merge_authorized": True}
        )


def test_contracts_reject_unknown_fields_and_coercion() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        task(approved=True)
    with pytest.raises(ValidationError):
        EnvironmentSpec.model_validate(
            {"name": "native", "workspace": "clone", "execution": "native", "verified": "true"}
        )


def test_contracts_are_frozen_and_defaults_are_not_shared() -> None:
    first, second = task(), task(id="b")
    with pytest.raises(ValidationError, match="frozen_instance"):
        first.title = "Changed"
    first.depends_on.append("c")
    assert second.depends_on == []
    one = ProjectConfig(name="one", design_path="design.md")
    two = ProjectConfig(name="two", design_path="design.md")
    one.checks["test"] = ["pytest"]
    assert two.checks == {}


def test_native_network_requirements_are_preserved_for_capability_inspection() -> None:
    environment = EnvironmentSpec(name="native", workspace="clone", execution="native")
    assert environment.private_network is True
    assert environment.allow_native is False
    assert environment.verified is False


@pytest.mark.parametrize(
    "values",
    [
        {"max_parallel": 0},
        {"memory_budget_mb": 0},
        {"cpu_budget": float("inf")},
        {"cpu_budget": 0.0},
        {"max_repair_rounds": -1},
        {"schema_version": 2},
        {"schema_version": True},
        {"design_path": "../design.md"},
        {"checks": {"test": []}},
        {"checks": {"test": [""]}},
    ],
)
def test_invalid_project_configuration_is_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"name": "demo", "design_path": "design.md", **values})


def test_duplicate_environment_names_are_rejected() -> None:
    environment = EnvironmentSpec(name="local", workspace="clone", execution="native")
    with pytest.raises(ValidationError, match="duplicate"):
        ProjectConfig(name="demo", design_path="design.md", environments=[environment, environment])


def test_cycle_is_rejected() -> None:
    with pytest.raises(ValueError, match="cycle"):
        validate_task_graph([task(id="a", depends_on=["b"]), task(id="b", depends_on=["a"])])


def test_self_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="cycle"):
        validate_task_graph([task(depends_on=["a"])])


def test_missing_dependency_is_rejected() -> None:
    with pytest.raises(ValueError, match="missing"):
        validate_task_graph([task(depends_on=["absent"])])


def test_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_task_graph([task(), task()])


def test_dependency_graph_accepts_unordered_diamond() -> None:
    validate_task_graph(
        [
            task(id="d", depends_on=["b", "c"]),
            task(id="c", depends_on=["a"]),
            task(id="b", depends_on=["a"]),
            task(id="a"),
        ]
    )


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (["src"], ["src/feature.py"], True),
        (["src/a.py"], ["src/a.py"], True),
        (["src/a.py"], ["src/b.py"], False),
        (["src"], ["src-other"], False),
        (["src/*.py"], ["src/sub/file.txt"], True),
        (["**/*.py"], ["docs/x.md"], True),
        (["src/test?.py"], ["docs/x.md"], False),
        (["src/[ab].py"], ["src/c.py"], True),
        (["Src"], ["src/a.py"], False),
        ([], ["src"], False),
    ],
)
def test_path_ownership_overlap_is_conservative_and_case_sensitive(
    left: list[str],
    right: list[str],
    expected: bool,
) -> None:
    assert paths_overlap(left, right) is expected
    assert paths_overlap(right, left) is expected


def test_overlap_helper_rejects_unsafe_paths() -> None:
    with pytest.raises(ValueError):
        paths_overlap(["../escape"], ["src"])


def test_digest_is_canonical_and_binds_nested_content() -> None:
    assert digest({"b": 2, "a": 1}) == (
        "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    )
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest(task()) == digest(task().model_dump(mode="json"))
    assert digest({"nested": {"a": 1, "b": 2}}) == digest({"nested": {"b": 2, "a": 1}})
    assert digest({"checks": ["a", "b"]}) != digest({"checks": ["b", "a"]})
    assert digest(task()) != digest(task(base_sha="new-head"))


def test_digest_rejects_non_json_nan() -> None:
    with pytest.raises(ValueError):
        digest({"bad": float("nan")})


@pytest.mark.parametrize(
    "field",
    [
        "task_id",
        "attempt_id",
        "head_sha",
        "base_sha",
        "policy_digest",
        "recipe_digest",
        "environment_digest",
        "controller_version",
    ],
)
@pytest.mark.parametrize("value", ["", "a b", "a\n", "a\x00b"])
def test_evidence_binding_rejects_ambiguous_tokens(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        binding(**{field: value})


def test_evidence_does_not_launder_a_review_bound_to_another_head() -> None:
    review = ReviewDecision(
        binding=binding(head_sha="other"),
        verdict="approve",
        findings=[],
        reviewer_runner="claude",
        independent=True,
        summary="Looks correct",
    )
    with pytest.raises(ValidationError, match="binding"):
        TaskEvidence(binding=binding(), review=review)


@pytest.mark.parametrize("runner", ["codex", "claude", "agy"])
def test_review_decision_names_any_supported_reviewer_runner(runner: str) -> None:
    review = ReviewDecision(
        binding=binding(),
        verdict="approve",
        findings=[],
        reviewer_runner=runner,
        independent=True,
        summary="Looks correct",
    )
    assert review.reviewer_runner == runner


def test_evidence_and_review_preserve_gate_inputs() -> None:
    review = ReviewDecision(
        binding=binding(),
        verdict="approve",
        findings=[],
        reviewer_runner="claude",
        independent=False,
        summary="Simulated",
    )
    evidence = TaskEvidence(binding=binding(), review=review)
    assert evidence.live is False
    assert evidence.review is not None and evidence.review.independent is False
    with pytest.raises(ValidationError):
        ReviewFinding(severity="cosmetic", message="Typo")
    with pytest.raises(ValidationError):
        ReviewFinding(severity="minor", message="Typo", path="../x", line=0)


@pytest.mark.parametrize(
    "values",
    [
        {"argv": []},
        {"argv": [""]},
        {"argv": ["pytest\x00"]},
        {"duration_seconds": -1.0},
        {"duration_seconds": float("inf")},
    ],
)
def test_check_results_reject_malformed_execution_records(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CheckResult.model_validate(
            {
                "name": "unit",
                "argv": ["pytest"],
                "exit_code": 0,
                "duration_seconds": 1.0,
                "stdout": "",
                "stderr": "",
                **values,
            }
        )


def test_artifact_paths_cannot_escape_evidence_directory() -> None:
    with pytest.raises(ValidationError):
        TaskEvidence(binding=binding(), artifact_paths=["/secret"])
