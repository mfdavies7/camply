# Object-Oriented Usage (Python)

## Search for a GoingToCamp Campsite

```python
from datetime import datetime
import logging
from typing import List

from spotsnagger.containers import AvailableCampsite, SearchWindow
from spotsnagger.search import SearchGoingToCamp

logging.basicConfig(format="%(asctime)s [%(levelname)8s]: %(message)s",
                    level=logging.INFO)

month_of_july = SearchWindow(start_date=datetime(year=2023, month=7, day=1),
                             end_date=datetime(year=2023, month=7, day=31))
camping_finder = SearchGoingToCamp(search_window=month_of_july,
                                   recreation_area=14,  # Parks Canada
                                   campgrounds=[-2147483643],  # Banff - Two Jack Lakeside
                                   weekends_only=False,
                                   nights=1)
matches: List[AvailableCampsite] = camping_finder.get_matching_campsites(log=True, verbose=True,
                                                                         continuous=False)
```

The above script returns a list of any matching `AvailableCampsite` pydantic objects.

## Continuously Search for GoingToCamp Campsites

You'll notice that the `get_matching_campsites` function accepts parameter values very similar
to the commandline arguments.

```python
from datetime import datetime
import logging

from spotsnagger.containers import SearchWindow
from spotsnagger.search import SearchGoingToCamp

logging.basicConfig(format="%(asctime)s [%(levelname)8s]: %(message)s",
                    level=logging.INFO)

month_of_july = SearchWindow(start_date=datetime(year=2023, month=7, day=1),
                             end_date=datetime(year=2023, month=7, day=31))
camping_finder = SearchGoingToCamp(search_window=month_of_july,
                                   recreation_area=14,  # Parks Canada
                                   campgrounds=[-2147483643],
                                   weekends_only=False,
                                   nights=3)
camping_finder.get_matching_campsites(log=True, verbose=True,
                                      continuous=True,
                                      polling_interval=5,
                                      notification_provider="pushover",
                                      search_forever=True,
                                      notify_first_try=False)
```
