"""
CLI Testing: `spotsnagger ...`
"""

import logging

from spotsnagger.cli import spotsnagger_command_line
from tests.conftest import SpotSnaggerRunner, cli_status_checker, vcr_cassette

logger = logging.getLogger(__name__)


@vcr_cassette
def test_main_succeeds(cli_runner: SpotSnaggerRunner) -> None:
    """
    It exits with a status code of zero.
    """
    result = cli_runner.invoke(spotsnagger_command_line)
    assert "Welcome to spotsnagger, the campsite finder" in result.output
    cli_status_checker(result=result)
