<div align="center">
<a href="https://github.com/juftin/camply">
  <img src="https://raw.githubusercontent.com/juftin/camply/main/docs/_static/camply.svg"
    width="400" height="400" alt="spotsnagger">
</a>
</div>

**`spotsnagger`**, the campsite finder, is a tool to help you book a campsite online. Finding
reservations at sold out campgrounds can be tough. That's where spotsnagger comes in. It searches
Canadian national, provincial and regional parks via the [GoingToCamp](https://goingtocamp.com)
booking platform. It continuously checks for cancellations and
availabilities to pop up - once a campsite becomes available, spotsnagger sends you a notification
to book your spot!

---

---

<p align="center">
  <a href="https://github.com/juftin/camply"><img src="https://img.shields.io/pypi/v/camply?color=blue&label=camply" alt="PyPI"></a>
  <a href="https://pypi.python.org/pypi/camply/"><img src="https://img.shields.io/pypi/pyversions/camply" alt="PyPI - Python Version"></a>
  <a href="https://hub.docker.com/r/juftin/camply"><img src="https://img.shields.io/docker/v/juftin/camply?color=blue&label=docker&logo=docker" alt="Docker Image Version"></a>
  <a href="https://github.com/juftin/camply/blob/main/LICENSE"><img src="https://img.shields.io/github/license/juftin/camply?color=blue&label=License" alt="GitHub License"></a>
  <a href="https://github.com/juftin/camply/actions/workflows/test.yaml?query=branch%3Amain"><img src="https://github.com/juftin/camply/actions/workflows/test.yaml/badge.svg?branch=main" alt="Testing Status"></a>
  <a href="https://github.com/go-task/task"><img src="https://img.shields.io/badge/task---?message=task&logo=task&color=teal&labelColor=grey" alt="task"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-lightgreen?logo=pre-commit" alt="pre-commit"></a>
  <a href="https://juftin.github.io/camply/"><img src="https://img.shields.io/static/v1?message=docs&color=526CFE&logo=Material+for+MkDocs&logoColor=FFFFFF&label=" alt="docs"></a>
  <a href="https://github.com/semantic-release/semantic-release"><img src="https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg" alt="semantic-release"></a>
</p>

## [Check Out The Docs](https://juftin.com/camply/)

## Installing

Install spotsnagger via `pip` or [pipx](https://github.com/pypa/pipx):

```commandline
pipx install spotsnagger
```

## Usage

List the supported recreation areas (recreation areas contain campgrounds):

```commandline
spotsnagger recreation-areas
```

Search for campgrounds inside a recreation area (campgrounds contain campsites).
Recreation Area #14 is Parks Canada:

```commandline
spotsnagger campgrounds --rec-area 14 --search "Two Jack"
```

Search for available campsites, get a notification whenever one becomes
available, and continue searching after the first one is found. The below command
is using `silent` notifications as an example but spotsnagger also supports `Email`,
`Slack`, `Twilio` (SMS), `Pushover`, `Pushbullet`, `Ntfy`, `Apprise`, `Telegram`,
and `Webhook`.

```commandline
spotsnagger campsites     --rec-area 14     --campground -2147483643     --start-date 2023-07-10     --end-date 2023-07-18     --notifications silent     --search-forever
```

## Providers

spotsnagger searches a single provider, **`GoingToCamp`** ([goingtocamp.com](https://goingtocamp.com)),
which is the default. It covers the following Canadian recreation areas:

- Parks Canada - Canada National Parks - [reservation.pc.gc.ca](https://reservation.pc.gc.ca/)
- BC Parks - British Columbia - [camping.bcparks.ca](https://camping.bcparks.ca)
- Manitoba Parks - Manitoba - [manitoba.goingtocamp.com](https://manitoba.goingtocamp.com)
- Nova Scotia Parks - Nova Scotia - [novascotia.goingtocamp.com](https://novascotia.goingtocamp.com)
- New Brunswick Provincial Parks - New Brunswick - [parcsnbparks.info](https://www.parcsnbparks.info/)
- Newfoundland & Labrador Provincial Parks - Newfoundland and Labrador - [nlcamping.ca](https://nlcamping.ca)
- Gatineau Park - Ontario-Quebec - [reservations.ncc-ccn.gc.ca](https://reservations.ncc-ccn.gc.ca)
- Algonquin Highlands - Ontario - [ahtrails.ca](https://ahtrails.ca)
- Long Point Region - Ontario - [longpoint.goingtocamp.com](https://longpoint.goingtocamp.com)
- Maitland Valley - Ontario - [maitlandvalley.goingtocamp.com](https://maitlandvalley.goingtocamp.com)
- Saugeen Valley - Ontario - [saugeen.goingtocamp.com](https://saugeen.goingtocamp.com)
- St. Clair Region - Ontario - [stclair.goingtocamp.com](https://stclair.goingtocamp.com)

Visit the [Providers](https://juftin.com/camply/providers/) section in the docs to learn more.

## Documentation

Head over to the [spotsnagger documentation](https://juftin.com/camply/) to see what you can do!

```console
❯ spotsnagger --help

 Usage: spotsnagger [OPTIONS] COMMAND [ARGS]...

 Welcome to spotsnagger, the campsite finder.
 Finding reservations at sold out campgrounds can be tough. That's where spotsnagger comes in. It searches the
 APIs of booking services like GoingToCamp (which serves Parks Canada and provincial parks) to
 continuously check for cancellations and availabilities to pop up. Once a campsite becomes available,
 spotsnagger sends you a notification to book your spot!


 visit the spotsnagger documentation at https://juftin.com/camply

╭─ Options ──────────────────────────────────────────────────────────────────────────────────────────────╮
│                                                                                                        │
│  --debug/--no-debug             Enable extra debugging output                                          │
│  --provider              TEXT   Camping Search Provider. Defaults to 'GoingToCamp'                     │
│  --version                      Show the version and exit.                                             │
│  --help                         Show this message and exit.                                            │
│                                                                                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────────────────────────╮
│                                                                                                        │
│  campgrounds              Search for Campgrounds (inside of Recreation Areas) and list them            │
│  campsites                Find Available Campsites with Custom Search Criteria                         │
│  configure                Set up spotsnagger configuration file with an interactive console                 │
│  equipment-types          Get a list of supported equipment                                            │
│  list-campsites           List campsite IDs for a given campground or recreation area                  │
│  providers                List the different spotsnagger providers                                          │
│  recreation-areas         Search for Recreation Areas and list them                                    │
│  test-notifications       Test your notification provider setup                                        │
│  tui                      Open Textual TUI.                                                            │
│                                                                                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Contributing

SpotSnagger doesn't support your favorite campsite booking provider yet? Consider
[contributing](https://juftin.com/camply/contributing/).

---

---

<br/>

[<p align="center" ><img src="https://raw.githubusercontent.com/juftin/juftin/main/static/juftin.png" width="120" height="120"  alt="juftin logo"> </p>](https://github.com/juftin)
