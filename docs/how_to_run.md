# How to Run SpotSnagger

## Run Modes

### non-continuous

spotsnagger's default run-mode is **"non-continuous"**. This means that spotsnagger runs a search with your custom
campsite query once. Once this search is complete spotsnagger will exit whether it found any matching campsites or not.
[\*\*example](command_line_usage.md#searching-for-a-campsite)

### continuous

Second, spotsnagger has a **"continuous"** mode. Differently from the "non-continuous" mode, spotsnagger will continue
to search until it finds at least one matching campsite. spotsnagger sleeps in between searches so we don't overload
our friends who run the camping APIs. [\*\*example](command_line_usage.md#continuously-searching-for-a-campsite)

!!! note

    This mode is enabled when any of the following options are provided:
    **`--continuous`**, **`--notifications`**, **`--search-forever`**,
    **`--polling-interval`**, **`--notify-first-try`**.

!!! important

    When you run spotsnagger in **"continuous"** or **"search-forever"** mode it needs to run as a continuous
    Python process in your terminal. This means that you need an always-on computer to run your search.

    A small computing device like a Raspberry Pi is perfect for something like this. If you're looking to
    achieve this with a device like a laptop, make sure you've prevented the computer from sleeping.

### search-forever

Third, spotsnagger has its **"search-forever"** mode. This is slightly different from the "continuous" mode because it will
continue to run even after it's found its first matching campsite. spotsnagger remembers which campsites it's found
before and won't notify you for the same campsite twice.
[\*\*example](command_line_usage.md#continue-looking-after-the-first-match-is-found)

!!! note

    This mode is enabled with the **`--search-forever`** option.

### search-once

Lastly, spotsnagger has its **"search-once"** mode. This enables some features of continuous searching, like the
ability to send notifications, but without actually running continuously. This is useful if you're
interested in running spotsnagger as a CRON job instead of as a blocking python process.
[\*\*example](command_line_usage.md#run-spotsnagger-as-a-cron-job)

!!! note

    This mode is enabled with the **`--search-once`** option.

## Running in Docker

Docker is a great solution to run spotsnagger wherever you are. There is an official docker image published alongside
spotsnagger's PyPI distribution that makes running spotsnagger in the background as a detached container really easy.

```shell
docker pull juftin/camply
```

Here's an example of a detached container searching in the background (notice the `-d` flag, the
container will run detached).

```commandline
docker run --rm -d \
  --name spotsnagger-detached-example \
  --env PUSHOVER_PUSH_TOKEN=${PUSHOVER_PUSH_TOKEN} \
  --env PUSHOVER_PUSH_USER=${PUSHOVER_PUSH_USER} \
  --env TZ="America/Denver" \
  juftin/camply \
  spotsnagger campsites \
      --rec-area 14 \
      --campground -2147483643 \
      --start-date 2023-08-01 \
      --end-date 2023-09-01 \
      --search-forever \
      --notifications pushover
```

See the [Environment Variables](#environment-variables) section for a list of environment variables spotsnagger uses.
Alternatively, if you have already run `spotsnagger configure` locally, you can share
your [`.spotsnagger`](examples/example.spotsnagger) file inside the docker container.

```commandline
docker run --rm \
  --name spotsnagger-file-share-example \
  --env TZ="America/Denver" \
  --volume ${HOME}/.spotsnagger:/home/spotsnagger/.spotsnagger \
  juftin/camply \
  spotsnagger campsites \
      --rec-area 14 \
      --campground -2147483643 \
      --start-date 2023-07-22 \
      --end-date 2023-07-27 \
      --search-forever \
      --notifications email
```

To manage multiple searches (with different notification preferences) I like to use YAML
configuration files:

```commandline
docker run --rm -d \
  --name spotsnagger-email-example \
  --env TZ="America/Denver" \
  --env EMAIL_TO_ADDRESS=${EMAIL_TO_ADDRESS} \
  --env EMAIL_USERNAME=${EMAIL_USERNAME} \
  --env EMAIL_PASSWORD=${EMAIL_PASSWORD} \
  --volume example_search.yaml:/home/spotsnagger/example_search.yaml \
  juftin/camply:latest \
  spotsnagger campsites \
      --yaml-config /home/spotsnagger/example_search.yaml
```

A [docker-compose example](examples/docker-compose.yaml) of the above YAML Config is also
available.

### Environment Variables

- Pushover Notifications
    - `PUSHOVER_PUSH_USER`
- Apprise Notifications
    - `APPRISE_URL`
- Email Notifications
    - `EMAIL_TO_ADDRESS`
    - `EMAIL_USERNAME`
    - `EMAIL_PASSWORD`
    - `EMAIL_FROM_ADDRESS` (defaults to "spotsnagger@juftin.com")
    - `EMAIL_SUBJECT_LINE` (defaults to "spotsnagger Notification")
    - `EMAIL_SMTP_SERVER` (defaults to "smtp.gmail.com")
    - `EMAIL_SMTP_PORT` (defaults to 465)
- Ntfy Notifications
    - `NTFY_TOPIC`
- Pushbullet Notifications
    - `PUSHBULLET_API_TOKEN`
- Twilio Notifications
    - `TWILIO_ACCOUNT_SID`
    - `TWILIO_AUTH_TOKEN`
    - `TWILIO_SOURCE_NUMBER`
    - `TWILIO_DEST_NUMBERS`
- Slack Notifications
    - `SLACK_WEBHOOK`
- Telegram Notifications
    - `TELEGRAM_BOT_TOKEN`
    - `TELEGRAM_CHAT_ID`
- Webhook Notifications
    - `WEBHOOK_URL`
    - `WEBHOOK_HEADERS` (optional, defaults to `{"Content-Type": "application/json"}`)
- Optional Environment Variables
    - `LOG_LEVEL` (sets logging level, defaults to "INFO")
    - `PUSHOVER_PUSH_TOKEN` (Personal Pushover App Token)
    - `TZ` ([TZ Database Name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for
      logging, defaults to UTC)
