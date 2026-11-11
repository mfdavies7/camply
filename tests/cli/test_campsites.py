"""
CLI Testing - Campsites: `spotsnagger campsites...`
"""

import logging

from tests.conftest import SpotSnaggerRunner, cli_status_checker, vcr_cassette

logger = logging.getLogger(__name__)


@vcr_cassette
def test_multiple_search_windows_goingtocamp(cli_runner: SpotSnaggerRunner) -> None:
    """
    Multiple Search Windows: GoingToCamp
    """
    test_command = """
    spotsnagger \
      campsites \
      --provider goingtocamp \
      --rec-area 1 \
      --start-date 2023-09-01 \
      --end-date 2023-09-02 \
      --start-date 2023-10-01 \
      --end-date 2023-10-02 \
      --equipment-id -32768 \
      --campground -2147483643
    """
    result = cli_runner.run_spotsnagger_command(command=test_command)
    assert "2 different months selected for search" in result.output
    assert "2 booking nights selected for search" in result.output
    assert "Long Point Region" in result.output
    assert "Waterford North Conservation Area" in result.output
    assert "Reservable Campsites Matching Search Preferences" in result.output
    cli_status_checker(result=result)
