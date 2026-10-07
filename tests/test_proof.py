import pathlib
import evaluate, mutants

README = (pathlib.Path(__file__).parent.parent / "README.md").read_text()


def test_every_case_gets_its_labeled_verdict_and_line():
    rows = evaluate.rows()
    assert len(rows) >= 10
    assert all(ok for *_, ok in rows)


def test_readme_results_table_matches_evaluate_output():
    assert evaluate.results() in README, "README results table drifted from evaluate.py"


def test_readme_lists_every_mutant_and_the_count():
    for name, *_ in mutants.MUTANTS:
        assert f"RED  {name}" in README, f"README misses mutant: {name}"
    assert f"mutants killed {len(mutants.MUTANTS)}/{len(mutants.MUTANTS)}" in README


def test_every_mutant_pattern_exists_exactly_once():
    root = pathlib.Path(mutants.ROOT)
    for name, f, old, new, test in mutants.MUTANTS:
        assert (root / f).read_text().count(old) == 1, name
        assert (root / test).exists(), name


def test_three_required_defenses_have_a_mutant():
    names = " ".join(m[0] for m in mutants.MUTANTS)
    for word in ("hmac", "window", "empty"):
        assert word in names.lower(), word
