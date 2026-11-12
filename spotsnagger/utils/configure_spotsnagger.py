"""
SpotSnagger Configuration Script
"""

import logging
import sys
from collections import OrderedDict
from os.path import isfile
from time import sleep

import rich
from rich.prompt import Confirm, Prompt

from spotsnagger.config import FileConfig

logger = logging.getLogger(__name__)


def double_check(message: str) -> bool:
    """
    Double check if a step should be taken within CLI

    Parameters
    ----------
    message: str
        Message to log in interactive shell
    """
    first_confirmation = Confirm.ask(prompt=message)
    if first_confirmation is True:
        second_confirmation = Confirm.ask(prompt="Are you sure?")
        return second_confirmation
    else:
        logging.info("Okay, skipping")
        return False


def check_dot_spotsnagger_file() -> bool:
    """
    Check to see if the `.spotsnagger` file already exists

    Return the file existence status

    Returns
    -------
    bool
    """
    if isfile(FileConfig.DOT_SPOTSNAGGER_FILE) is True:
        logger.info(
            "Skipping configuration. `.spotsnagger` file already exists: "
            f"{FileConfig.DOT_SPOTSNAGGER_FILE}"
        )
        return True
    else:
        return False


def generate_configuration() -> OrderedDict:
    """
    Generate the SpotSnagger Configuration Config

    Returns
    -------
    OrderedDict
        Dict of configuration values
    """
    config_dict = FileConfig.DOT_SPOTSNAGGER_FIELDS.copy()
    for field, field_dict in config_dict.items():
        default_value = field_dict["default"]
        field_note = field_dict["notes"]
        if field_note is not None:
            rich.print(
                f"[bold blue]{field}:[/bold blue] "
                f"[bold green]{field_note}[/bold green]"
            )
        message = f"Enter value for [bold blue]{field}[/bold blue]"
        if default_value != "":
            message += f" (default: `[bold purple]{default_value}[/bold purple]`)"
        logged_input = Prompt.ask(prompt=message)
        config_value = logged_input if logged_input != "" else default_value
        config_dict[field] = config_value
    return config_dict


def write_config_to_file(config_dict: OrderedDict) -> None:
    """
    Write the Configuration Object to a file

    Parameters
    ----------
    config_dict : OrderedDict
        Configuration Object
    """
    string_list = [
        "# SPOTSNAGGER CONFIGURATION FILE. ",
        "# SEE https://github.com/mfdavies7/camply/blob/main/docs/examples/example.spotsnagger",
        "",
    ]
    for config_key, config_value in config_dict.items():
        string_list.append(f'{config_key}="{config_value}"')
    string_list.append("")
    with open(FileConfig.DOT_SPOTSNAGGER_FILE, "w") as file_object:
        file_object.write("\n".join(string_list))
        file_object.seek(0)


def generate_dot_spotsnagger_file():
    """
    Perform the larger Dot SpotSnagger File Generation
    """
    logger.info("Running spotsnagger configuration.")
    logger.info(
        "This process generates a configuration file "
        "(https://github.com/mfdavies7/camply/blob/main/docs/examples/example.spotsnagger)"
    )
    logger.info("Do not include quotes around values")
    logger.info(
        "To skip a configuration field or keep it as default, just press <Enter>."
    )
    sleep(1.5)
    if isfile(FileConfig.DOT_SPOTSNAGGER_FILE):
        logger.warning(
            f".spotsnagger file already exists on this machine: {FileConfig.DOT_SPOTSNAGGER_FILE}"
        )
        overwrite = double_check(
            "Would you like to overwrite your "
            "[bold yellow].spotsnagger[/bold yellow] "
            "configuration file?"
        )
        if overwrite is False:
            sys.exit(0)
    config = generate_configuration()
    if double_check(
        "Are you ready to publish this to a file at "
        f"[bold yellow]{FileConfig.DOT_SPOTSNAGGER_FILE}[/bold yellow]"
    ):
        write_config_to_file(config_dict=config)
        logger.info(
            f"`.spotsnagger` file written to machine: {FileConfig.DOT_SPOTSNAGGER_FILE}"
        )
