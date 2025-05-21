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
),
grouped_matched_passenger_counting_events AS (
	SELECT
		operation_day,
		trip_id,
		device_id,
		COUNT(counted_stop) AS 'num_matched_pce'
	FROM
		matched_passenger_counting_events
	GROUP BY
		operation_day,
		trip_id,
		device_id
	ORDER BY
		operation_day,
		trip_id
),
primary_indicators AS (
  SELECT
    operation_day,
    trip_id,
    MAX(num_matched_pce) AS max_pce
  FROM
    grouped_matched_passenger_counting_events
  GROUP BY
    operation_day,
    trip_id
)
SELECT
  g.operation_day,
  g.trip_id,
  g.device_id
FROM
  grouped_matched_passenger_counting_events g
JOIN
  primary_indicators p
ON
  g.operation_day = p.operation_day 
  AND g.trip_id = p.trip_id
  AND g.num_matched_pce = p.max_pce
ORDER BY
  g.operation_day,
  g.trip_id;