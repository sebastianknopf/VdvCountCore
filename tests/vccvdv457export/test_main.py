import pytest
import os

import vccvdv457export.__main__ as main


class FakeDDB:
    instances = []

    def __init__(self, data_directory, schema_filename):
        self.closed = False
        FakeDDB.instances.append(self)

    def close(self):
        self.closed = True


class OkAdapter:
    calls = []

    def __init__(self, archive_name, create_reports):
        self.archive_name, self.create_reports = archive_name, create_reports

    def process(self, ddb, output_directory, invalid_output_directory, passenger_counting_output_directory=None, comparison_counting_output_directory=None):
        OkAdapter.calls.append((self.create_reports, output_directory, invalid_output_directory, passenger_counting_output_directory, comparison_counting_output_directory))


class FailingAdapter(OkAdapter):
    def process(self, ddb, output_directory, invalid_output_directory, passenger_counting_output_directory=None, comparison_counting_output_directory=None):
        raise RuntimeError('conversion failed')


@pytest.fixture
def env(monkeypatch):
    for name in ('VCC_VDV457_EXPORT_CONVERT_2', 'VCC_VDV457_EXPORT_CONVERT_3', 'VCC_VDV457_EXPORT_REPORT_2',
                 'VCC_VDV457_EXPORT_REPORT_3', 'VCC_VDV457_EXPORT_ADAPTER_TYPE_2', 'VCC_VDV457_EXPORT_ADAPTER_TYPE_3',
                 'VCC_VDV457_EXPORT_OUTPUT_INVALID_DIRECTORY_2', 'VCC_VDV457_EXPORT_OUTPUT_INVALID_DIRECTORY_3',
                 'VCC_VDV457_EXPORT_OUTPUT_PASSENGER_COUNTING_DIRECTORY_2', 'VCC_VDV457_EXPORT_OUTPUT_PASSENGER_COUNTING_DIRECTORY_3',
                 'VCC_VDV457_EXPORT_OUTPUT_COMPARISON_COUNTING_DIRECTORY_2', 'VCC_VDV457_EXPORT_OUTPUT_COMPARISON_COUNTING_DIRECTORY_3',
                 'VCC_DEBUG'):
        monkeypatch.delenv(name, raising=False)

    FakeDDB.instances.clear()
    OkAdapter.calls.clear()

    archived = []
    staged = []
    monkeypatch.setattr(main, 'directory_contains_files', lambda directory: True)
    monkeypatch.setattr(main, 'stage_directory_files', lambda *args: staged.append(args))
    monkeypatch.setattr(main, 'archive_directory_files', lambda *args: archived.append(args))
    monkeypatch.setattr(main, 'DuckDB', FakeDDB)
    monkeypatch.setattr(main.s2, 'DefaultAdapter', OkAdapter)
    monkeypatch.setattr(main.s3, 'DefaultAdapter', OkAdapter)

    return {'archived': archived, 'staged': staged, 'monkeypatch': monkeypatch}


def failed(env) -> bool:
    [call] = env['archived']
    return call[3]


class TestRunNow:

    def test_empty_input_directory_does_nothing(self, env):
        env['monkeypatch'].setattr(main, 'directory_contains_files', lambda directory: False)

        main._run_now()

        assert env['staged'] == [] and env['archived'] == [] and FakeDDB.instances == []

    def test_files_are_staged_before_processing(self, env):
        main._run_now()

        assert env['staged'] == [('/data/input', '/data/stage')]

    def test_no_converter_enabled_archives_without_failure(self, env):
        main._run_now()

        assert OkAdapter.calls == []
        assert failed(env) is False
        assert FakeDDB.instances[0].closed

    def test_vdv4572_converter_uses_its_directories(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')

        main._run_now()

        assert OkAdapter.calls == [(False, '/data/vdv4572', '/data/vdv4572', None, None)]
        assert failed(env) is False

    def test_vdv4573_converter_uses_its_directories(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_3', '1')

        main._run_now()

        assert OkAdapter.calls == [(False, '/data/vdv4573', '/data/vdv4573', None, None)]

    def test_converter_uses_configured_invalid_directory(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_INVALID_DIRECTORY_2', '/invalid/2')

        main._run_now()

        assert OkAdapter.calls == [(False, '/data/vdv4572', '/data/vdv4572/invalid/2', None, None)]

    def test_converter_uses_configured_counting_directories(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_PASSENGER_COUNTING_DIRECTORY_2', '/pc/2')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_COMPARISON_COUNTING_DIRECTORY_2', '/cc/2')

        main._run_now()

        assert OkAdapter.calls == [(False, '/data/vdv4572', '/data/vdv4572', '/data/vdv4572/pc/2', '/data/vdv4572/cc/2')]

    def test_converter_uses_relative_subdirectories_as_given(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_INVALID_DIRECTORY_2', 'invalid')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_PASSENGER_COUNTING_DIRECTORY_2', 'pc')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_COMPARISON_COUNTING_DIRECTORY_2', 'cc')

        main._run_now()

        assert OkAdapter.calls == [(False, '/data/vdv4572', '/data/vdv4572/invalid', '/data/vdv4572/pc', '/data/vdv4572/cc')]

    def test_base_output_directory_env_is_ignored(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_OUTPUT_DIRECTORY_2', '/ignored/base')

        main._run_now()

        assert OkAdapter.calls == [(False, '/data/vdv4572', '/data/vdv4572', None, None)]

    def test_both_converters_run_when_enabled(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_3', 'true')

        main._run_now()

        assert len(OkAdapter.calls) == 2

    def test_reports_are_enabled_per_converter(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_3', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_REPORT_3', 'true')

        main._run_now()

        assert [c[0] for c in OkAdapter.calls] == [False, True]

    def test_disabled_converter_flag_is_not_run(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'false')

        main._run_now()

        assert OkAdapter.calls == []

    def test_failing_converter_marks_archive_as_failed(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setattr(main.s2, 'DefaultAdapter', FailingAdapter)

        main._run_now()

        assert failed(env) is True
        assert FakeDDB.instances[0].closed

    def test_failing_converter_does_not_stop_the_other_converter(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_3', 'true')
        env['monkeypatch'].setattr(main.s2, 'DefaultAdapter', FailingAdapter)

        main._run_now()

        assert len(OkAdapter.calls) == 1
        assert OkAdapter.calls[0][1] == '/data/vdv4573'
        assert failed(env) is True

    def test_unknown_adapter_type_marks_archive_as_failed(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_2', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_ADAPTER_TYPE_2', 'unknown')

        main._run_now()

        assert OkAdapter.calls == []
        assert failed(env) is True

    def test_unknown_adapter_type_for_vdv4573_marks_archive_as_failed(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_CONVERT_3', 'true')
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_ADAPTER_TYPE_3', 'unknown')

        main._run_now()

        assert failed(env) is True

    def test_database_initialisation_error_marks_archive_as_failed(self, env):
        def broken(*args):
            raise OSError('no schema')

        env['monkeypatch'].setattr(main, 'DuckDB', broken)

        main._run_now()

        assert failed(env) is True

    def test_archive_receives_directories_and_batch_name(self, env):
        main._run_now()

        stage, input_directory, archive_name, _ = env['archived'][0]
        assert (stage, input_directory) == ('/data/stage', '/data/input')
        assert len(archive_name) == 14 and archive_name.isdigit()


class TestRun:

    def test_runs_when_cron_matches(self, env):
        calls = []
        env['monkeypatch'].setattr(main, '_run_now', lambda: calls.append(1))
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_INTERVAL', '* * * * *')

        main.run()

        assert calls == [1]

    def test_does_not_run_when_cron_does_not_match(self, env):
        calls = []
        env['monkeypatch'].setattr(main, '_run_now', lambda: calls.append(1))
        # a date that never matches: February 31st
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_INTERVAL', '0 0 30 2 *')

        main.run()

        assert calls == []

    def test_invalid_cron_expression_raises(self, env):
        env['monkeypatch'].setenv('VCC_VDV457_EXPORT_INTERVAL', 'not a cron')

        with pytest.raises(Exception):
            main.run()


class TestOutputDirectories:

    def test_creates_base_and_relative_subdirectories_on_demand(self, monkeypatch, tmp_path):
        monkeypatch.setenv('VCC_VDV457_EXPORT_OUTPUT_INVALID_DIRECTORY_2', 'invalid')
        monkeypatch.setenv('VCC_VDV457_EXPORT_OUTPUT_PASSENGER_COUNTING_DIRECTORY_2', 'pc')
        monkeypatch.setenv('VCC_VDV457_EXPORT_OUTPUT_COMPARISON_COUNTING_DIRECTORY_2', 'cc')
        monkeypatch.setenv('VCC_VDV457_EXPORT_OUTPUT_DIRECTORY_2', str(tmp_path / 'ignored'))

        output_directory, invalid_output_directory, passenger_output_directory, comparison_output_directory = main._get_output_directories('2')

        assert output_directory == '/data/vdv4572'
        assert invalid_output_directory == '/data/vdv4572/invalid'
        assert passenger_output_directory == '/data/vdv4572/pc'
        assert comparison_output_directory == '/data/vdv4572/cc'
        assert os.path.isdir('/data/vdv4572')
        assert os.path.isdir('/data/vdv4572/invalid')
        assert os.path.isdir('/data/vdv4572/pc')
        assert os.path.isdir('/data/vdv4572/cc')

    def test_creates_only_base_and_default_invalid_when_optionals_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv('VCC_VDV457_EXPORT_OUTPUT_DIRECTORY_3', str(tmp_path / 'ignored'))
        monkeypatch.delenv('VCC_VDV457_EXPORT_OUTPUT_INVALID_DIRECTORY_3', raising=False)
        monkeypatch.delenv('VCC_VDV457_EXPORT_OUTPUT_PASSENGER_COUNTING_DIRECTORY_3', raising=False)
        monkeypatch.delenv('VCC_VDV457_EXPORT_OUTPUT_COMPARISON_COUNTING_DIRECTORY_3', raising=False)

        output_directory, invalid_output_directory, passenger_output_directory, comparison_output_directory = main._get_output_directories('3')

        assert output_directory == '/data/vdv4573'
        assert invalid_output_directory == '/data/vdv4573'
        assert passenger_output_directory is None
        assert comparison_output_directory is None
        assert os.path.isdir('/data/vdv4573')
