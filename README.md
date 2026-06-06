# dataops-gtfs-rt-trip-updates

## download
https://gocarta.s3.us-east-2.amazonaws.com/public/gtfs-rt/TripUpdates.pb

## frequency
The pipeline runs approximately every 5 seconds on a cloud server.

## columns
| column | example | description |
| :--- | :--- | :--- |
| **service_id** | `2` | Which type of service (e.g., weekday, Saturday, or Sunday) |
| **route_id** | `"1"` | Route ID |
| **trip_id** | `"768020"` | Trip ID |
| **direction_id** | `0` | Direction ID |
| **stop_headsign** | `1 ALTON PARK 38TH STREET` | Direction ID |
| **trip_start_time** | `"15:56:00"` | what time the trip started |
| **stop_id** | `"2162"` | Stop ID |
| **stop_code** | `"2941"` | Stop Code (this is what Clever uses) |
| **stop_name** | `"Market & First Horizon Bank (7th)"` | Stop Name |
| **stop_sequence** | `"28"` | Stop sequence in Trip in GTFS |
| **stop_sequence_actual** | `"28"` | Actual stop sequence after factoring in skipped stops in GTFS |
| **schedule_relationship** | `"scheduled"` | Only displaying scheduled trips at the moment |
| **vehicle_id** | `"173"` | Vehicle ID |
| **scheduled_arrival_time** | `"16:06:05"` | When the vehicle should arrive at this stop according to the static GTFS file |
| **scheduled_departure_time** | `"16:06:05"` | When the vehicle should leave from this stop according to the static GTFS file |
| **predicted_arrival_time** | `"16:06:05"` | When the vehicle should arrive at this stop according to realtime system |
| **predicted_departure_time** | `"16:06:05"` | When the vehicle should leave from this stop according to the realtime system |
| **latitude** | `35.048171` | Latitude |
| **longitude** | `-85.309494` | Longitude |

## download links
- [metadata](https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/meta.json)
- [csv](https://gocarta.s3.us-east-2.amazonaws.com/public/data/v/v1/data.csv)
- [geojson](https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.points.geojson)
- [geoparquet](https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.parquet)
- [gtfs](https://gocarta.s3.us-east-2.amazonaws.com/public/gtfs-rt/TripUpdates.pb)
- [json](https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.json)
- [json lines](https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.jsonl)
- [shapefile](https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.points.shp.zip)

## preview links
- You can view the geojson on a map using [geojson.io](https://geojson.io/#data=data:text/x-url,https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.points.geojson).
- You can view the shapefile on a map using [shapefile.io](https://shapefile.io?url=https://gocarta.s3.us-east-2.amazonaws.com/public/data/gtfsrt_trip_updates/v1/data.points.shp.zip).
- You can query the data with SQL using [duckdb](https://shell.duckdb.org/#queries=v0,CREATE-TABLE-dataset-AS-SELECT-*-FROM-'s3://gocarta/public/data/gtfsrt_trip_updates/v1/data.parquet'~,Describe-dataset~).

## support
Post an issue [here](https://github.com/gocarta/dataops-gtfs-rt-trip-updates/issues) or email the package author at DanielDufour@gocarta.org.
