"""
Going to Camp Providers
"""

from spotsnagger.containers import RecreationArea

# Map going to camp subdomains to RecreationAreas
RECREATION_AREAS = {
    "longpoint.goingtocamp.com": RecreationArea(
        recreation_area="Long Point Region",
        recreation_area_id=1,
        recreation_area_location="Ontario, CA",
    ),
    "stclair.goingtocamp.com": RecreationArea(
        recreation_area="St. Clair Region",
        recreation_area_id=2,
        recreation_area_location="Ontario, CA",
    ),
    "maitlandvalley.goingtocamp.com": RecreationArea(
        recreation_area="Maitland Valley",
        recreation_area_id=4,
        recreation_area_location="Ontario, CA",
    ),
    "saugeen.goingtocamp.com": RecreationArea(
        recreation_area="Saugeen Valley",
        recreation_area_id=5,
        recreation_area_location="Ontario, CA",
    ),
    "ahtrails.ca": RecreationArea(
        recreation_area="Algonquin Highlands",
        recreation_area_id=8,
        recreation_area_location="Ontario, CA",
    ),
    "reservations.ncc-ccn.gc.ca": RecreationArea(
        recreation_area="Gatineau Park",
        recreation_area_id=10,
        recreation_area_location="Ottawa-Gatineau, Ontario-Quebec, CA",
    ),
    "nlcamping.ca": RecreationArea(
        recreation_area="Newfoundland & Labrador Provincial Parks",
        recreation_area_id=11,
        recreation_area_location="Newfoundland and Labrador, CA",
    ),
    "camping.bcparks.ca": RecreationArea(
        recreation_area="BC Parks",
        recreation_area_id=12,
        recreation_area_location="British Columbia, CA",
    ),
    "novascotia.goingtocamp.com": RecreationArea(
        recreation_area="Nova Scotia Parks",
        recreation_area_id=13,
        recreation_area_location="Nova Scotia, CA",
    ),
    "reservation.pc.gc.ca": RecreationArea(
        recreation_area="Parks Canada",
        recreation_area_id=14,
        recreation_area_location="CA",
    ),
    "manitoba.goingtocamp.com": RecreationArea(
        recreation_area="Manitoba Parks",
        recreation_area_id=15,
        recreation_area_location="Manitoba, CA",
    ),
    "parcsnbparks.ca": RecreationArea(
        recreation_area="New Brunswick Provincial Parks",
        recreation_area_id=16,
        recreation_area_location="New Brunswick, CA",
    ),
}
