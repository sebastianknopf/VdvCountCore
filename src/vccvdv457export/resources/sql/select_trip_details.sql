WITH expanded_trip AS (
	SELECT
		operation_day,
		trip_id,
		device_id,
		vehicle_id,
		counted_stop_times,
		UNNEST(line)
	FROM
		vccdata
), 
counted_stops AS (
	SELECT
    	operation_day,
    	trip_id,
    	device_id,
    	vehicle_id,
    	line_id,
    	international_id AS line_international_id, 
    	name AS line_name,
    	UNNEST(counted_stop_times) AS counted_stop
  	FROM 
  		expanded_trip
)
SELECT
	operation_day,
	trip_id,
	device_id,
	vehicle_id,
	counted_stop.stop.stop_id AS stop_id,
	counted_stop.stop.international_id AS stop_international_id,
	counted_stop.stop.latitude AS stop_latitude,
	counted_stop.stop.longitude AS stop_longitude,
	counted_stop.stop.name AS stop_name,
	counted_stop.sequence AS stop_sequence,
	line_id,
	line_international_id,
	line_name
FROM
	counted_stops
WHERE
	operation_day = ?
	AND trip_id = ?
	AND device_id = ?