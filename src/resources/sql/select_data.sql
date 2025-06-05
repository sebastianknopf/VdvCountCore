WITH counted_stops AS
    (SELECT operation_day,
            trip_id,
            vehicle_id,
            device_id,
            UNNEST(counted_stop_times) AS counted_stop
     FROM vccdata),
     matched_passenger_counting_events AS
    (SELECT operation_day,
            trip_id,
            vehicle_id,
            device_id,
            counted_stop,
            UNNEST(counted_stop.passenger_counting_events) AS passenger_counting_event
     FROM counted_stops),
     matched_counting_sequences AS
    (SELECT operation_day,
            trip_id,
            vehicle_id,
            device_id,
            counted_stop,
            passenger_counting_event,
            UNNEST(passenger_counting_event.counting_sequences) AS counting_sequence
     FROM matched_passenger_counting_events),
     unmatched_passenger_counting_events AS
    (SELECT operation_day,
            trip_id,
            vehicle_id,
            device_id,
            UNNEST(unmatched_passenger_counting_events) AS passenger_counting_event
     FROM vccdata),
     unmatched_counting_sequences AS
    (SELECT operation_day,
            trip_id,
            vehicle_id,
            device_id,
            passenger_counting_event,
            UNNEST(passenger_counting_event.counting_sequences) AS counting_sequence
     FROM unmatched_passenger_counting_events)
SELECT *
FROM
    (SELECT operation_day,
            trip_id,
            vehicle_id,
            device_id,
            counted_stop.arrival_timestamp AS nom_arrival_timestamp,
            counted_stop.departure_timestamp AS nom_arrival_timestamp,
            counted_stop.stop.stop_id AS stop_id,
            counted_stop.stop.parent_id AS stop_parent_id,
            counted_stop.stop.international_id AS stop_international_id,
            counted_stop.stop.latitude AS stop_latitude,
            counted_stop.stop.longitude AS stop_longitude,
            counted_stop.stop.name AS stop_name,
            counted_stop.sequence AS stop_sequence,
            passenger_counting_event.after_stop_sequence AS pce_after_stop_sequence,
            passenger_counting_event.latitude AS pce_latitude,
            passenger_counting_event.longitude AS pce_longitude,
            counting_sequence.door_id AS door_id,
            counting_sequence.counting_area_id AS counting_area_id,
            counting_sequence.object_class AS object_class,
            counting_sequence.count_begin_timestamp AS begin_timestamp,
            counting_sequence.count_end_timestamp AS end_timestamp,
            counting_sequence.in,
            counting_sequence.out
     FROM matched_counting_sequences
     UNION SELECT operation_day,
                  trip_id,
                  vehicle_id,
                  device_id,
                  NULL AS nom_arrival_timestamp,
                  NULL AS departure_timestamp,
                  NULL AS stop_id,
                  NULL AS stop_parent_id,
                  NULL AS stop_international_id,
                  NULL AS stop_latitude,
                  NULL AS stop_longitude,
                  NULL AS stop_name,
                  NULL AS stop_sequence,
                  passenger_counting_event.after_stop_sequence AS pce_after_stop_sequence,
                  passenger_counting_event.latitude AS pce_latitude,
                  passenger_counting_event.longitude AS pce_longitude,
                  counting_sequence.door_id AS door_id,
                  counting_sequence.counting_area_id AS counting_area_id,
                  counting_sequence.object_class AS object_class,
                  counting_sequence.count_begin_timestamp AS begin_timestamp,
                  counting_sequence.count_end_timestamp AS end_timestamp,
                  counting_sequence.in,
                  counting_sequence.out
     FROM unmatched_counting_sequences
     ORDER BY counting_sequence.count_begin_timestamp)
WHERE operation_day = ?
    AND trip_id = ?
    AND vehicle_id = ?
    AND device_id = ?