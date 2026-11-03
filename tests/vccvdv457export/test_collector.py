from vccvdv457export.collector import PassengerCountingEventCollector


def test_empty_primary_data_yields_no_events():
    collector = PassengerCountingEventCollector([], 'dev1')

    assert collector.get_passenger_counting_events() == []
