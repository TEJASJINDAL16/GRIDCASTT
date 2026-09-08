"""The public documents must not contradict the specification.

A public repository describing an architecture we rejected is worse than no
README: a reader who believes it will ask the wrong questions about the code,
and the mismatch is not visible from either document alone.

The committed README did all three of these until stage 1 rewrote it — it
described the phase 2 base-plus-regional-correction architecture as though it
were shipping, said the model retrains nightly where PLANNING 6 forbids any
calendar schedule, and defined the baseline as "last week" where 5c requires
the most recent MEASURED matching hour.
"""

from __future__ import annotations

import pathlib
import re

import pytest

README = pathlib.Path("README.md")


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text()


def test_readme_does_not_claim_scheduled_retraining(readme):
    """PLANNING 6: never retrain on a calendar schedule."""
    claims = re.findall(
        r"retrain\w*\s+(?:it\s+|the\s+model\s+)?(?:nightly|daily|weekly|monthly)"
        r"|(?:nightly|daily|weekly|monthly)\s+retrain\w*",
        readme, re.I)
    # Naming a cadence in order to reject it is the opposite of claiming it.
    offenders = [c for c in claims if "not" not in readme[
        max(0, readme.lower().find(c.lower()) - 60):
        readme.lower().find(c.lower())].lower()]
    assert not offenders, f"README claims scheduled retraining: {offenders}"


def test_readme_states_retraining_is_trigger_based(readme):
    assert re.search(r"not on a schedule|trigger[- ]based|only when a trigger",
                     readme, re.I), (
        "README must say retraining is trigger-based; it is the single most "
        "load-bearing claim about how the system behaves after deployment"
    )


def test_readme_describes_the_phase_1_architecture(readme):
    """The hybrid that ships, not the phase 2 experiment."""
    assert "Ridge" in readme and "LightGBM" in readme
    assert re.search(r"residual", readme, re.I)


def test_readme_does_not_present_phase_2_as_shipping(readme):
    """'Regional correction' is a phase 2 candidate to be tested, not assumed."""
    for line in readme.splitlines():
        if re.search(r"regional correction", line, re.I):
            assert re.search(r"phase 2|not yet|candidate|experiment", line, re.I), (
                f"README presents the phase 2 correction layer as shipping: {line!r}")


def test_readme_baseline_matches_the_5c_definition(readme):
    """A baseline defined as 'last week' is not under the same information
    constraint as the model — see PLANNING 5c."""
    assert re.search(r"most recent measured", readme, re.I), (
        "README must give the measured-row baseline definition"
    )
    assert re.search(r"not simply .last week.", readme, re.I), (
        "README should say explicitly that it is not 'last week', because that "
        "is the definition a reader will otherwise assume"
    )


def test_readme_publishes_no_performance_number(readme):
    """INV-5: no performance claim without its baseline stated alongside. Until
    stage 2 produces a baseline there is nothing legitimate to publish."""
    numbers = re.findall(r"\b\d+(?:\.\d+)?\s*%\s*(?:MAPE|error|accuracy|better)",
                         readme, re.I)
    assert not numbers, f"README publishes a performance figure: {numbers}"


def test_readme_carries_the_electricity_maps_attribution(readme):
    """The academic licence requires attribution in published work (11)."""
    assert "Electricity Maps" in readme


def test_readme_points_at_the_build_stages(readme):
    assert "BUILD_STAGES.md" in readme and "PLANNING.md" in readme
