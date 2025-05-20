WITH counted_stops AS (
  SELECT
    operation_day,
    trip_id,
    device_id,
    UNNEST(counted_stop_times) AS counted_stop
  FROM 
  	vccdata
),
matched_passenger_counting_events AS (
	SELECT
    	operation_day,
    	trip_id,
    	device_id,
    	counted_stop,
    	UNNEST(counted_stop.passenger_counting_events) AS passenger_counting_event
  	FROM 
  		counted_stops
)
SELECT
	operation_day,
	trip_id,
	device_id,
	COUNT(counted_stop) AS 'num_counted_stops_with_pce'
FROM
	matched_passenger_counting_events
GROUP BY
	operation_day,
	trip_id,
	device_id
HAVING
	COUNT(passenger_counting_event) > 0
ORDER BY
	operation_day,
	trip_id