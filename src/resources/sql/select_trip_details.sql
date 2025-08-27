WITH expanded_trip AS
    (SELECT operation_day,
            trip_id,
            international_id AS trip_international_id,
            vehicle_id,
            vehicle_num_doors,
            counted_stop_times,
            direction,
            UNNEST(LINE)
     FROM vccdata),
     counted_stops AS
    (SELECT operation_day,
            trip_id,
            international_id AS trip_international_id,
            vehicle_id,
            vehicle_num_doors,
            direction,
            line_id,
            international_id AS line_international_id,
            name AS line_name,
            UNNEST(counted_stop_times) AS counted_stop
     FROM expanded_trip)
SELECT operation_day,
       trip_id,
       trip_international_id,
       vehicle_id,
       vehicle_num_doors,
       counted_stop.arrival_timestamp AS nom_arrival_timestamp,
       counted_stop.departure_timestamp AS nom_departure_timestamp,
       counted_stop.stop.stop_id AS stop_id,
       counted_stop.stop.parent_id AS stop_parent_id,
       counted_stop.stop.international_id AS stop_international_id,
       counted_stop.stop.latitude AS stop_latitude,
       counted_stop.stop.longitude AS stop_longitude,
       counted_stop.stop.name AS stop_name,
       counted_stop.sequence AS stop_sequence,
       direction,
       line_id,
       line_international_id,
       line_name
FROM counted_stops
WHERE operation_day = ?
    AND trip_id = ?
    AND vehicle_id = ?
GROUP BY
	operation_day,
	trip_id,
	trip_international_id,
	vehicle_id,
	vehicle_num_doors,
	counted_stop,
	direction,
	line_id,
	line_international_id,
	line_name
ORDER BY
	counted_stop.sequence