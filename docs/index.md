# spotsnagger

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

[![PyPI](https://img.shields.io/pypi/v/camply?color=blue&label=camply)](https://github.com/juftin/camply)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/camply)](https://pypi.python.org/pypi/camply/)
[![Docker Image Version](https://img.shields.io/docker/v/juftin/camply?color=blue&label=docker&logo=docker)](https://hub.docker.com/r/juftin/camply)
[![Testing Status](https://github.com/juftin/camply/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/juftin/camply/actions/workflows/test.yaml)
[![GitHub License](https://img.shields.io/github/license/juftin/camply?color=blue&label=License)](https://github.com/juftin/camply/blob/main/LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-lightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)
[![semantic-release](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--release-e10079.svg)](https://github.com/semantic-release/semantic-release)
[![Discord Chat](https://img.shields.io/static/v1?label=chat&message=discord&color=blue&logo=discord)](https://discord.gg/qZDr78kKvB)

## Table of Contents

- [Installation](installation.md)
    - [PyPI](installation.md#pypi)
    - [Docker](installation.md#docker)
- [Providers](providers.md)
    - [GoingToCamp](providers.md#goingtocamp)
- [Command Line Usage](command_line_usage.md)
    - [Simple Examples](command_line_usage.md#simple-examples)
    - [providers](command_line_usage.md#providers)
    - [campsites](command_line_usage.md#campsites)
    - [recreation-areas](command_line_usage.md#recreation-areas)
    - [campgrounds](command_line_usage.md#campgrounds)
    - [configure](command_line_usage.md#configure)
    - [test-notifications](command_line_usage.md#test-notifications)
    - [tui](command_line_usage.md#tui)
    - [Examples](command_line_usage.md#examples)
        - [Finding Campground IDs](command_line_usage.md#finding-campground-ids)
        - [Searching for a Campsite](command_line_usage.md#searching-for-a-campsite)
        - [Searching for a Specific Campsite by ID](command_line_usage.md#searching-for-a-specific-campsite-by-id)
        - [Continuously Searching for A Campsite](command_line_usage.md#continuously-searching-for-a-campsite)
        - [Searching Across Multiple Time Windows](command_line_usage.md#searching-across-multiple-time-windows)
        - [Continue Looking After The First Match Is Found](command_line_usage.md#continue-looking-after-the-first-match-is-found)
        - [Send a Push Notification](command_line_usage.md#send-a-push-notification)
        - [Send a Text Message](command_line_usage.md#send-a-text-message)
        - [Send a Notification to Different Services](command_line_usage.md#send-a-notification-to-different-services)
        - [Searching for Specific Weekdays](command_line_usage.md#searching-for-specific-weekdays)
        - [Send a Notification Using Apprise-Compatible Services](command_line_usage.md#send-a-notification-using-apprise-compatible-services)
        - [Look for Weekend Campsite Availabilities](command_line_usage.md#look-for-weekend-campsite-availabilities)
        - [Look for Consecutive Nights at the Same Campsite](command_line_usage.md#look-for-consecutive-nights-at-the-same-campsite)
        - [Searching Using Equipment](command_line_usage.md#searching-using-equipment)
        - [Using a YAML Configuration file to search for campsites](command_line_usage.md#using-a-yaml-configuration-file-to-search-for-campsites)
        - [Saving the Results of a Search](command_line_usage.md#saving-the-results-of-a-search)
        - [Search for Recreation Areas by Query String](command_line_usage.md#search-for-recreation-areas-by-query-string)
        - [Look for Specific Campgrounds Within a Recreation Area](command_line_usage.md#look-for-specific-campgrounds-within-a-recreation-area)
        - [Run spotsnagger as a CRON Job](command_line_usage.md#run-spotsnagger-as-a-cron-job)
        - [Send a Webhook Notification](command_line_usage.md#send-a-webhook-notification)
- [How to Run SpotSnagger](how_to_run.md#how-to-run-spotsnagger)
    - [Run Modes](how_to_run.md#run-modes)
        - [non-continuous](how_to_run.md#non-continuous)
        - [continuous](how_to_run.md#continuous)
        - [search-forever](how_to_run.md#search-forever)
        - [search-once](how_to_run.md#search-once)
    - [Running in Docker](how_to_run.md#running-in-docker)
        - [Environment Variables](how_to_run.md#environment-variables)
- [Object-Oriented Usage (Python)](python.md)
    - [Search for a GoingToCamp Campsite](python.md#search-for-a-goingtocamp-campsite)
    - [Continuously Search for GoingToCamp Campsites](python.md#continuously-search-for-goingtocamp-campsites)
- [Dependencies](dependencies.md)

---

---

<br/>

[<p align="center" ><img src="https://raw.githubusercontent.com/juftin/juftin/main/static/juftin.png" width="120" height="120"  alt="juftin logo"> </p>](https://github.com/juftin)
