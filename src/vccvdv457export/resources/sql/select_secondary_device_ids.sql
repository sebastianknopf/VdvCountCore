SELECT
    DISTINCT device_id AS 'device_id'
FROM
    vccdata
WHERE
    operation_day = ?
    AND trip_id = ?
    AND device_id <> ?