"""Tests for the CPU pane plugin."""

from collections import namedtuple
from unittest.mock import MagicMock, patch

from pydantic import ValidationError
import pytest

from uptop.models import MetricData, MetricType, PluginType, get_metric_type
from uptop.plugins.cpu import CPUCollector, CPUCore, CPUData, CPUPane

MockFreqInfo = namedtuple("scpufreq", ["current", "min", "max"])
MockTempReading = namedtuple("shwtemp", ["label", "current", "high", "critical"])


class TestCPUCore:
    def test_valid_core(self) -> None:
        core = CPUCore(id=0, usage_percent=50.0)
        assert core.id == 0
        assert core.usage_percent == 50.0

    def test_core_with_all_fields(self) -> None:
        core = CPUCore(id=1, usage_percent=75.5, freq_mhz=3600.0, temp_celsius=65.0)
        assert core.freq_mhz == 3600.0

    def test_core_id_must_be_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            CPUCore(id=-1, usage_percent=50.0)

    def test_usage_percent_bounds(self) -> None:
        with pytest.raises(ValidationError):
            CPUCore(id=0, usage_percent=101.0)


class TestCPUData:
    def test_empty_cpudata(self) -> None:
        data = CPUData()
        assert data.cores == []
        assert data.core_count == 0

    def test_total_usage_percent(self) -> None:
        cores = [CPUCore(id=i, usage_percent=float((i + 1) * 20)) for i in range(4)]
        data = CPUData(cores=cores)
        assert data.total_usage_percent == 50.0


class TestCPUMetricTypes:
    """Tests for metric type annotations on CPU models."""

    def test_cpucore_metric_types(self) -> None:
        """Test that CPUCore fields have correct metric types."""
        assert get_metric_type(CPUCore, "usage_percent") == MetricType.GAUGE
        assert get_metric_type(CPUCore, "freq_mhz") == MetricType.GAUGE
        assert get_metric_type(CPUCore, "temp_celsius") == MetricType.GAUGE
        # id is not a metric
        assert get_metric_type(CPUCore, "id") is None

    def test_cpudata_metric_types(self) -> None:
        """Test that CPUData fields have correct metric types."""
        assert get_metric_type(CPUData, "load_avg_1min") == MetricType.GAUGE
        assert get_metric_type(CPUData, "load_avg_5min") == MetricType.GAUGE
        assert get_metric_type(CPUData, "load_avg_15min") == MetricType.GAUGE


class TestCPUCollector:
    def test_collector_attributes(self) -> None:
        collector = CPUCollector()
        assert collector.name == "cpu"

    def test_get_schema(self) -> None:
        collector = CPUCollector()
        assert collector.get_schema() == CPUData

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_with_mocked_psutil(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_freq = MockFreqInfo(current=3000.0, min=800.0, max=4000.0)
        mock_psutil.cpu_percent.return_value = [25.0, 50.0]
        mock_psutil.cpu_freq.return_value = [mock_freq] * 2
        mock_psutil.getloadavg.return_value = (1.0, 2.0, 3.0)
        mock_psutil.sensors_temperatures.return_value = {}
        data = await collector.collect()
        assert data.core_count == 2

    @patch("uptop.plugins.cpu.psutil")
    def test_get_cpu_temps_empty(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_psutil.sensors_temperatures.return_value = {}
        temps = collector._get_cpu_temps()
        assert temps == {}


class TestCPUPane:
    def test_pane_attributes(self) -> None:
        pane = CPUPane()
        assert pane.name == "cpu"
        assert pane.display_name == "CPU Monitor"

    def test_plugin_type(self) -> None:
        assert CPUPane.get_plugin_type() == PluginType.PANE

    def test_get_schema(self) -> None:
        pane = CPUPane()
        assert pane.get_schema() == CPUData

    def test_initialize(self) -> None:
        pane = CPUPane()
        pane.initialize()
        assert pane._initialized is True

    def test_shutdown(self) -> None:
        pane = CPUPane()
        pane.initialize()
        pane.shutdown()
        assert pane._initialized is False

    def test_render_tui_with_valid_data(self) -> None:
        pane = CPUPane()
        cores = [CPUCore(id=0, usage_percent=25.0)]
        data = CPUData(cores=cores, load_avg_1min=1.5, load_avg_5min=2.0, load_avg_15min=1.8)
        widget = pane.render_tui(data)
        from uptop.tui.panes.cpu_widget import CPUWidget

        assert isinstance(widget, CPUWidget)
        assert hasattr(widget, "update_data")

    def test_render_tui_with_invalid_data(self) -> None:
        pane = CPUPane()
        data = MetricData()
        widget = pane.render_tui(data)
        from textual.widgets import Label

        assert isinstance(widget, Label)

    def test_get_ai_help_docs(self) -> None:
        pane = CPUPane()
        docs = pane.get_ai_help_docs()
        assert "CPU Monitor" in docs

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_data(self, mock_psutil: MagicMock) -> None:
        pane = CPUPane()
        pane.initialize()
        mock_freq = MockFreqInfo(current=3000.0, min=800.0, max=4000.0)
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.return_value = [mock_freq]
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        mock_psutil.sensors_temperatures.return_value = {}
        data = await pane.collect_data()
        assert isinstance(data, CPUData)

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_data_auto_init(self, mock_psutil: MagicMock) -> None:
        pane = CPUPane()
        mock_freq = MockFreqInfo(current=3000.0, min=800.0, max=4000.0)
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.return_value = [mock_freq]
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        mock_psutil.sensors_temperatures.return_value = {}
        await pane.collect_data()
        assert pane._collector is not None

    def test_render_tui_with_freq_and_temp(self) -> None:
        pane = CPUPane()
        cores = [
            CPUCore(id=0, usage_percent=25.0, freq_mhz=3000.0, temp_celsius=55.0),
            CPUCore(id=1, usage_percent=75.0, freq_mhz=3200.0),
        ]
        data = CPUData(cores=cores, load_avg_1min=1.5, load_avg_5min=2.0, load_avg_15min=1.8)
        widget = pane.render_tui(data)
        from uptop.tui.panes.cpu_widget import CPUWidget

        assert isinstance(widget, CPUWidget)
        assert hasattr(widget, "update_data")

    def test_initialize_with_config(self) -> None:
        pane = CPUPane()
        pane.initialize({"interval": 2.0})
        assert pane._collector is not None
        assert pane.config == {"interval": 2.0}


class TestCPUCollectorExtended:
    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_no_freq_percpu_fallback(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_freq = MockFreqInfo(current=2500.0, min=800.0, max=3500.0)
        mock_psutil.cpu_percent.return_value = [50.0, 50.0]
        mock_psutil.cpu_freq.side_effect = [None, mock_freq]
        mock_psutil.getloadavg.return_value = (0.5, 0.5, 0.5)
        mock_psutil.sensors_temperatures.return_value = {}
        data = await collector.collect()
        assert data.cores[0].freq_mhz == 2500.0

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_no_freq_at_all(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.side_effect = [None, None]
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        mock_psutil.sensors_temperatures.return_value = {}
        data = await collector.collect()
        assert data.cores[0].freq_mhz is None

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_freq_exception(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.side_effect = RuntimeError("Freq unavailable")
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        mock_psutil.sensors_temperatures.return_value = {}
        data = await collector.collect()
        assert data.cores[0].freq_mhz is None

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_with_coretemp(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_freq = MockFreqInfo(current=3000.0, min=800.0, max=4000.0)
        mock_temps = [
            MockTempReading(label="Core 0", current=55.0, high=80.0, critical=100.0),
        ]
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.return_value = [mock_freq]
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        mock_psutil.sensors_temperatures.return_value = {"coretemp": mock_temps}
        data = await collector.collect()
        assert data.cores[0].temp_celsius == 55.0

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_with_cpu_in_sensor_name(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_freq = MockFreqInfo(current=3000.0, min=800.0, max=4000.0)
        mock_temps = [
            MockTempReading(label="Core 0", current=45.0, high=80.0, critical=100.0),
        ]
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.return_value = [mock_freq]
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        mock_psutil.sensors_temperatures.return_value = {"my_cpu_thermal": mock_temps}
        data = await collector.collect()
        assert data.cores[0].temp_celsius == 45.0

    @pytest.mark.asyncio
    @patch("uptop.plugins.cpu.psutil")
    async def test_collect_no_sensors_attr(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_freq = MockFreqInfo(current=3000.0, min=800.0, max=4000.0)
        mock_psutil.cpu_percent.return_value = [50.0]
        mock_psutil.cpu_freq.return_value = [mock_freq]
        mock_psutil.getloadavg.return_value = (1.0, 1.0, 1.0)
        del mock_psutil.sensors_temperatures
        data = await collector.collect()
        assert data.cores[0].temp_celsius is None

    @patch("uptop.plugins.cpu.psutil")
    def test_get_cpu_temps_exception(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_psutil.sensors_temperatures.side_effect = RuntimeError("Error")
        temps = collector._get_cpu_temps()
        assert temps == {}

    @patch("uptop.plugins.cpu.psutil")
    def test_get_cpu_temps_none_result(self, mock_psutil: MagicMock) -> None:
        collector = CPUCollector()
        mock_psutil.sensors_temperatures.return_value = None
        temps = collector._get_cpu_temps()
        assert temps == {}
