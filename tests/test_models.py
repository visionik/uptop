"""Tests for uptop data models."""

from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
import pytest

from uptop.models import (
    Counter,
    CounterFloat,
    Gauge,
    GaugeInt,
    MetricData,
    MetricType,
    PluginMetadata,
    PluginType,
    SystemSnapshot,
    counter_field,
    gauge_field,
    get_all_metric_types,
    get_metric_type,
    histogram_field,
    summary_field,
)


def _utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class TestMetricData:
    """Tests for MetricData base class."""

    def test_default_timestamp(self) -> None:
        """Test that timestamp defaults to now."""
        before = _utcnow()
        data = MetricData()
        after = _utcnow()

        assert before <= data.timestamp <= after

    def test_default_source(self) -> None:
        """Test that source defaults to 'unknown'."""
        data = MetricData()
        assert data.source == "unknown"

    def test_custom_source(self) -> None:
        """Test setting custom source."""
        data = MetricData(source="cpu_collector")
        assert data.source == "cpu_collector"

    def test_age_seconds(self) -> None:
        """Test age_seconds calculation."""
        old_time = _utcnow() - timedelta(seconds=5)
        data = MetricData(timestamp=old_time)

        age = data.age_seconds()
        assert 4.9 <= age <= 6.0  # Allow some tolerance

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            MetricData(unknown_field="value")


class TestPluginMetadata:
    """Tests for PluginMetadata model."""

    def test_required_fields(self) -> None:
        """Test that name and display_name are required."""
        meta = PluginMetadata(
            name="test_plugin",
            display_name="Test Plugin",
            plugin_type=PluginType.PANE,
        )
        assert meta.name == "test_plugin"
        assert meta.display_name == "Test Plugin"

    def test_defaults(self) -> None:
        """Test default values."""
        meta = PluginMetadata(
            name="test_plugin",
            display_name="Test Plugin",
            plugin_type=PluginType.PANE,
        )
        assert meta.version == "0.1.0"
        assert meta.api_version == "1.0"
        assert meta.enabled is True
        assert meta.description == ""

    def test_name_validation_valid(self) -> None:
        """Test valid plugin names."""
        valid_names = ["cpu", "my_plugin", "plugin123", "a"]
        for name in valid_names:
            meta = PluginMetadata(
                name=name,
                display_name="Test",
                plugin_type=PluginType.PANE,
            )
            assert meta.name == name

    def test_name_validation_invalid(self) -> None:
        """Test invalid plugin names are rejected."""
        invalid_names = ["", "123start", "has-hyphen", "HAS_CAPS", "has space"]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                PluginMetadata(
                    name=name,
                    display_name="Test",
                    plugin_type=PluginType.PANE,
                )

    def test_version_validation(self) -> None:
        """Test version must be semver format."""
        # Valid
        meta = PluginMetadata(
            name="test",
            display_name="Test",
            plugin_type=PluginType.PANE,
            version="1.2.3",
        )
        assert meta.version == "1.2.3"

        # Invalid
        with pytest.raises(ValidationError):
            PluginMetadata(
                name="test",
                display_name="Test",
                plugin_type=PluginType.PANE,
                version="not-a-version",
            )

    def test_frozen(self) -> None:
        """Test that PluginMetadata is immutable."""
        meta = PluginMetadata(
            name="test",
            display_name="Test",
            plugin_type=PluginType.PANE,
        )
        with pytest.raises(ValidationError):
            meta.name = "changed"

    def test_all_plugin_types(self) -> None:
        """Test all plugin types are valid."""
        for ptype in PluginType:
            meta = PluginMetadata(
                name="test",
                display_name="Test",
                plugin_type=ptype,
            )
            assert meta.plugin_type == ptype


class TestSystemSnapshot:
    """Tests for SystemSnapshot model."""

    def test_default_values(self) -> None:
        """Test default values."""
        snapshot = SystemSnapshot()
        assert snapshot.hostname == ""
        assert snapshot.panes == {}
        assert isinstance(snapshot.timestamp, datetime)

    def test_add_pane_data(self) -> None:
        """Test adding pane data."""
        snapshot = SystemSnapshot()
        data = MetricData(source="cpu")

        snapshot.add_pane_data("cpu", data)

        assert "cpu" in snapshot.panes
        assert snapshot.panes["cpu"] == data

    def test_get_pane_data(self) -> None:
        """Test getting pane data."""
        snapshot = SystemSnapshot()
        data = MetricData(source="memory")
        snapshot.add_pane_data("memory", data)

        result = snapshot.get_pane_data("memory")
        assert result == data

    def test_get_pane_data_missing(self) -> None:
        """Test getting non-existent pane returns None."""
        snapshot = SystemSnapshot()
        result = snapshot.get_pane_data("nonexistent")
        assert result is None

    def test_multiple_panes(self) -> None:
        """Test snapshot with multiple panes."""
        snapshot = SystemSnapshot(hostname="testhost")
        snapshot.add_pane_data("cpu", MetricData(source="cpu"))
        snapshot.add_pane_data("memory", MetricData(source="memory"))
        snapshot.add_pane_data("disk", MetricData(source="disk"))

        assert len(snapshot.panes) == 3
        assert snapshot.hostname == "testhost"


class TestPluginType:
    """Tests for PluginType enum."""

    def test_all_types_exist(self) -> None:
        """Test all expected plugin types exist."""
        assert PluginType.PANE == "pane"
        assert PluginType.COLLECTOR == "collector"
        assert PluginType.FORMATTER == "formatter"
        assert PluginType.ACTION == "action"

    def test_string_values(self) -> None:
        """Test plugin types are string enums."""
        for ptype in PluginType:
            assert isinstance(ptype.value, str)


class TestMetricType:
    """Tests for MetricType enum."""

    def test_all_types_exist(self) -> None:
        """Test all expected metric types exist."""
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.HISTOGRAM == "histogram"
        assert MetricType.SUMMARY == "summary"

    def test_string_values(self) -> None:
        """Test metric types are string enums."""
        for mtype in MetricType:
            assert isinstance(mtype.value, str)


class TestMetricFieldFactories:
    """Tests for metric field factory functions."""

    def test_counter_field_creates_correct_type(self) -> None:
        """Test counter_field creates a field with counter metric type."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: int = counter_field("Test counter")

        assert get_metric_type(TestModel, "value") == MetricType.COUNTER

    def test_gauge_field_creates_correct_type(self) -> None:
        """Test gauge_field creates a field with gauge metric type."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: float = gauge_field("Test gauge")

        assert get_metric_type(TestModel, "value") == MetricType.GAUGE

    def test_histogram_field_creates_correct_type(self) -> None:
        """Test histogram_field creates a field with histogram metric type."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: list[float] = histogram_field("Test histogram", default_factory=list)

        assert get_metric_type(TestModel, "value") == MetricType.HISTOGRAM

    def test_summary_field_creates_correct_type(self) -> None:
        """Test summary_field creates a field with summary metric type."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: float = summary_field("Test summary", default=0.0)

        assert get_metric_type(TestModel, "value") == MetricType.SUMMARY

    def test_field_with_constraints(self) -> None:
        """Test that field factories work with Pydantic constraints."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            percent: float = gauge_field("Percentage", ge=0.0, le=100.0)
            count: int = counter_field("Count", ge=0)

        # Test validation works
        model = TestModel(percent=50.0, count=10)
        assert model.percent == 50.0
        assert model.count == 10

        # Test constraint violation
        with pytest.raises(ValidationError):
            TestModel(percent=150.0, count=10)

        with pytest.raises(ValidationError):
            TestModel(percent=50.0, count=-1)

    def test_field_description_preserved(self) -> None:
        """Test that field descriptions are preserved in schema."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            bytes_sent: int = counter_field("Total bytes transmitted")

        schema = TestModel.model_json_schema()
        assert schema["properties"]["bytes_sent"]["description"] == "Total bytes transmitted"


class TestMetricTypeAliases:
    """Tests for type aliases (Counter, Gauge, etc.)."""

    def test_counter_alias(self) -> None:
        """Test Counter type alias detection."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: Counter

        assert get_metric_type(TestModel, "value") == MetricType.COUNTER

    def test_counter_float_alias(self) -> None:
        """Test CounterFloat type alias detection."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: CounterFloat

        assert get_metric_type(TestModel, "value") == MetricType.COUNTER

    def test_gauge_alias(self) -> None:
        """Test Gauge type alias detection."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: Gauge

        assert get_metric_type(TestModel, "value") == MetricType.GAUGE

    def test_gauge_int_alias(self) -> None:
        """Test GaugeInt type alias detection."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: GaugeInt

        assert get_metric_type(TestModel, "value") == MetricType.GAUGE


class TestGetMetricType:
    """Tests for get_metric_type function."""

    def test_returns_none_for_unannotated_field(self) -> None:
        """Test that unannotated fields return None."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: int

        assert get_metric_type(TestModel, "value") is None

    def test_returns_none_for_nonexistent_field(self) -> None:
        """Test that nonexistent fields return None."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            value: int

        assert get_metric_type(TestModel, "nonexistent") is None

    def test_works_with_metric_data_subclass(self) -> None:
        """Test metric type extraction works with MetricData subclasses."""

        class TestData(MetricData):
            bytes_sent: int = counter_field("Bytes sent")
            cpu_percent: float = gauge_field("CPU usage")

        assert get_metric_type(TestData, "bytes_sent") == MetricType.COUNTER
        assert get_metric_type(TestData, "cpu_percent") == MetricType.GAUGE
        assert get_metric_type(TestData, "timestamp") is None  # Inherited, no metric type


class TestGetAllMetricTypes:
    """Tests for get_all_metric_types function."""

    def test_returns_all_annotated_fields(self) -> None:
        """Test that all annotated fields are returned."""

        class TestData(MetricData):
            bytes_sent: int = counter_field("Bytes sent")
            bytes_recv: int = counter_field("Bytes received")
            cpu_percent: float = gauge_field("CPU usage")
            name: str = ""  # Not a metric

        result = get_all_metric_types(TestData)

        assert len(result) == 3
        assert result["bytes_sent"] == MetricType.COUNTER
        assert result["bytes_recv"] == MetricType.COUNTER
        assert result["cpu_percent"] == MetricType.GAUGE
        assert "name" not in result
        assert "timestamp" not in result
        assert "source" not in result

    def test_empty_for_no_metrics(self) -> None:
        """Test returns empty dict for models without metric annotations."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            name: str
            value: int

        result = get_all_metric_types(TestModel)
        assert result == {}

    def test_mixed_type_aliases_and_fields(self) -> None:
        """Test models mixing type aliases and field factories."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            counter_alias: Counter
            gauge_field_val: float = gauge_field("A gauge")
            plain_field: str = ""

        result = get_all_metric_types(TestModel)

        assert len(result) == 2
        assert result["counter_alias"] == MetricType.COUNTER
        assert result["gauge_field_val"] == MetricType.GAUGE
