"""
SpotSnagger Command Line Interface
"""

import json
import logging
import shlex
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from time import sleep
from typing import (
    Any,
    Container,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    Union,
)

import click
from pydantic import ValidationError
from rich import traceback
from rich_click import RichCommand, RichGroup, rich_click

from spotsnagger import __application__, __version__, saved
from spotsnagger.config import SearchConfig, logging_config
from spotsnagger.config.logging_config import set_up_logging
from spotsnagger.containers import SearchWindow
from spotsnagger.containers.examples import example_campsite
from spotsnagger.notifications import CAMPSITE_NOTIFICATIONS, MultiNotifierProvider
from spotsnagger.providers import GoingToCamp
from spotsnagger.search import CAMPSITE_SEARCH_PROVIDER, BaseCampingSearch
from spotsnagger.trip import (
    ProviderAvailability,
    Trip,
    find_itineraries,
    parse_park,
)
from spotsnagger.utils import (
    configure_spotsnagger,
    log_spotsnagger,
    make_list,
    yaml_utils,
)
from spotsnagger.utils.general_utils import (
    days_of_the_week_mapping,
    handle_search_windows,
)

logging.Logger.spotsnagger = log_spotsnagger
logger = logging.getLogger(__name__)

DEFAULT_SPOTSNAGGER_PROVIDER: str = GoingToCamp.__name__

rich_click.STYLE_OPTION = "bold green"
rich_click.STYLE_SWITCH = "bold blue"
rich_click.STYLE_METAVAR = "bold red"
rich_click.STYLE_HELPTEXT_FIRST_LINE = "bold blue"
rich_click.STYLE_HELPTEXT = ""
rich_click.STYLE_HEADER_TEXT = "bold green"
rich_click.STYLE_OPTION_DEFAULT = "bold yellow"
rich_click.STYLE_OPTION_HELP = ""
rich_click.STYLE_ERRORS_SUGGESTION = "bold red"
rich_click.STYLE_OPTIONS_TABLE_BOX = "SIMPLE_HEAVY"
rich_click.STYLE_COMMANDS_TABLE_BOX = "SIMPLE_HEAVY"
if logging_config.LOG_HANDLER == "python":
    rich_click.COLOR_SYSTEM = None

try:
    from trogon import tui
except ImportError:

    def tui(*args, **kwargs):
        """
        TUI Placeholder - trogon not installed
        """

        def placeholder(app: click.Group):
            """
            Return the group in place
            """
            return app

        return placeholder


@dataclass
class SpotSnaggerContext:
    """
    Context Object Passed Around Application
    """

    debug: Optional[bool] = None
    provider: Optional[str] = None


provider_argument = click.option(
    "--provider",
    show_default=False,
    default=None,
    type=click.Choice(CAMPSITE_SEARCH_PROVIDER.keys(), case_sensitive=False),
    help="Camping Search Provider. Defaults to 'GoingToCamp'",
    metavar="TEXT",
    envvar="SPOTSNAGGER_PROVIDER",
)
debug_option = click.option(
    "--debug/--no-debug", default=None, help="Enable extra debugging output"
)


def _set_up_debug(debug: Optional[bool] = None) -> None:
    """
    Set up the SpotSnagger Debugging Mode
    """
    if debug is None:
        debug = False
    if debug is True:
        set_up_logging(log_level=logging.DEBUG)
        logger.debug("Setting up spotsnagger debugging")
        logger.debug("SpotSnagger Version: %s", __version__)
        logger.debug("Python Version: %s", sys.version.split(" ")[0])
        logger.debug("Platform: %s", sys.platform)
    traceback.install(show_locals=debug, suppress=[click, rich_click])


def _preferred_provider(
    context: SpotSnaggerContext, command_provider: Optional[str]
) -> str:
    """
    Called to get the preferred subcommands provider.

    It establishes rules for the "preferred" provider. That is, when multiple
    providers are elgigible to serve a command, the one that is most specific is
    chosen. Preference is in the following order:

    1. The provider explicitly provided to a spotsnagger subcommand
    2. The provider associated with SpotSnaggerContext
    3. The default provider

    The preferred provider is returned
    """
    if command_provider:
        provider = command_provider
    elif command_provider is None and context.provider:
        provider = context.provider
    else:
        provider = DEFAULT_SPOTSNAGGER_PROVIDER
    logger.info('Using SpotSnagger Provider: "%s"', provider)
    return provider


@tui()
@click.group(cls=RichGroup)
@debug_option
@provider_argument
@click.version_option(version=__version__, prog_name=__application__)
@click.pass_context
def spotsnagger_command_line(
    ctx: click.core.Context, debug: bool, provider: Optional[str]
) -> None:
    """
    Welcome to spotsnagger, the campsite finder.

    Finding reservations at sold out campgrounds can be
    tough. That's where spotsnagger comes in. It searches the APIs of booking services like
    GoingToCamp (which serves Parks Canada and provincial parks) to continuously
    check for cancellations and availabilities to pop up. Once a campsite becomes available,
    spotsnagger sends you a notification to book your spot!

    \b

    visit the spotsnagger documentation at https://juftin.com/camply
    """
    set_up_logging(log_level=None if debug is False else logging.INFO)
    logger.spotsnagger("spotsnagger, the campsite finder")
    ctx.obj = SpotSnaggerContext(debug=debug, provider=provider)
    _set_up_debug(debug=debug)


@spotsnagger_command_line.command(cls=RichCommand)
@debug_option
@click.pass_obj
def configure(context: SpotSnaggerContext, debug: bool) -> None:
    """
    Set up spotsnagger configuration file with an interactive console

    In order to send notifications through spotsnagger you must set up some authorization values.
    Whether you need to set up pushover notifications (push notifications on your phone,
    your pushover account can be set up at https://pushover.net) or Email messages, everything
    can be done through the configure command. The end result is a file called .spotsnagger in your
    home folder.
    """
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    configure_spotsnagger.generate_dot_spotsnagger_file()


# Shared Arguments
search_argument = click.option(
    "--search",
    default=None,
    help="Search for Campgrounds or Recreation Areas by search string.",
)
state_argument = click.option("--state", default=None, help="Filter by US state code.")
campsite_id_argument = click.option(
    "--campsite", default=None, multiple=True, help="Add individual Campsites by ID."
)
rec_area_argument = click.option(
    "--rec-area",
    default=None,
    multiple=True,
    help="Add Recreation Areas (comprised of campgrounds) by ID.",
)
campground_argument = click.option(
    "--campground",
    default=None,
    multiple=True,
    help="Add individual Campgrounds by ID.",
)
booking_category_argument = click.option(
    "--booking-category",
    default=None,
    type=int,
    help="Reservation service to search, e.g. Campsite (frontcountry), Backcountry, "
    "Roofed Accommodation or Group. Defaults to 0 (Campsite). IDs differ per "
    "recreation area: use `spotsnagger booking-categories --rec-area <rec area id>` "
    "to list them.",
)


@spotsnagger_command_line.command(cls=RichCommand)
@rec_area_argument
@provider_argument
@click.pass_obj
def booking_categories(
    context: SpotSnaggerContext,
    rec_area: Optional[int] = None,
    provider: str = DEFAULT_SPOTSNAGGER_PROVIDER,
) -> None:
    """
    List the reservation services of a recreation area

    Reservation services (booking categories) are things like frontcountry
    campsites, backcountry sites, roofed accommodations and group sites. Pass the
    ID to `--booking-category` when listing campgrounds or searching campsites.
    """
    provider = _preferred_provider(context, provider)
    if provider != GoingToCamp.__name__:
        logger.warning("That Provider doesn't support booking categories")
        sys.exit(0)
    if not rec_area:
        logger.error(
            "This provider requires --rec-area to be specified when listing booking categories"
        )
        sys.exit(1)
    GoingToCamp().list_booking_categories(rec_area[0], log=True)
    sys.exit(0)


@spotsnagger_command_line.command(cls=RichCommand)
@rec_area_argument
@provider_argument
@click.pass_obj
def equipment_types(
    context: SpotSnaggerContext,
    rec_area: Optional[int] = None,
    provider: str = DEFAULT_SPOTSNAGGER_PROVIDER,
) -> None:
    """
    Get a list of supported equipment

    This command returns supported equipment for the current provider/recreation area.
    Equipment are camping equipment that can be used at a campsite. Different providers
    and recreation areas have different types of equipment for which reservations can be made.
    """
    provider = _preferred_provider(context, provider)
    if not rec_area and provider == GoingToCamp.__name__:
        logger.error(
            "This provider requires --rec-area to be specified when listing equipment types"
        )
        sys.exit(1)

    if provider == GoingToCamp.__name__:
        GoingToCamp().list_equipment_types(rec_area[0])
    else:
        logger.warning("That Provider doesn't support equipment based searching, yet")
    sys.exit(0)


@spotsnagger_command_line.command(cls=RichCommand)
@search_argument
@state_argument
@debug_option
@provider_argument
@click.pass_obj
def recreation_areas(
    context: SpotSnaggerContext,
    search: Optional[str],
    state: Optional[str],
    debug: bool,
    provider: str = DEFAULT_SPOTSNAGGER_PROVIDER,
) -> None:
    """
    Search for Recreation Areas and list them

    Search for Recreation Areas and their IDs. Recreation Areas are places like
    National Parks and National Forests that can contain one or many campgrounds.
    """
    provider = _preferred_provider(context, provider)
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    if all(
        [
            search is None,
            state is not None,
            provider == GoingToCamp.__name__,
        ]
    ):
        # State Filtering Not Supported
        logger.error(
            f"{provider} does not support filtering recreation areas by state. Leave --state blank."
        )
        sys.exit(1)
    if provider == GoingToCamp.__name__:
        rec_area_finder = GoingToCamp()
    else:
        rec_area_finder = CAMPSITE_SEARCH_PROVIDER[provider]
    params = {}
    if state is not None:
        params.update({"state": state})
    rec_area_finder.find_recreation_areas(search_string=search, **params)


@spotsnagger_command_line.command(cls=RichCommand)
@search_argument
@state_argument
@rec_area_argument
@campground_argument
@campsite_id_argument
@booking_category_argument
@provider_argument
@debug_option
@click.pass_obj
def campgrounds(
    context: SpotSnaggerContext,
    debug: bool,
    search: Optional[str] = None,
    state: Optional[str] = None,
    rec_area: Optional[int] = None,
    campground: Optional[int] = None,
    campsite: Optional[int] = None,
    booking_category: Optional[int] = None,
    provider: Optional[str] = DEFAULT_SPOTSNAGGER_PROVIDER,
) -> None:
    """
    Search for Campgrounds (inside of Recreation Areas) and list them

    Search for Campgrounds and their IDs. Campgrounds are facilities inside of
    Recreation Areas that contain campsites. Most 'campgrounds' are areas made up of
    multiple campsites, others are facilities like fire towers or cabins that might only
    contain a single 'campsite' to book.
    """
    provider = _preferred_provider(context, provider)
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    if all(
        [
            search is None,
            state is None,
            len(rec_area) == 0,
            len(campground) == 0,
            len(campsite) == 0,
            provider != GoingToCamp.__name__,
        ]
    ):
        logger.error(
            "You must add a --search, --state, --campground, --campsite, "
            "or --rec-area parameter to search for Campgrounds."
        )
        sys.exit(1)
    search_provider_class = CAMPSITE_SEARCH_PROVIDER[provider]
    camp_finder = search_provider_class.provider_class()
    params: Dict[str, Any] = {}
    if state is not None:
        params.update({"state": state})
    if booking_category is not None:
        params.update({"booking_category_id": booking_category})
    camp_finder.find_campgrounds(
        search_string=search,
        rec_area_id=make_list(rec_area, coerce=int),
        campground_id=make_list(campground, coerce=int),
        campsite_id=make_list(campsite, coerce=int),
        **params,
    )


# `campsite` arguments
start_date_argument = click.option(
    "--start-date",
    multiple=True,
    default=None,
    help="(YYYY-MM-DD) Start of Search window. You will be arriving this day.",
)
end_date_argument = click.option(
    "--end-date",
    multiple=True,
    default=None,
    help="(YYYY-MM-DD) End of Search window. You will be checking out this day.",
)
weekends_argument = click.option(
    "--weekends",
    is_flag=True,
    show_default=True,
    default=False,
    help="Only search for weekend bookings (Fri/Sat nights).",
)
nights_argument = click.option(
    "--nights",
    show_default=True,
    default=1,
    type=click.INT,
    help="Search for campsite stays with consecutive nights. "
    "Defaults to 1 which returns all campsites found.",
)
continuous_argument = click.option(
    "--continuous",
    is_flag=True,
    show_default=True,
    default=False,
    help="Continuously check for a campsite to become available, and quit once "
    "at least one campsite is found.",
)
polling_interval_argument = click.option(
    "--polling-interval",
    default=None,
    type=click.INT,
    help="Enables continuous searching. How often to wait in between "
    "checks (in minutes). Defaults to 10, cannot be less than 5.",
)

_joined_notifications = [f"`{item}`" for item in CAMPSITE_NOTIFICATIONS.keys()]
notification_kwargs = {
    "multiple": True,
    "show_default": True,
    "metavar": "TEXT",
    "type": click.Choice(
        choices=list(CAMPSITE_NOTIFICATIONS.keys()), case_sensitive=False
    ),
    "default": [],
    "help": "Enables continuous searching. Types of notifications to receive. "
    f"Options available are {', '.join(_joined_notifications)}. "
    "Defaults to `silent` - "
    "which just logs messages to console.",
}
notifications_argument = click.option("--notifications", **notification_kwargs)
notify_first_try_argument = click.option(
    "--notify-first-try",
    is_flag=True,
    flag_value="FLAG-SET",
    help="Enables continuous searching. Whether to send all "
    "non-silent notifications if more than 5 matching "
    "campsites are found on the first try. Defaults to False which "
    "only sends the first 5.",
)
search_forever_argument = click.option(
    "--search-forever",
    is_flag=True,
    flag_value="FLAG-SET",
    help="Enables continuous searching. This method continues to search "
    "after the first availability has been found. The one caveat is "
    "that it will never notify about the same identical campsite for "
    "the same booking date.",
)
search_once_argument = click.option(
    "--search-once",
    is_flag=True,
    default=False,
    help="Enables continuous searching features - but doesn't actually "
    "search continuously. This option is only useful when you want to run spotsnagger "
    "periodically in a CRON job fashion but still receive notifications - "
    "it's strongly recommended you enable offline searching as well to "
    "save results between searches.",
)
yaml_config_argument = click.option(
    "--yaml-config",
    "--yml-config",
    default=None,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="Rather than provide arguments to the command line utility, instead "
    "pass a file path to a YAML configuration file. See the documentation "
    "for more information on how to structure your configuration file.",
)
equipment_argument = click.option(
    "--equipment",
    default=None,
    nargs=2,
    multiple=True,
    help="Search for campsites compatible with your camping equipment. "
    "This argument accepts two options, the equipment name and its length "
    "If you don't want to filter based on length provide a length of 0. Accepted "
    "equipment names include `Tent`, `RV`. `Trailer`, `Vehicle` and are "
    "not case-sensitive.",
)
equipment_id_argument = click.option(
    "--equipment-id",
    default=None,
    help="Search for campsites compatible with specific equipment categories. Going To "
    "Camp uses equipment category IDs for filtering campsites by equipment. Every "
    "recreation area has equipment categories unique to it. "
    "Use `spotsnagger equipment-types --provider GoingToCamp --rec-area <rec area id>` "
    "to get a listing of equipment for an area.",
)

offline_search_argument = click.option(
    "--offline-search",
    is_flag=True,
    show_default=True,
    default=False,
    help="When set to True, the campsite search will both save the results of the "
    "campsites it's found, but also load those campsites before beginning a "
    "search for other campsites.",
)
offline_search_path_argument = click.option(
    "--offline-search-path",
    show_default=True,
    default=None,
    type=click.Path(dir_okay=False),
    help="Enables offline search. This is the name of the file to be saved/loaded. "
    "Campsites can be saved as a serialized pickle file or "
    "a JSON file, depending on the file extension. When not specified, "
    "the filename will default to `spotsnagger_campsites.json`",
)
save_argument = click.option(
    "--save",
    default=None,
    metavar="NAME",
    help="Save this search under NAME (replacing any with that name) so it can be "
    "searched again later with `spotsnagger saved run NAME` or from the web UI.",
)
day_of_the_week_argument = click.option(
    "--day",
    multiple=True,
    show_default=False,
    type=click.Choice(
        choices=list(days_of_the_week_mapping.keys()), case_sensitive=False
    ),
    metavar="TEXT",
    help="Day(s) of the Week to search.",
)


def _get_equipment(equipment: Optional[List[str]]) -> List[Tuple[str, Optional[int]]]:
    """
    Parse Equipment from CLI Args
    """
    equipment_list = []
    for equipment_name, equipment_length in equipment:
        try:
            equipment_length = round(float(equipment_length), 0)
            if equipment_length == 0:
                equipment_length = None
        except ValueError:
            equipment_length = None
        equipment_list.append((equipment_name, equipment_length))
    return equipment_list


def _validate_campsites(
    rec_area: Optional[int],
    campground: Optional[int],
    campsite: Optional[int],
    start_date: Tuple[str],
    end_date: Tuple[str],
    provider: str,
    yaml_config: Optional[str],
    continuous: bool,
    polling_interval: int,
    notifications: List[str],
    notify_first_try: bool,
    search_forever: bool,
    search_once: bool,
    day: Optional[Tuple[str]],
    **kwargs: Dict[str, Any],
) -> Tuple[bool, List[SearchWindow], Set[int]]:
    """
    Validate the campsites portion of the CLI

    Also, indicate whether the search should be continuous.

    Parameters
    ----------
    rec_area: Optional[int]
    campground: Optional[int]
    campsite: Optional[int]
    start_date: Optional[str]
    end_date: Optional[str]
    provider: str
    yaml_config: Optional[str]
    continuous: bool
    polling_interval: int
    notifications: List[str]
    notify_first_try: bool
    search_forever: bool
    day: Optional[Tuple[str]]
    **kwargs: Dict[str, Any]

    Returns
    -------
    Tuple[bool, List[SearchWindow], Set[int]]
        Tuple containing continuous run eval, search_windows,
        and days of the week
    """
    if yaml_config is None:
        search_windows = handle_search_windows(start_date=start_date, end_date=end_date)
    else:
        search_windows = ()
    days_of_the_week = None
    if day is not None:
        days_of_the_week = {days_of_the_week_mapping[item] for item in day}
    if search_once is True and (continuous is True or search_forever is not None):
        logger.error(
            "You cannot specify `--search-once` alongside `--continuous` or `--search-forever`"
        )
        sys.exit(1)

    if any(
        [
            len(notifications) > 0,
            search_forever is not None,
            notify_first_try is not None,
            polling_interval is not None,
            search_once is True,
        ]
    ):
        continuous = True
    return continuous, search_windows, days_of_the_week


def _get_provider_kwargs_from_cli(
    rec_area: Tuple[Union[str, int]],
    campground: Tuple[Union[str, int]],
    campsite: Tuple[Union[str, int]],
    start_date: str,
    end_date: str,
    weekends: bool,
    nights: int,
    provider: Optional[str],
    continuous: bool,
    polling_interval: Optional[str],
    notifications: Tuple[str],
    notify_first_try: Optional[str],
    search_forever: Optional[str],
    search_once: bool,
    yaml_config: Optional[str],
    offline_search: bool,
    offline_search_path: Optional[str],
    equipment: Tuple[Union[str, int]],
    equipment_id: Tuple[Union[str, int]],
    day: Optional[Tuple[str]],
    booking_category: Optional[int] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Get Provider kwargs from CLI
    """
    notifications = make_list(notifications)
    continuous, search_windows, days_of_the_week = _validate_campsites(
        rec_area=rec_area,
        campground=campground,
        campsite=campsite,
        start_date=start_date,
        end_date=end_date,
        weekends=weekends,
        nights=nights,
        provider=provider,
        yaml_config=yaml_config,
        continuous=continuous,
        polling_interval=polling_interval,
        notifications=notifications,
        notify_first_try=notify_first_try,
        search_forever=search_forever,
        search_once=search_once,
        day=day,
    )
    if len(notifications) == 0:
        notifications = ["silent"]
    if polling_interval is None:
        polling_interval = SearchConfig.RECOMMENDED_POLLING_INTERVAL
    if notify_first_try is None:
        notify_first_try = False
    else:
        notify_first_try = True
    if search_forever is None:
        search_forever = False
    else:
        search_forever = True
    provider_kwargs = {
        "search_window": search_windows,
        "recreation_area": make_list(rec_area),
        "campgrounds": make_list(campground),
        "campsites": make_list(campsite),
        "weekends_only": weekends,
        "nights": int(nights),
        "offline_search": offline_search,
        "offline_search_path": offline_search_path,
        "equipment": equipment,
        "equipment_id": equipment_id,
        "booking_category_id": booking_category,
        "days_of_the_week": days_of_the_week,
    }
    search_kwargs = {
        "log": True,
        "verbose": True,
        "continuous": continuous,
        "polling_interval": float(polling_interval),
        "notify_first_try": notify_first_try,
        "notification_provider": notifications,
        "search_forever": search_forever,
        "search_once": search_once,
    }
    return provider_kwargs, search_kwargs


@spotsnagger_command_line.command(cls=RichCommand)
@rec_area_argument
@campground_argument
@campsite_id_argument
@start_date_argument
@end_date_argument
@nights_argument
@weekends_argument
@day_of_the_week_argument
@notifications_argument
@continuous_argument
@search_forever_argument
@yaml_config_argument
@offline_search_argument
@offline_search_path_argument
@search_once_argument
@polling_interval_argument
@notify_first_try_argument
@equipment_argument
@equipment_id_argument
@booking_category_argument
@provider_argument
@save_argument
@debug_option
@click.pass_obj
def campsites(
    context: SpotSnaggerContext,
    debug: bool,
    rec_area: Tuple[Union[str, int]],
    campground: Tuple[Union[str, int]],
    campsite: Tuple[Union[str, int]],
    start_date: str,
    end_date: str,
    weekends: bool,
    nights: int,
    provider: Optional[str],
    continuous: bool,
    polling_interval: Optional[str],
    notifications: Tuple[str],
    notify_first_try: Optional[str],
    search_forever: Optional[str],
    search_once: bool,
    yaml_config: Optional[str],
    offline_search: bool,
    offline_search_path: Optional[str],
    equipment: Tuple[Union[str, int]],
    equipment_id: Tuple[Union[str, int]],
    day: Optional[Tuple[str]],
    booking_category: Optional[int],
    save: Optional[str] = None,
) -> None:
    """
    Find Available Campsites with Custom Search Criteria

    Search for a campsite within spotsnagger. Campsites are returned based on the search criteria
    provided. Campsites contain properties like booking date, site type (tent, RV, cabin, etc),
    capacity, price, and a link to make the booking. Required parameters include
    `--start-date`, `--end-date`, `--rec-area` / `--campground`. Constant searching
    functionality can be enabled with  `--continuous` and notifications can be enabled using
    `--notifications`.
    """
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    if yaml_config is not None:
        if save:
            raise click.UsageError(
                "A --yaml-config search is already saved in its file"
            )
        provider, provider_kwargs, search_kwargs = yaml_utils.yaml_file_to_arguments(
            file_path=yaml_config
        )
        provider = _preferred_provider(context, provider)
    else:
        provider = _preferred_provider(context, provider)
        if save:
            # saved searches are the web UI's shape: one park, campground(s), one window
            unsupported = {
                "--campsite": campsite,
                "--equipment": equipment,
                "--equipment-id": equipment_id,
                "--day": day,
                "--weekends": weekends,
            }
            used = [flag for flag, value in unsupported.items() if value]
            if used or len(rec_area) != 1 or len(start_date) != 1 or len(end_date) != 1:
                raise click.UsageError(
                    "--save works with one --rec-area, one --start-date/--end-date and "
                    f"--campground(s) only{' (not ' + ', '.join(used) + ')' if used else ''}. "
                    "For anything more, keep the search in a --yaml-config file."
                )
            park = rec_area[0]
            _save(
                save,
                "search",
                {
                    "rec_area": f"aspira-{park}"
                    if provider.lower() == "aspira"
                    else park,
                    "campground": list(campground),
                    "start_date": start_date[0],
                    "end_date": end_date[0],
                    "nights": nights,
                    "booking_category": booking_category or 0,
                },
            )
        provider_kwargs, search_kwargs = _get_provider_kwargs_from_cli(
            rec_area=rec_area,
            campground=campground,
            campsite=campsite,
            start_date=start_date,
            end_date=end_date,
            weekends=weekends,
            nights=nights,
            provider=provider,
            continuous=continuous,
            polling_interval=polling_interval,
            notifications=notifications,
            notify_first_try=notify_first_try,
            search_forever=search_forever,
            search_once=search_once,
            offline_search=offline_search,
            offline_search_path=offline_search_path,
            equipment=equipment,
            equipment_id=equipment_id,
            day=day,
            yaml_config=yaml_config,
            booking_category=booking_category,
        )
    provider_class: Type[BaseCampingSearch] = CAMPSITE_SEARCH_PROVIDER[provider]
    camping_finder: BaseCampingSearch = provider_class(**provider_kwargs)
    camping_finder.get_matching_campsites(**search_kwargs)


def _save(name: str, kind: str, params: Dict[str, Any]) -> None:
    """
    Save a search or trip, turning bad input into a CLI usage error
    """
    try:
        item = saved.save(name, kind, params)
    except (ValueError, KeyError) as e:
        raise click.UsageError(f"Couldn't save {name!r}: {e}") from e
    logger.info(
        f'Saved as "{item["name"]}", run it again with: spotsnagger saved run "{item["name"]}"'
    )


def _parse_stop(text: str) -> Dict[str, str]:
    """
    `park=1 campground=-21,-22 nights=2-3 category=0 name="Lake"` -> TripStop fields
    """
    aliases = {"campground": "campgrounds", "category": "booking_category"}
    try:
        return {
            aliases.get(key, key): value
            for key, value in (item.split("=", 1) for item in shlex.split(text))
        }
    except ValueError as e:
        raise click.BadParameter(
            f"{text!r}: use key=value pairs, e.g. 'park=1 campground=-2147483643 nights=2-3'",
            param_hint="--stop",
        ) from e


@spotsnagger_command_line.command(cls=RichCommand)
@click.option(
    "--trip-file",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="YAML or JSON trip file (see docs/examples/example_trip.yaml). "
    "Command line options override what's in the file.",
)
@click.option(
    "--stop",
    "stops",
    multiple=True,
    metavar="TEXT",
    help="A stop, in order, as key=value pairs: `park` (rec area ID), `campground` "
    "(comma-separated IDs, any of them will do), `nights` (`2` or a range like `2-4`, "
    "`0-2` makes the stop optional), optional `category` and `name`. Repeat per stop.",
)
@start_date_argument
@end_date_argument
@click.option(
    "--start-day",
    multiple=True,
    type=click.Choice(
        choices=list(days_of_the_week_mapping.keys()), case_sensitive=False
    ),
    metavar="TEXT",
    help="Day(s) of the week the trip may start on (e.g. FRI). Defaults to any day.",
)
@click.option(
    "--any-order", is_flag=True, help="Allow the stops to be visited in any order."
)
@click.option("--min-total-nights", type=click.INT, help="Shortest whole trip.")
@click.option("--max-total-nights", type=click.INT, help="Longest whole trip.")
@click.option(
    "--max-results", type=click.INT, help="Stop after this many trips (default 25)."
)
@notifications_argument
@continuous_argument
@search_forever_argument
@polling_interval_argument
@save_argument
@debug_option
@click.pass_obj
def trip(
    context: SpotSnaggerContext,
    debug: bool,
    trip_file: Optional[str],
    stops: Tuple[str, ...],
    start_date: Tuple[str, ...],
    end_date: Tuple[str, ...],
    start_day: Tuple[str, ...],
    any_order: bool,
    min_total_nights: Optional[int],
    max_total_nights: Optional[int],
    max_results: Optional[int],
    notifications: Tuple[str, ...],
    continuous: bool,
    search_forever: Optional[str],
    polling_interval: Optional[int],
    save: Optional[str] = None,
) -> None:
    """
    Find a Trip: Back-to-Back Stays Across Several Campgrounds

    Each checkout is the next stop's check-in, so the whole trip has no gaps.
    Give one or more date ranges (`--start-date`/`--end-date` pairs) the trip must
    fit in, and a `--stop` per campground with a flexible number of nights. Stops
    can list alternative campgrounds, be optional, or be visited in any order.
    """
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    data: Dict[str, Any] = yaml_utils.read_yaml(trip_file) if trip_file else {}
    if stops:
        data["stops"] = [_parse_stop(stop) for stop in stops]
    if start_date or end_date:
        if len(start_date) != len(end_date):
            raise click.UsageError("Give one --end-date for every --start-date")
        data["windows"] = [
            {"start_date": s, "end_date": e} for s, e in zip(start_date, end_date)
        ]
    overrides = {
        "start_days": [days_of_the_week_mapping[d] for d in start_day] or None,
        "any_order": any_order or None,
        "min_total_nights": min_total_nights,
        "max_total_nights": max_total_nights,
        "max_results": max_results,
    }
    data.update({k: v for k, v in overrides.items() if v is not None})
    try:
        trip_plan = Trip.parse_obj(data)
    except ValidationError as e:
        raise click.UsageError(f"That trip isn't valid:\n{e}") from e
    if save:
        _save(save, "trip", json.loads(trip_plan.json()))
    _run_trip(trip_plan, notifications, continuous, search_forever, polling_interval)


def _run_trip(
    trip_plan: Trip,
    notifications: Sequence[str],
    continuous: bool,
    search_forever: Optional[str],
    polling_interval: Optional[int],
) -> None:
    """
    Search for a trip once, or keep searching and notify about new itineraries
    """
    continuous = bool(
        continuous or notifications or search_forever or polling_interval is not None
    )
    notifier = MultiNotifierProvider(list(notifications) or "silent")
    minutes = BaseCampingSearch._get_polling_minutes(polling_interval)
    available = ProviderAvailability()
    seen: Set[Any] = set()
    try:
        while True:
            available.cache.clear()
            new = [
                i for i in find_itineraries(trip_plan, available) if i.key not in seen
            ]
            seen.update(i.key for i in new)
            for number, itinerary in enumerate(new, start=1):
                logger.info(f"Trip option {number}: {itinerary.describe()}")
            if new and continuous:
                notifier.send_message(
                    f"{len(new)} new trip option(s) found:\n\n"
                    + "\n\n".join(i.describe() for i in new)
                )
            if not continuous or (new and not search_forever):
                break
            logger.info(
                f"No new trips found, checking again in {minutes} minutes"
                if not new
                else f"Searching again in {minutes} minutes"
            )
            sleep(minutes * 60)
    except Exception as e:
        if continuous:
            notifier.last_gasp(error=e)
        raise
    if not seen:
        logger.info("No gap-free trips found for those dates and stops")


@spotsnagger_command_line.group(cls=RichGroup, name="saved")
def saved_command() -> None:
    """
    Saved Searches and Trips (Shared with the Web UI)

    Save a search with `--save NAME` on `campsites` or `trip`, or with the Save
    button in `spotsnagger web`.
    """


@saved_command.command(name="list", cls=RichCommand)
def saved_list() -> None:
    """
    List saved searches and trips
    """
    items = saved.list_saved()
    if not items:
        logger.info("Nothing saved yet. Add --save NAME to a campsites or trip search.")
    for item in items:
        params = item["params"]
        if item["kind"] == "trip":
            what = f"trip, {len(params['stops'])} stops"
        else:
            what = f"search, {params['start_date']} to {params['end_date']}"
        logger.info(f"{item['name']} ({what}, saved {item['saved_at']})")


@saved_command.command(name="run", cls=RichCommand)
@click.argument("name")
@notifications_argument
@continuous_argument
@search_forever_argument
@polling_interval_argument
@click.pass_context
def saved_run(
    ctx: click.Context,
    name: str,
    notifications: Tuple[str, ...],
    continuous: bool,
    search_forever: Optional[str],
    polling_interval: Optional[int],
) -> None:
    """
    Search a saved search or trip again
    """
    try:
        item = saved.get_saved(name)
    except KeyError as e:
        raise click.UsageError(e.args[0]) from e
    params = item["params"]
    if item["kind"] == "trip":
        try:
            trip_plan = Trip.parse_obj(params)
        except ValidationError as e:
            raise click.UsageError(f"That trip isn't valid any more:\n{e}") from e
        _run_trip(
            trip_plan, notifications, continuous, search_forever, polling_interval
        )
        return
    is_aspira, rec_area = parse_park(params["rec_area"])
    ctx.invoke(
        campsites,
        provider="Aspira" if is_aspira else GoingToCamp.__name__,
        rec_area=(rec_area,),
        campground=tuple(make_list(params["campground"]) or ()),
        start_date=(params["start_date"],),
        end_date=(params["end_date"],),
        nights=int(params.get("nights") or 1),
        booking_category=int(params.get("booking_category") or 0),
        notifications=notifications,
        continuous=continuous,
        search_forever=search_forever,
        polling_interval=polling_interval,
    )


@saved_command.command(name="delete", cls=RichCommand)
@click.argument("name")
def saved_delete(name: str) -> None:
    """
    Delete a saved search or trip
    """
    try:
        saved.delete(name)
    except KeyError as e:
        raise click.UsageError(e.args[0]) from e
    logger.info(f'Deleted "{name}"')


@spotsnagger_command_line.command(cls=RichCommand)
@debug_option
@click.pass_obj
def providers(
    context: SpotSnaggerContext,
    debug: bool,
) -> None:
    """
    List the different spotsnagger providers
    """
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    logger.info(
        "spotsnagger currently supports %s providers:",
        len(CAMPSITE_SEARCH_PROVIDER.keys()),
    )
    for provider_name, search_class in CAMPSITE_SEARCH_PROVIDER.items():
        logger.info(
            '    "%s":    %s',
            provider_name,
            search_class.__doc__.strip().splitlines()[0],
        )


test_notifications_kwargs = notification_kwargs.copy()
test_notifications_kwargs["help"] = test_notifications_kwargs["help"].replace(
    "Enables continuous searching. ", ""
)
test_notifications_kwargs.pop("default")
test_notifications_kwargs["required"] = True


@spotsnagger_command_line.command(cls=RichCommand)
@click.option("--notifications", **test_notifications_kwargs)
@debug_option
@click.pass_obj
def test_notifications(
    context: SpotSnaggerContext, debug: bool, notifications: Container[str]
) -> None:
    """
    Test your notification provider setup
    """
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    notification_providers = make_list(notifications)
    provider = MultiNotifierProvider(provider=notification_providers)
    logger.info("Testing your notification providers:")
    for sub_provider in provider.providers:
        logger.info('\t"%s"', sub_provider)
    provider.send_campsites(campsites=[example_campsite])


@spotsnagger_command_line.command(cls=RichCommand)
@rec_area_argument
@campground_argument
@provider_argument
@debug_option
@click.pass_obj
def list_campsites(
    context: SpotSnaggerContext,
    debug: bool,
    campground: Sequence[int],
    rec_area: Sequence[int],
    provider: str,
) -> None:
    """
    List campsite IDs for a given campground or recreation area
    """
    provider = _preferred_provider(context, provider)
    if context.debug is None:
        context.debug = debug
        _set_up_debug(debug=context.debug)
    if all(
        [
            len(rec_area) == 0,
            len(campground) == 0,
        ]
    ):
        logger.error(
            "You must provide a `--campground` or `--rec-area` to list campsites"
        )
        sys.exit(1)
    search_provider_class = CAMPSITE_SEARCH_PROVIDER[provider]
    if search_provider_class.list_campsites_supported is False:
        logger.error("That provider does not support listing campsites")
        sys.exit(1)
    camp_search = search_provider_class(
        search_window=SearchWindow(
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=2),
        ),
        recreation_area=rec_area,
        campgrounds=campground,
        verbose=False,
    )
    logger.info("Searching for campsites to list")
    camp_search.list_campsite_units()


@spotsnagger_command_line.command(cls=RichCommand)
@click.option(
    "--port", default=8000, show_default=True, help="Port to serve the web UI on."
)
@click.option("--no-browser", is_flag=True, help="Don't open a browser window.")
@debug_option
@click.pass_obj
def web(context: SpotSnaggerContext, port: int, no_browser: bool, debug: bool) -> None:
    """
    Open a simple point-and-click campsite search in your web browser
    """
    from spotsnagger.web import serve

    _set_up_debug(debug=debug)
    serve(port=port, open_browser=not no_browser)


def cli():
    """
    SpotSnagger Command Line Utility Wrapper
    """
    try:
        spotsnagger_command_line()
    except KeyboardInterrupt:
        logger.debug("Handling Exit Request")
    finally:
        logger.spotsnagger("Exiting spotsnagger")


if __name__ == "__main__":
    cli()
