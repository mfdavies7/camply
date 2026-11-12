# Command Line Usage

When installed, `spotsnagger`'s command line utility can be invoked with the command, `spotsnagger`. The CLI
tool accepts the sub-commands `campsites`, `recreation-areas`, `campgrounds`, `providers`,
`equipment-types`, `configure`, `test-notifications`, and `tui`.

!!! important

    The multi-line commands in this documentation correspond to running **`spotsnagger`** on a
    MacOS or Linux Shell. If you are a Windows user take note that multi-line commands
    on Windows Shells use the **`^`** character instead of **`\`** to escape new lines.

```console
❯ spotsnagger --help

 Usage: spotsnagger [OPTIONS] COMMAND [ARGS]...

 Welcome to spotsnagger, the campsite finder.
 Finding reservations at sold out campgrounds can be tough. That's where spotsnagger comes in. It searches the
 APIs of booking services like GoingToCamp (which serves Parks Canada and provincial parks) to
 continuously check for cancellations and availabilities to pop up. Once a campsite becomes available,
 spotsnagger sends you a notification to book your spot!


 visit the spotsnagger documentation at https://mfdavies7.github.io/camply

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
│  providers                List the different spotsnagger providers                                          │
│  recreation-areas         Search for Recreation Areas and list them                                    │
│  test-notifications       Test your notification provider setup                                        │
│  tui                      Open Textual TUI.                                                            │
│                                                                                                        │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Simple Examples

[List the supported recreation areas](#search-for-recreation-areas-by-query-string) (recreation
areas contain campgrounds):

```commandline
spotsnagger recreation-areas
```

[Search for campgrounds inside a recreation area](#look-for-specific-campgrounds-within-a-recreation-area)
(campgrounds contain campsites). Recreation Area #14 is Parks Canada:

```commandline
spotsnagger campgrounds --rec-area 14 --search "Two Jack"
```

[Search for available campsites](#searching-for-a-campsite),
[get an notification whenever one becomes available](#send-a-push-notification), and
[continue searching after the first one is found](#continue-looking-after-the-first-match-is-found):

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-10 \
    --end-date 2023-07-18 \
    --notifications email \
    --search-forever
```

## providers

List the various [providers](providers.md) that spotsnagger works with.

```commandline
spotsnagger providers
```

!!! note

    spotsnagger has a single provider, **`GoingToCamp`**, which is used by default.
    It searches Canadian recreation areas, campgrounds, and campsites
    listed on https://goingtocamp.com

## campsites

Search for a campsite within spotsnagger. Campsites are returned based on the search criteria provided.
Campsites contain properties like booking date, site type (tent, RV, cabin, etc), capacity, price,
and a link to make the booking. Required parameters include `--start-date`, `--end-date`,
a single `--rec-area`, and at least one `--campground`. Constant searching functionality can be enabled with
`--continuous` and notifications can be enabled using `--notifications` (see the
[Send a Push Notification](#send-a-push-notification) section for more information).

### Arguments

- `--rec-area`: `RECREATION_AREA_ID`
    - The Recreation Area (comprised of campgrounds) to search, by ID. Only one is allowed.
      [\*\*_example_](#searching-for-a-campsite)
- `--campground`: `CAMPGROUND_ID`
    - Add individual Campgrounds by ID.
      [\*\*_example_](#searching-for-a-campsite)
- `--campsite`: `CAMPSITE_ID`
    - Add individual Campsites by ID.
      [\*\*_example_](#searching-for-a-specific-campsite-by-id)
- `--start-date`: `START_DATE`
    - `YYYY-MM-DD`: Start of Search window. You will be arriving this day.
      [\*\*_example_](#searching-for-a-campsite)
- `--end-date`: `END_DATE`
    - `YYYY-MM-DD`: End of Search window. You will be checking out this day..
      [\*\*_example_](#searching-for-a-campsite)
- `--day`
    - Day(s) of the Week to search.
      [\*\*_example_](#searching-for-specific-weekdays)
- `--weekends`
    - Only search for weekend bookings (Fri/Sat nights).
      [\*\*_example_](#look-for-weekend-campsite-availabilities)
- `--nights`
    - Search for campsite stays with consecutive nights. Defaults to 1 which returns all campsites
      found.
      [\*\*_example_](#look-for-consecutive-nights-at-the-same-campsite)
- `--provider`: `PROVIDER`
    - Camping Search Provider. Defaults to 'GoingToCamp', the only supported provider, not case-sensitive.
- `--continuous`
    - Continuously check for a campsite to become available, and quit once at least one campsite is
      found.
      [\*\*_example_](#continuously-searching-for-a-campsite)
- `--search-forever`
    - Enables continuous searching. This method continues to search after the first availability
      has been found. The one caveat is that it will never notify about the same identical campsite
      for the same booking date.
      [\*\*_example_](#continue-looking-after-the-first-match-is-found)
- `--notifications`: `NOTIFICATIONS`
    - Enables continuous searching. Types of notifications to receive. Options available
      are `pushover`, `email`, `ntfy`, `apprise`, `pushbullet`, `slack`, `telegram`, `twilio`,
      `webhook`, `silent`.
      Defaults to `silent` - which just logs messages to console.
      [\*\*_example_](#send-a-push-notification)
- `--equipment-id`
    - Search for campsites compatible with specific equipment categories. GoingToCamp
      uses equipment category IDs for filtering campsites by equipment. Every recreation
      area has equipment categories unique to it.
      [\*\*_example_](#searching-using-equipment)
- `--notify-first-try`
    - Enables continuous searching. Whether to send all non-silent notifications if more than 5
      matching campsites are found on the first try. Defaults to false which only sends the first5.
      [\*\*_example_](#continuously-searching-for-a-campsite)
- `--polling-interval`: `POLLING_INTERVAL`
    - Enables continuous searching. How often to wait in between checks (in minutes). Defaults to
      10, cannot be less than 5.
      [\*\*_example_](#look-for-weekend-campsite-availabilities)
- `--yaml-config`
    - Rather than provide arguments to the command line utility, instead pass a file path to a YAML
      configuration file. See the documentation for more information on how to structure your
      configuration file.
      [\*\*_example_](#using-a-yaml-configuration-file-to-search-for-campsites)
- `--offline-search`
    - When set to True, the campsite search will both save the results of the campsites it's
      found, but also load those campsites before beginning a search for other campsites.
      [\*\*_example_](#saving-the-results-of-a-search)
- `--offline-search-path`
    - Enables offline search. This is the name of the file to be saved/loaded. Campsites can be saved as
      a serialized pickle file or a JSON file, depending on the file extension. When not specified,
      the filename will default to `spotsnagger_campsites.json`.
      [\*\*_example_](#saving-the-results-of-a-search)
- `--search-once`
    - Enables continuous searching features - but doesn't actually search continuously. This option
      is only useful when you want to run spotsnagger periodically in a CRON job fashion but still
      receive notifications - it's strongly recommended you enable offline searching as
      well to save results between searches.
      [\*\*_example_](#run-spotsnagger-as-a-cron-job)

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-10 \
    --end-date 2023-07-18
```

## trip

Find a trip: back-to-back stays across several campgrounds with no gaps, so each
checkout is the next stop's check-in. Every stop takes a flexible number of
nights, and can list alternative campgrounds (any one will do), be optional
(`nights=0-2`) or, with `--any-order`, be visited in any order. The trip must
fit inside one of the `--start-date` / `--end-date` ranges given. Limit it
further with `--start-day` (e.g. `FRI`), `--min-total-nights`,
`--max-total-nights` and `--max-results`. `--continuous`, `--notifications`,
`--polling-interval` and `--search-forever` work as they do for `campsites`.

```commandline
spotsnagger trip     --start-date 2027-07-01 --end-date 2027-07-15     --stop "park=1 campground=-2147483643 nights=2-3 name=First"     --stop "park=1 campground=-2147483642,-2147483647 nights=1-2"     --start-day FRI     --notifications pushover
```

Alternative locations across different parks need a trip file (YAML or JSON);
see [example_trip.yaml](examples/example_trip.yaml).

```commandline
spotsnagger trip --trip-file example_trip.yaml
```

The web UI (`spotsnagger web`) has the same options under its **Trip** tab.

## saved

Save a search or trip to search it again later: add `--save NAME` to
`campsites` or `trip`, or press **Save** in the web UI. Both share the same list,
stored in `~/.spotsnagger_saved.json`, so a search saved in one can be run from
the other. `campsites --save` keeps one park, its campground(s), one date range,
nights and type of stay; keep anything more involved in a `--yaml-config` file.

```commandline
spotsnagger trip --start-date 2027-07-01 --end-date 2027-07-15     --stop "park=1 campground=-2147483643 nights=2-3" --save "July loop"
spotsnagger saved list
spotsnagger saved run "July loop" --notifications pushover
spotsnagger saved delete "July loop"
```

`saved run` accepts `--continuous`, `--notifications`, `--polling-interval` and
`--search-forever`. Saved dates don't move, so once they've passed, save again
with new ones.

## recreation-areas

Search for Recreation Areas and their IDs. Recreation Areas are park systems like Parks Canada or
BC Parks that can contain one or many campgrounds.

### Arguments

- `--search` `SEARCH`
    - Search for Recreation Areas by search string.

```commandline
spotsnagger recreation-areas --search "Parks Canada"
```

\*\*_see the [examples](#search-for-recreation-areas-by-query-string) for more information_

## campgrounds

Search for Campgrounds and their IDs. Campgrounds are facilities inside of Recreation Areas that
contain campsites. Most 'campgrounds' are areas made up of multiple campsites, others are facilities
like fire towers or cabins that might only contain a single 'campsite' to book.

### Arguments

- `--rec-area`: `RECREATION_AREA_ID`
    - The Recreation Area to list campgrounds for (required).
- `--search` `SEARCH`
    - Filter Campgrounds by search string.
- `--campground`: `CAMPGROUND_ID`
    - Add individual Campgrounds by ID.

```commandline
spotsnagger campgrounds --rec-area 14 --search "Two Jack"
```

\*\*_see the [examples](#look-for-specific-campgrounds-within-a-recreation-area) for more information_

## configure

Set up `spotsnagger` configuration file with an interactive console

In order to send notifications through `spotsnagger` you must set up some authorization values. Whether
you need to set up [Pushover notifications](https://pushover.net)
, [PushBullet](https://www.pushbullet.com/#settings/account), [Telegram](https://core.telegram.org/bots),
or Email messages, everything can be done through the `configure` command. The end result is a file called
[`.spotsnagger`](examples/example.spotsnagger) in your home folder. See
the [Running in Docker](how_to_run.md#running-in-docker) section to see how you can use environment variables
instead of a config file.

```commandline
spotsnagger configure
```

## test-notifications

Test your notification provider setup.

If you want to send yourself a test notification via spotsnagger, the `test-notifiactions`
command is for you. See the [Send a Push Notification](#send-a-push-notification)
section for more details on how to set up the notification provider of your choice.

```commandline
spotsnagger test-notifications --notifications email
```

## tui

SpotSnagger has an optional TUI interface thanks to [textual](https://github.com/textualize/textual) and
[trogon](https://github.com/Textualize/trogon). A TUI is a text-based user interface that allows you to
interact with spotsnagger in a more visual way, it's a visual application that runs in your terminal.
The TUI config is a great way to set up your camp search with your mouse and keyboard, and then run
spotsnagger like you normally would.

!!! note

    SpotSnagger's TUI command requires that the **`tui`** extra is installed. To install spotsnagger with
    the TUI extra, run **`pipx install "spotsnagger[tui]"`**.

```commandline
spotsnagger tui
```

![spotsnagger TUI](_static/tui.png)

## Examples

Read through the examples below to get a better understanding of `spotsnagger`, its features, and the
functionality of the different arguments provided to the CLI.

### Finding Campground IDs

GoingToCamp campsite searches need a Recreation Area ID and at least one Campground ID.
First, find your Recreation Area ID:

```commandline
spotsnagger recreation-areas
```

For this example we'll search Parks Canada, which corresponds to Recreation Area ID #14.
Next, list the Campgrounds within the Recreation Area:

```commandline
spotsnagger campgrounds --rec-area 14
```

The above command lists all of the campgrounds within the Recreation Area. In the
following examples we'll search Two Jack Lakeside in Banff National Park, which
corresponds to Campground ID #-2147483643 (GoingToCamp regularly uses negative ID numbers).

### Searching for a Campsite

The below search looks for campsites at Two Jack Lakeside between 2023-07-10 and 2023-07-17.
The search will be performed once and any results will be logged to the console. spotsnagger
searches for campsites inside of search windows in increments of one night. `--start-date`
and `--end-date` define the bounds of the search window, you will be leaving the day after
`--end-date`. Multiple Campgrounds can be searched by supplying `--campground` more than once.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-10 \
    --end-date 2023-07-18
```

### Searching for a Specific Campsite by ID

Sometimes you have a favorite campsite inside your favorite campground. To search for just a
specific campsite you can give its ID to `spotsnagger` with the `--campsite` argument, alongside
its `--rec-area` and `--campground`. Campsite IDs are shown in the results of a regular
campsite search. You can provide the `--campsite` argument once or multiple times.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --campsite <CAMPSITE_ID> \
    --start-date 2023-07-10 \
    --end-date 2023-07-18
```

### Continuously Searching for A Campsite

Most of the time you want to look for campgrounds until an eventual match is found. The below snippet will
search for matching campsites until it finds a match. It also sends a notification via `pushover`
once matches are found. Alternate notification methods are listed in the
[Send a Push Notification](#send-a-push-notification) example.

!!! note

    The use of **`--continuous`** in the below example isn't actually necessary.
    Continuous searching is enabled when any of the following options are provided:
    **`--continuous`**, **`--notifications`**, **`--search-forever`**,
    **`--polling-interval`**, **`--notify-first-try`**.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-12 \
    --end-date 2023-07-13 \
    --continuous \
    --notifications pushover \
    --notify-first-try
```

!!! warning

    When `spotsnagger` is told to running continuously with non-silent notifications set up
    and it finds more than 5 matching campsites on the first try, it will only send notifications for
    the first 5 campsites. This is to prevent thousands of campsites flooding your notifications. It's
    always encouraged to perform an initial online search before setting up a `spotsnagger` search. To bypass
    this behavior and send all notifications, pass the `--notify-first-try` argument.

### Searching Across Multiple Time Windows

There might be an occasion where you're looking to search for a campsite across
multiple date ranges, i.e. any Monday in July. `spotsnagger` supports this quite nicely by
passing multiple `--start-date` and `--end-date` options.

!!! note

    The important rule about multiple **`--start-date`** and **`--end-date`** options
    is that ordering matters. If you provide multiple start dates and multiple end
    dates the first end date will correspond to the first start date, and so on
    and so forth.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-12 \
    --end-date 2023-07-13 \
    --start-date 2023-07-19 \
    --end-date 2023-07-20 \
    --start-date 2023-07-26 \
    --end-date 2023-07-27
```

### Continue Looking After The First Match Is Found

Sometimes you want to search for all possible matches up until your arrival date. No problem. Add
the `--search-forever` and `spotsnagger` won't stop sending notifications after the first match is found.

!!! note

    `spotsnagger` will save and store all previous notifications when
    **`--search-forever`** is enabled, so it won't notify you about the exact same
    campsite availability twice. This can be problematic when certain campsites become
    available more than once.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-01 \
    --end-date 2023-08-01 \
    --notifications pushover \
    --search-forever
```

### Send a Push Notification

spotsnagger supports notifications via a number of services:

- [Pushover](https://pushover.net)
- Email
- [Ntfy](https://ntfy.sh)
- [Apprise](https://github.com/caronc/apprise)
- [Pushbullet](https://www.pushbullet.com/#settings/account)
- [Slack](https://slack.com)
- [Telegram](https://core.telegram.org/bots)
- [Twilio (SMS)](https://www.twilio.com)
- Silent

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-09-10 \
    --end-date 2023-09-21 \
    --notifications pushover
```

Like all providers, `Pushover` requires that you share credentials/authentication - for `Pushover` this involves
sharing your "Pushover User Key" with spotsnagger through a [configuration file](examples/example.spotsnagger)
(via the **`spotsnagger configure`** command) or though environment variables (`PUSHOVER_PUSH_USER`). See the
[Environment Variables](how_to_run.md#environment-variables) section for a list of relevant environment variables
per notification provider.

!!! info

    When searching continuously `spotsnagger` uses the **`silent`** notification provider
    unless you expictly specify another notification provider to use. The **`silent`** notification
    provider simply prints logs to your console when matching campsites are found.

!!! note

    I personally use [Pushover](https://pushover.net) notifications - it's built for push notifications, easy to set up,
    and includes a 30-day trial and a one-time fee of $5 after that to unlock lifetime programmatic push notifications.
    There are other notification providers like `Ntfy`, `Slack` and `Email` that are free to use if that's more your style.

!!! note

    SpotSnagger provides a courtesy Pushover API token for you to use, however it's
    highly reccomended that you create and use your
    [own API token](https://pushover.net/apps/build). This is done via the
    `PUSHOVER_PUSH_TOKEN` environment variable. In the past, some users have exhausted the
    courtesy token's monthly limit with faulty spotsnagger configurations.

### Send a Text Message

If you want to sign up for a [Twilio](https://www.twilio.com/try-twilio) account, spotsnagger also supports
sending text messages via SMS. You can set up your Twilio configuration via `spotsnagger configure`. You will need
to set the following config values for Twilio: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_SOURCE_NUMBER`, `TWILIO_DEST_NUMBERS`.

Sending text messages via Twilio also requires the `twilio` extras:

```
pip install spotsnagger[twilio]
```

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-09-10 \
    --end-date 2023-09-21 \
    --notifications twilio
```

### Send a Notification to Different Services

spotsnagger supports notifications from different providers. To send notifications to multiple providers
you can pass the --notifications parameter multiple times. YAML config entries also
accept an array as well.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-09-10 \
    --end-date 2023-09-21 \
    --notifications email \
    --notifications pushover
```

### Send a Notification Using Apprise-Compatible Services

In addition to the built-in notification providers, you can also send notifications using one of the
many popular services supported by [Apprise](https://github.com/caronc/apprise). You'll need
to set up a supported notification URL using the `APPRISE_URL` config value; Refer to the Apprise
documentation to learn how to format a URL to fit your needs.

Using Apprise notifications requires the `apprise` extras:

```
pip install spotsnagger[apprise]
```

### Searching for Specific Weekdays

The below search spans across a three-month time window, but it only looks for campsites that
are available on a Tuesday or Wednesday night.

!!! note

    You can use the day's full spelling or an abbreviation - and neither is case sensitive.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-05-01 \
    --end-date 2023-08-01 \
    --day Tuesday \
    --day Wednesday
```

### Look for Weekend Campsite Availabilities

This below search looks across larger periods of time, but only if a campground is available to book
on a Friday or Saturday night (`--weekends`). It also uses the `--polling-interval` argument which
checks every 5 minutes instead of the default 10 minutes.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-05-01 \
    --end-date 2023-08-01 \
    --weekends \
    --notifications email \
    --polling-interval 5
```

!!! note

    Using the **`--weekends`** option is the same as specifying
    **`--day Friday`** + **`--day Saturday`**.

### Look for Consecutive Nights at the Same Campsite

A lot of times you need to search for consecutive nights at the same campsite. By default, any and
all campsites with a single nights booking are returned by spotsnagger. To search for campsites with
consecutive night stays, pass the `--nights` argument.

!!! note

    The **`--nights`** argument handles issues with improper search parameters. For example, if you
    set the **`--weekends`** parameter the maximum number of consecutive nights possible is 2. If you supply
    more than this your **`--nights`** parameter will be overwritten to 2.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-05-01 \
    --end-date 2023-08-01 \
    --nights 4
```

### Searching Using Equipment

GoingToCamp allows you to search for campsites using equipment filters. In order to find the
corresponding equipment IDs, use the `equipment-types` command and pass in the Recreation Area ID:

```commandline
spotsnagger equipment-types --rec-area 1
```

The previous command lists all of the Equipment IDs for Recreation Area #1 (Long Point Region),
such as `Trailer up to 25ft` and `Trailer up to 40ft`. Next, use an Equipment ID in your search:

```commandline
spotsnagger campsites \
  --rec-area 1 \
  --campground -2147483643 \
  --start-date 2023-09-01 \
  --end-date 2023-09-02 \
  --equipment-id -32768
```

### Using a YAML Configuration file to search for campsites

Sometimes, using a YAML configuration file is easier to manage all of your search options. See the
below [YAML example file](examples/example_search.yaml) and corresponding spotsnagger command:

```yaml
--8<-- "docs/examples/example_search.yaml"
```

```commandline
spotsnagger campsites --yaml-config example_search.yaml
```

!!! note

    A JSON Schema for the YAML configuration file can be found at
    [docs/yaml_search.json](yaml_search.json)

### Saving the Results of a Search

In some cases, you might want to save all the campsites found during one
search and load them into a new search, so you don't receive duplicate notifications.
This can be achieved by passing the `--offline-search` flag. By default, spotsnagger will save
the results in a file called `spotsnagger_campsites.json`.

Alternatively, you can also path the `--offline-search-path` flag to specify a certain file
path to save the results as. When a file path with a `.json` extension is passed
spotsnagger will export the results as a JSON file. When the `.pkl` or `.pickle` extension is
used, spotsnagger will use a serialized Pickle file.

```commandline
spotsnagger \
  campsites \
  --rec-area 14 \
  --campground -2147483643 \
  --start-date 2023-09-01 \
  --end-date 2023-10-01 \
  --continuous \
  --offline-search
```

```commandline
spotsnagger \
  campsites \
  --rec-area 14 \
  --campground -2147483643 \
  --start-date 2023-09-01 \
  --end-date 2023-10-01 \
  --continuous \
  --offline-search-path campsites.pkl
```

### Search for Recreation Areas by Query String

Just need to find what your Recreation Area ID number is? This simple command allows you to
search and list recreation areas. It accepts a `--search` argument.

```commandline
spotsnagger recreation-areas --search "BC Parks"
```

### Look for Specific Campgrounds Within a Recreation Area

Need to get even more specific and search for a particular campground? This search lists campgrounds
attached to a recreation area id `--rec-area`. It also accepts a `--search` argument.

```commandline
spotsnagger campgrounds --rec-area 14 --search "Banff"
```

### Run spotsnagger as a CRON Job

In some instances you don't want to run spotsnagger as a continuous, blocking Python
process. Instead you might want to run spotsnagger as a CRON job that checks for a campsite
every 30 minutes (**`*/30 * * * *`**). In this case you would use the `--search-once` option
which enables continuous searching functionality (like sending notifications) without
actually searching continuously.

Make sure to save your search results offline if running spotsnagger as a CRON job, this allows
spotsnagger to save any campsites it finds between searches so that it only sends you a notification once:

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-07-10 \
    --end-date 2023-07-18 \
    --notifications email \
    --search-once \
    --offline-search
```

### Send a webhook notification

SpotSnagger supports sending notifications to a webhook URL.
This can be useful if you want to integrate spotsnagger with
services that accept webhooks, like [IFTTT](https://ifttt.com/).

Webhook notifications require the `WEBHOOK_URL` environment variable /
config value to be set. Optionally, you can also set the `WEBHOOK_HEADERS`
config value to a JSON object containing any headers you want to send with
the webhook POST request.

```commandline
export WEBHOOK_URL="https://webhook.site/api/webhook"
export WEBHOOK_HEADERS='{"Authorization": "Bearer 1234"}'
```

Unless explicitly set otherwise, `WEBHOOK_HEADERS` will have
`Content-Type: application/json` set.

```commandline
spotsnagger campsites \
    --rec-area 14 \
    --campground -2147483643 \
    --start-date 2023-09-10 \
    --end-date 2023-09-13 \
    --notifications webhook
```

The JSON POST body is an array of available campsites
under a `campsites` key.

```json
{
    "campsites": [
        {
            "campsite_id": -2147475532,
            "booking_date": "2023-09-12T00:00:00",
            "booking_end_date": "2023-09-13T00:00:00",
            "booking_nights": 1,
            "campsite_site_name": "B12",
            "campsite_loop_name": "Unknown",
            "campsite_type": "Unknown",
            "campsite_occupancy": [1, 6],
            "campsite_use_type": "N/A",
            "availability_status": "Available",
            "recreation_area": "Parks Canada",
            "recreation_area_id": 14,
            "facility_name": "Banff - Two Jack Lakeside",
            "facility_id": -2147483643,
            "booking_url": "https://reservation.pc.gc.ca/create-booking/results?...",
            "permitted_equipment": null,
            "campsite_attributes": null
        }
    ],
    "timestamp": "2023-09-10T01:57:00.729918+00:00"
}
```
