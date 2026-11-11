# Providers

spotsnagger works with two providers, **`GoingToCamp`** and **`Aspira`**. A "provider" is an
Online Booking Service that lists camping and recreation inventory. `GoingToCamp` is the
default, so you only need to pass **`--provider Aspira`** for Aspira parks.

## GoingToCamp

![](_static/goingtocamp_logo.png){: .center}

[GoingToCamp](https://goingtocamp.com/) provides campground listing and booking services for
Parks Canada and several Canadian provincial and regional park systems.

To get a listing of GoingToCamp recreation areas, and their IDs, run the following command:

```shell
spotsnagger recreation-areas
```

When using GoingToCamp you must restrict campground and campsite searches to a single
recreation area. Since recreation areas may list every campground in a provincial park system,
it feels natural to filter searches by recreation area. Campsite searches also need at least
one **`--campground`** ID.

Currently, the following recreation areas are supported:

| ID  | Recreation Area                          | Province                  | Website                                                                   |
| --- | ---------------------------------------- | ------------------------- | ------------------------------------------------------------------------- |
| 1   | Long Point Region                        | Ontario                   | [longpoint.goingtocamp.com](https://longpoint.goingtocamp.com)            |
| 2   | St. Clair Region                         | Ontario                   | [stclair.goingtocamp.com](https://stclair.goingtocamp.com)                |
| 4   | Maitland Valley                          | Ontario                   | [maitlandvalley.goingtocamp.com](https://maitlandvalley.goingtocamp.com)  |
| 5   | Saugeen Valley                           | Ontario                   | [saugeen.goingtocamp.com](https://saugeen.goingtocamp.com)                |
| 8   | Algonquin Highlands                      | Ontario                   | [ahtrails.ca](https://ahtrails.ca)                                        |
| 10  | Gatineau Park                            | Ontario-Quebec            | [reservations.ncc-ccn.gc.ca](https://reservations.ncc-ccn.gc.ca)          |
| 11  | Newfoundland & Labrador Provincial Parks | Newfoundland and Labrador | [nlcamping.ca](https://nlcamping.ca)                                      |
| 12  | BC Parks                                 | British Columbia          | [camping.bcparks.ca](https://camping.bcparks.ca)                          |
| 13  | Nova Scotia Parks                        | Nova Scotia               | [novascotia.goingtocamp.com](https://novascotia.goingtocamp.com)          |
| 14  | Parks Canada                             | Canada National Parks     | [reservation.pc.gc.ca](https://reservation.pc.gc.ca/)                     |
| 15  | Manitoba Parks                           | Manitoba                  | [manitoba.goingtocamp.com](https://manitoba.goingtocamp.com)              |
| 16  | New Brunswick Provincial Parks           | New Brunswick             | [parcsnbparks.info](https://parcsnbparks.info/)                           |

Check out the following documentation examples for more details on searching GoingToCamp recreation areas:

- [Searching for a Campsite](command_line_usage.md#searching-for-a-campsite)
- [Searching Using Equipment](command_line_usage.md#searching-using-equipment)

## Aspira

Alberta, Prince Edward Island and Saskatchewan provincial parks book through Aspira's
ReserveAmerica sites, a different system from GoingToCamp.

| ID  | Recreation Area                       | Province             | Website                                                        |
| --- | ------------------------------------- | -------------------- | -------------------------------------------------------------- |
| 1   | Alberta Parks                         | Alberta              | [shop.albertaparks.ca](https://shop.albertaparks.ca)           |
| 2   | Prince Edward Island Provincial Parks | Prince Edward Island | [www.peiprovincialparks.ca](https://www.peiprovincialparks.ca) |
| 3   | Saskatchewan Provincial Parks         | Saskatchewan         | [parks.saskatchewan.ca](https://parks.saskatchewan.ca)         |

```shell
spotsnagger campgrounds --provider Aspira --rec-area 3
spotsnagger campsites --provider Aspira --rec-area 3 --campground 290125     --start-date 2026-11-24 --end-date 2026-11-27
```

`--booking-category` picks what to search: `0` Camping (default), `1` Day Use or `2`
Backcountry Camping permits, where the province offers it (PEI is camping only). Each
category has its own campgrounds, so pass the same `--booking-category` to
`spotsnagger campgrounds`:

```shell
spotsnagger campgrounds --provider Aspira --rec-area 1 --booking-category 2
spotsnagger campsites --provider Aspira --rec-area 1 --booking-category 2 --campground 331053 --start-date 2027-07-10 --end-date 2027-07-12
```

A backcountry campground matches only when a permit is available for every night of the
stay.

These sites sit behind a waiting-room queue; spotsnagger waits for it to redirect back to the
site. Because of the queue, Aspira parks can only be searched once: `--continuous` and
`--search-forever` aren't supported, and notifications need `--search-once` (a YAML
search needs `continuous: false` or `search_once: true`).
