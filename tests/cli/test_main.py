"""
CLI Testing: `camply ...`
"""

import logging

from camply.cli import camply_command_line
from tests.conftest import CamplyRunner, cli_status_checker, vcr_cassette

logger = logging.getLogger(__name__)


@vcr_cassette
def test_main_succeeds(cli_runner: CamplyRunner) -> None:
    """
    It exits with a status code of zero.
    """
    result = cli_runner.invoke(camply_command_line)
    assert "Welcome to camply, the campsite finder" in result.output
    cli_status_checker(result=result)
