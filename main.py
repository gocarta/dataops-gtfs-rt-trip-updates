# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "boto3",
#     "datablob",
#     "gtfs-realtime-bindings",
#     "simple-env",
#     "tzdata",
# ]
# ///
import boto3
from collections import defaultdict
import datablob
import datetime
from google.transit import gtfs_realtime_pb2
import simple_env as se
from time import sleep
from zoneinfo import ZoneInfo

AWS_BUCKET_NAME = se.get("AWS_BUCKET_NAME")
if not AWS_BUCKET_NAME:
    raise Exception("[gtfs-rt-vehicle-positions] missing AWS_BUCKET_NAME")

AWS_BUCKET_PATH = se.get("AWS_BUCKET_PATH")
if not AWS_BUCKET_PATH:
    raise Exception("[gtfs-rt-vehicle-positions] missing AWS_BUCKET_PATH")

AWS_REGION = se.get("AWS_REGION")
if not AWS_REGION:
    raise Exception("[gtfs-rt-vehicle-positions] missing AWS_REGION")

GTFS_TIMEZONE = se.get("GTFS_TIMEZONE")
if not GTFS_TIMEZONE:
    raise Exception("[gtfs-rt-vehicle-positions] missing GTFS_TIMEZONE")

GTFS_UPDATE_FREQUENCY = se.get("GTFS_UPDATE_FREQUENCY")
if not GTFS_UPDATE_FREQUENCY:
    raise Exception("[gtfs-rt-vehicle-positions] missing GTFS_UPDATE_FREQUENCY")


def find_sublist(lst, sublst):
    matches = []
    n = len(lst)
    m = len(sublst)
    for i in range(n - m + 1):
        if lst[i : i + m] == sublst:
            matches.append(i)
    if len(matches) == 0:
        print("lst:", lst)
        print("sublst:", sublst)
        raise Exception("[find_sublist] sublist not found")
    elif len(matches) >= 2:
        print("lst:", lst)
        print("sublst:", sublst)
        raise Exception("[find_sublist] sublist found multiple times in list")

    return matches[0]


def hms(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


client = datablob.DataBlobClient(
    bucket_name=AWS_BUCKET_NAME, bucket_path=AWS_BUCKET_PATH
)

scheduled_service_dates = client.get_dataset_as_json(
    name="scheduled_service_dates", version="1"
)

# currently, CARTA doesn't have multiple service ids on the same date
service_id_by_date = dict(
    [(row["date"], row["service_id"]) for row in scheduled_service_dates]
)
# { '20260515': '1', '20260516': '3', '20260517': '2', ... }

scheduled_bus_trips = client.get_dataset_as_json(
    name="scheduled_bus_trips", version="1"
)

scheduled_stop_times = client.get_dataset_as_json(
    name="scheduled_stop_times", version="1"
)

trips_lookup = {}
stop_times_lookup = {}

for trip in scheduled_bus_trips:
    route_id = trip["route_id"]
    gtfs_headsign = trip["headsign"]
    gtfs_service_id = trip["service_id"]
    start_hours, start_minutes, start_seconds = trip["start_time"].split(":")
    start_time = (
        int(start_hours) * 60 * 60 + int(start_minutes) * 60 + int(start_seconds)
    )
    key = (gtfs_service_id, route_id, gtfs_headsign, start_time)
    trips_lookup[key] = trip

gtfs_trip_stop_sequence = defaultdict(list)
for stop_time in scheduled_stop_times:
    trip_id = str(stop_time["trip_id"])

    # we use stop_sequence_actual not stop_sequence because sometimes stop_sequence will jump, like going from 52 to 54 and skipping 53
    gtfs_trip_stop_sequence[trip_id].append(
        (
            stop_time["stop_name"],
            stop_time["stop_sequence_actual"],
            stop_time["stop_arrival_time"],
        )
    )

for key in gtfs_trip_stop_sequence:
    # make we resort the stops by stop_sequence_actual just in case they aren't in order in the scheduled_stop_times dataset
    gtfs_trip_stop_sequence[key].sort(key=lambda it: it[1])

    gtfs_trip_stop_sequence[key] = [
        name for name, seq, arrival_time in gtfs_trip_stop_sequence[key]
    ]

for stop_time in scheduled_stop_times:
    trip_id = str(stop_time["trip_id"])
    stop_name = stop_time["stop_name"]
    key = (trip_id, stop_name)
    stop_times_lookup[key] = stop_time

for stop_time in scheduled_stop_times:
    trip_id = str(stop_time["trip_id"])
    stop_name = stop_time["stop_name"]
    stop_sequence = stop_time["stop_sequence_actual"] - 1  # make it zero-indexed
    stop_code = str(stop_time["stop_code"])
    key = (trip_id, stop_code, stop_sequence)
    stop_times_lookup[key] = stop_time

i = 0

while True:
    matched = 0

    i += 1

    if i > 1:
        print(f"[gtfs-rt-trip-updates] sleeping {GTFS_UPDATE_FREQUENCY} seconds")
        sleep(GTFS_UPDATE_FREQUENCY)

    feed = gtfs_realtime_pb2.FeedMessage()

    now_datetime = datetime.datetime.now(ZoneInfo(GTFS_TIMEZONE))
    timestamp = int(now_datetime.timestamp())

    # feed header
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.incrementality = gtfs_realtime_pb2.FeedHeader.FULL_DATASET
    feed.header.timestamp = timestamp

    clever_predictions = client.get_dataset_as_json(
        name="clever_predictions", version="1"
    )

    results = []

    # group stop predictions by the transit agency trip id (an id that is internal to Clever)
    clever_predictions_by_tatripid_and_vid = defaultdict(list)
    for row in clever_predictions:
        clever_predictions_by_tatripid_and_vid[row["tatripid"], row["vid"]].append(row)

    for (
        tatrip,
        vid,
    ), clever_stop_predictions in clever_predictions_by_tatripid_and_vid.items():
        # sorting by distance from stop
        # this is distance along the route, not "as the crow flies" distance
        clever_stop_predictions.sort(key=lambda x: x["dstp"])

        # list of stop names in order like
        # ['MARKET + CHOO CHOO', 'MARKET + MAIN', 'MARKET + 17TH', 'MARKET + 19TH', ...]
        clever_stop_sequence = [it["stpnm"] for it in clever_stop_predictions]

        entity = feed.entity.add()

        clever_stop_predictions_0 = clever_stop_predictions[0]

        route_id = clever_stop_predictions_0["rt"]
        route_direction = clever_stop_predictions_0["rtdir"]
        destination = clever_stop_predictions_0["des"]
        trip_start_time = clever_stop_predictions_0["stst"]
        trip_start_date = clever_stop_predictions_0["stsd"]  # "2026-05-25"
        tmstmp = clever_stop_predictions_0["tmstmp"]  # "20260527 19:08"

        # "2026-05-25" -> "20260525"
        service_dates_lookup = trip_start_date.replace("-", "")

        # in theory, could have multiple service ids on the same date
        # but we don't do that are CARTA
        service_id = service_id_by_date[service_dates_lookup]

        trip_lookup_key = (service_id, route_id, destination, trip_start_time)

        trip_update = entity.trip_update

        tmstmp = datetime.datetime.strptime(tmstmp, "%Y%m%d %H:%M")
        tmstmp = tmstmp.replace(tzinfo=ZoneInfo(GTFS_TIMEZONE))
        trip_update.timestamp = int(tmstmp.timestamp())

        trip_update.vehicle.id = vid

        # don't currently use disruption management, so all trips are treated as scheduled
        trip_update.trip.schedule_relationship = (
            gtfs_realtime_pb2.TripDescriptor.SCHEDULED
        )

        if trip_lookup_key in trips_lookup:
            gtfs_scheduled_trip = trips_lookup[trip_lookup_key]
            gtfs_trip_id = gtfs_scheduled_trip["trip_id"]
            gtfs_stop_sequence = gtfs_trip_stop_sequence[gtfs_trip_id]
            trip_update.trip.trip_id = gtfs_trip_id
            trip_update.trip.direction_id = int(gtfs_scheduled_trip["direction_id"])
        else:
            gtfs_scheduled_trip = None
            gtfs_trip_id = None
            gtfs_stop_sequence = None
            trip_update.trip_id = tatrip
            trip_update.trip.direction_id = route_direction
            raise Exception("unfound gtfs match")

        entity.id = gtfs_trip_id

        if len(clever_stop_sequence) > len(gtfs_stop_sequence):
            print("[gtfs-rt-trip-updates] route_id:", route_id)
            print(
                "[gtfs-rt-trip-updates] number of clever stop predictions:",
                len(clever_stop_predictions),
            )
            print(
                "[gtfs-rt-trip-updates] number of stops in gtfs:",
                gtfs_scheduled_trip["stop_count"],
            )
            raise Exception(
                "[gtfs-rt-trip-updated] there are more stops in clever_stop_sequence than in gtfs_stop_sequence!"
            )
        stop_sequence_offset = find_sublist(gtfs_stop_sequence, clever_stop_sequence)

        trip_update.trip.route_id = route_id
        trip_update.trip.start_time = hms(trip_start_time)  # convert 38940 to 10:49:00

        for i, clever_stop_time in enumerate(clever_stop_predictions):
            stu = trip_update.stop_time_update.add()

            stu.schedule_relationship = (
                gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.SCHEDULED
            )

            clever_stop_name = clever_stop_time["stpnm"]
            clever_stop_id = clever_stop_time["stpid"]

            stop_sequence = stop_sequence_offset + i

            stop_time_lookup_key = (gtfs_trip_id, str(clever_stop_id), stop_sequence)

            if stop_time_lookup_key in stop_times_lookup:
                gtfs_stop_time = stop_times_lookup[stop_time_lookup_key]
                matched += 1
            else:
                print(
                    "[gtfs-rt-trip-updates] stop_time_lookup_key:", stop_time_lookup_key
                )
                print("[gtfs-rt-trip-updates] clever_stop_name:", clever_stop_name)
                print(
                    "[gtfs-rt-trip-updates] stop_sequence_offset:", stop_sequence_offset
                )
                print("[gtfs-rt-trip-updates] gtfs_stop_sequence:", gtfs_stop_sequence)
                print(
                    "[gtfs-rt-trip-updates] clever_stop_sequence:", clever_stop_sequence
                )
                raise Exception(
                    "[gtfs-rt-trip-updates] unmatched:", stop_time_lookup_key
                )

            gtfs_stop_id = gtfs_stop_time["stop_id"]

            # e.g., "20260527 19:29"
            prdtm = clever_stop_time["prdtm"]
            prdtm = datetime.datetime.strptime(prdtm, "%Y%m%d %H:%M")
            prdtm = prdtm.replace(tzinfo=ZoneInfo(GTFS_TIMEZONE))
            prdtm_ts = int(prdtm.timestamp())
            stu.arrival.time = prdtm_ts
            stu.departure.time = prdtm_ts

            stu.stop_id = str(gtfs_stop_id)

            row = {
                "service_id": service_id,
                "route_id": route_id,
                "trip_id": gtfs_stop_time["trip_id"],
                "direction_id": gtfs_stop_time["direction_id"],
                "stop_headsign": gtfs_stop_time["stop_headsign"],
                "trip_start_time": gtfs_stop_time["trip_start_time"],
                "stop_id": gtfs_stop_id,
                "stop_code": gtfs_stop_time["stop_code"],
                "stop_name": gtfs_stop_time["stop_name"],
                "stop_sequence": gtfs_stop_time["stop_sequence"],
                "stop_sequence_actual": gtfs_stop_time["stop_sequence_actual"],
                "schedule_relationship": "scheduled",
                "vehicle_id": vid,
                "scheduled_arrival_time": gtfs_stop_time["stop_arrival_time"],
                "scheduled_departure_time": gtfs_stop_time["stop_departure_time"],
                "predicted_arrival_time": prdtm.isoformat(),
                "predicted_departure_time": prdtm.isoformat(),
                "latitude": gtfs_stop_time["latitude"],
                "longitude": gtfs_stop_time["longitude"],
            }
            results.append(row)

    print("[gtfs-rt-trip-updates] matched:", matched)

    result = feed.SerializeToString()

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket="gocarta",
        Key="public/gtfs-rt/TripUpdates.pb",
        Body=result,
        ContentType="application/x-protobuf",
        # Adding CacheControl prevents clients from seeing stale bus locations
        CacheControl="max-age=0, no-cache, no-store, must-revalidate",
    )

    print(f"[gtfs-rt-trip-updates] updated GTFS Realtime feed")

    client.update_dataset(
        name="gtfsrt_trip_updates",
        description="GTFS Realtime Trip Updates.  The predicted arrival times for stops with additional information like location and headsign.",
        version="1",
        data=results,
        column_names=[
            "service_id",
            "route_id",
            "trip_id",
            "direction_id",
            "stop_headsign",
            "trip_start_time",
            "stop_id",
            "stop_code",
            "stop_name",
            "stop_sequence",
            "stop_sequence_actual",
            "schedule_relationship",
            "vehicle_id",
            "scheduled_arrival_time",
            "scheduled_departure_time",
            "predicted_arrival_time",
            "predicted_departure_time",
            "latitude",
            "longitude",
        ],
        latitude_key="latitude",
        longitude_key="longitude",
    )
    print("[dataops-gtfsrt-trip-updates] updated dataset")
