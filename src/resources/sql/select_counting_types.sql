SELECT DISTINCT COALESCE(counting_type, 'COMPARISON') AS counting_type
FROM vccdata
WHERE operation_day = ?
    AND trip_id = ?
    AND vehicle_id = ?
ORDER BY counting_type
