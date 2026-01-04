"""Tests for the PaneContainer widget.

This module tests the PaneContainer widget functionality including:
- Basic rendering with content
- Loading state display
- Error state display
- Stale data indicator
- State transitions
- Focus handling
"""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label, Static

from uptop.tui.widgets.pane_container import (
    ContentArea,
    ErrorDisplay,
    PaneContainer,
    PaneState,
    PaneTitleBar,
)


class PaneContainerTestApp(App[None]):
    """Test app for PaneContainer widget testing."""

    def __init__(
        self,
        title: str = "Test Pane",
        refresh_interval: float = 1.0,
        content: Static | None = None,
        is_loading: bool = False,
        has_error: bool = False,
        error_message: str = "",
        is_stale: bool = False,
    ) -> None:
        """Initialize test app with configurable pane container.

        Args:
            title: Pane title
            refresh_interval: Refresh interval in seconds
            content: Optional content widget
            is_loading: Initial loading state
            has_error: Initial error state
            error_message: Error message to display
            is_stale: Initial stale state
        """
        super().__init__()
        self._title = title
        self._refresh_interval = refresh_interval
        self._content = content
        self._is_loading = is_loading
        self._has_error = has_error
        self._error_message = error_message
        self._is_stale = is_stale

    def compose(self) -> ComposeResult:
        """Compose the test app with a PaneContainer."""
        container = PaneContainer(
            title=self._title,
            refresh_interval=self._refresh_interval,
            content=self._content,
            id="test-container",
        )
        container.is_loading = self._is_loading
        container.has_error = self._has_error
        container.error_message = self._error_message
        container.is_stale = self._is_stale
        yield container


class TestPaneState:
    """Tests for PaneState enum."""

    def test_pane_state_values(self) -> None:
        """Test that PaneState has expected values."""
        assert PaneState.NORMAL.value == "normal"
        assert PaneState.LOADING.value == "loading"
        assert PaneState.ERROR.value == "error"
        assert PaneState.STALE.value == "stale"

    def test_pane_state_is_string_enum(self) -> None:
        """Test that PaneState values are strings."""
        for state in PaneState:
            assert isinstance(state.value, str)


class PaneTitleBarTestApp(App[None]):
    """Test app for PaneTitleBar widget testing."""

    def __init__(
        self,
        title: str = "Test Title",
        state: PaneState = PaneState.NORMAL,
    ) -> None:
        """Initialize test app with configurable title bar.

        Args:
            title: Title bar title
            state: Initial state
        """
        super().__init__()
        self._title = title
        self._state = state

    def compose(self) -> ComposeResult:
        """Compose the test app with a PaneTitleBar."""
        yield PaneTitleBar(title=self._title, state=self._state, id="test-title-bar")


class TestPaneTitleBar:
    """Tests for PaneTitleBar widget."""

    @pytest.mark.asyncio
    async def test_title_bar_initialization(self) -> None:
        """Test PaneTitleBar initializes with correct defaults."""
        app = PaneTitleBarTestApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            title_bar = app.query_one("#test-title-bar", PaneTitleBar)
            assert title_bar.title == "Test Title"
            assert title_bar.state == PaneState.NORMAL

    @pytest.mark.asyncio
    async def test_title_bar_with_custom_values(self) -> None:
        """Test PaneTitleBar initializes with custom values."""
        app = PaneTitleBarTestApp(title="CPU Monitor", state=PaneState.LOADING)
        async with app.run_test() as pilot:
            await pilot.pause()
            title_bar = app.query_one("#test-title-bar", PaneTitleBar)
            assert title_bar.title == "CPU Monitor"
            assert title_bar.state == PaneState.LOADING

    @pytest.mark.asyncio
    async def test_title_bar_status_text_normal(self) -> None:
        """Test status text is empty for normal state."""
        app = PaneTitleBarTestApp(state=PaneState.NORMAL)
        async with app.run_test() as pilot:
            await pilot.pause()
            title_bar = app.query_one("#test-title-bar", PaneTitleBar)
            assert title_bar._get_status_text() == ""

    @pytest.mark.asyncio
    async def test_title_bar_status_text_loading(self) -> None:
        """Test status text for loading state."""
        app = PaneTitleBarTestApp(state=PaneState.LOADING)
        async with app.run_test() as pilot:
            await pilot.pause()
            title_bar = app.query_one("#test-title-bar", PaneTitleBar)
            assert title_bar._get_status_text() == "[*]"

    @pytest.mark.asyncio
    async def test_title_bar_status_text_error(self) -> None:
        """Test status text for error state."""
        app = PaneTitleBarTestApp(state=PaneState.ERROR)
        async with app.run_test() as pilot:
            await pilot.pause()
            title_bar = app.query_one("#test-title-bar", PaneTitleBar)
            assert title_bar._get_status_text() == "[!]"

    @pytest.mark.asyncio
    async def test_title_bar_status_text_stale(self) -> None:
        """Test status text for stale state."""
        app = PaneTitleBarTestApp(state=PaneState.STALE)
        async with app.run_test() as pilot:
            await pilot.pause()
            title_bar = app.query_one("#test-title-bar", PaneTitleBar)
            assert title_bar._get_status_text() == "[~]"


class TestErrorDisplay:
    """Tests for ErrorDisplay widget."""

    def test_error_display_initialization(self) -> None:
        """Test ErrorDisplay initializes with correct defaults."""
        error_display = ErrorDisplay()
        assert error_display.error_message == "An error occurred"

    def test_error_display_with_custom_message(self) -> None:
        """Test ErrorDisplay initializes with custom message."""
        error_display = ErrorDisplay(error_message="Connection failed")
        assert error_display.error_message == "Connection failed"


class TestPaneContainer:
    """Tests for PaneContainer widget."""

    def test_pane_container_initialization(self) -> None:
        """Test PaneContainer initializes with correct defaults."""
        container = PaneContainer()
        assert container.title == "Untitled"
        assert container.refresh_interval == 1.0
        assert container.is_loading is False
        assert container.has_error is False
        assert container.error_message == ""
        assert container.is_stale is False

    def test_pane_container_with_custom_values(self) -> None:
        """Test PaneContainer initializes with custom values."""
        content = Label("Test content")
        container = PaneContainer(
            title="Memory Monitor",
            refresh_interval=2.5,
            content=content,
            id="memory-pane",
            classes="primary",
        )
        assert container.title == "Memory Monitor"
        assert container.refresh_interval == 2.5
        assert container.id == "memory-pane"
        assert "primary" in container.classes

    def test_get_current_state_normal(self) -> None:
        """Test _get_current_state returns NORMAL by default."""
        container = PaneContainer()
        assert container._get_current_state() == PaneState.NORMAL

    def test_get_current_state_loading(self) -> None:
        """Test _get_current_state returns LOADING when is_loading is True."""
        container = PaneContainer()
        container.is_loading = True
        assert container._get_current_state() == PaneState.LOADING

    def test_get_current_state_error(self) -> None:
        """Test _get_current_state returns ERROR when has_error is True."""
        container = PaneContainer()
        container.has_error = True
        assert container._get_current_state() == PaneState.ERROR

    def test_get_current_state_stale(self) -> None:
        """Test _get_current_state returns STALE when is_stale is True."""
        container = PaneContainer()
        container.is_stale = True
        assert container._get_current_state() == PaneState.STALE

    def test_error_takes_precedence(self) -> None:
        """Test that error state takes precedence over loading and stale."""
        container = PaneContainer()
        container.is_loading = True
        container.is_stale = True
        container.has_error = True
        assert container._get_current_state() == PaneState.ERROR

    def test_loading_takes_precedence_over_stale(self) -> None:
        """Test that loading state takes precedence over stale."""
        container = PaneContainer()
        container.is_stale = True
        container.is_loading = True
        assert container._get_current_state() == PaneState.LOADING

    def test_set_error_method(self) -> None:
        """Test set_error method sets error state correctly."""
        container = PaneContainer()
        container.set_error("Collection failed")
        assert container.has_error is True
        assert container.error_message == "Collection failed"

    def test_clear_error_method(self) -> None:
        """Test clear_error method clears error state."""
        container = PaneContainer()
        container.set_error("Test error")
        container.clear_error()
        assert container.has_error is False
        assert container.error_message == ""

    def test_start_loading_method(self) -> None:
        """Test start_loading method sets loading state."""
        container = PaneContainer()
        container.start_loading()
        assert container.is_loading is True

    def test_stop_loading_method(self) -> None:
        """Test stop_loading method clears loading state."""
        container = PaneContainer()
        container.start_loading()
        container.stop_loading()
        assert container.is_loading is False

    def test_mark_stale_method(self) -> None:
        """Test mark_stale method sets stale state."""
        container = PaneContainer()
        container.mark_stale()
        assert container.is_stale is True

    def test_mark_fresh_method(self) -> None:
        """Test mark_fresh method clears stale state."""
        container = PaneContainer()
        container.mark_stale()
        container.mark_fresh()
        assert container.is_stale is False

    def test_can_focus_is_true(self) -> None:
        """Test that PaneContainer can receive focus for Tab navigation."""
        container = PaneContainer()
        assert container.can_focus is True


class TestPaneContainerRendering:
    """Integration tests for PaneContainer rendering using Textual pilot."""

    @pytest.mark.asyncio
    async def test_renders_with_title(self) -> None:
        """Test that PaneContainer renders with the correct title."""
        app = PaneContainerTestApp(title="CPU Monitor")
        async with app.run_test() as pilot:
            await pilot.pause()  # Allow widget composition
            container = app.query_one("#test-container", PaneContainer)
            title_bar = container.query_one("#title-bar", PaneTitleBar)
            assert title_bar.title == "CPU Monitor"

    @pytest.mark.asyncio
    async def test_renders_with_content(self) -> None:
        """Test that PaneContainer renders with content widget."""
        content = Label("Test content", id="test-content")
        app = PaneContainerTestApp(content=content)
        async with app.run_test() as pilot:
            await pilot.pause()  # Allow widget composition
            container = app.query_one("#test-container", PaneContainer)
            content_area = container.query_one("#content-area", ContentArea)
            assert content_area is not None

    @pytest.mark.asyncio
    async def test_loading_state_adds_class(self) -> None:
        """Test that loading state adds the loading CSS class."""
        app = PaneContainerTestApp(is_loading=True)
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            # Wait for any pending updates
            await pilot.pause()
            assert "loading" in container.classes

    @pytest.mark.asyncio
    async def test_error_state_adds_class(self) -> None:
        """Test that error state adds the error CSS class."""
        app = PaneContainerTestApp(has_error=True, error_message="Test error")
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            await pilot.pause()
            assert "error" in container.classes

    @pytest.mark.asyncio
    async def test_error_state_shows_error_display(self) -> None:
        """Test that error state shows the ErrorDisplay widget."""
        app = PaneContainerTestApp(has_error=True, error_message="Collection failed")
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            # Wait for recompose
            await pilot.pause()
            error_display = container.query_one("#error-display", ErrorDisplay)
            assert error_display.error_message == "Collection failed"

    @pytest.mark.asyncio
    async def test_stale_state_adds_class(self) -> None:
        """Test that stale state adds the stale CSS class."""
        app = PaneContainerTestApp(is_stale=True)
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            await pilot.pause()
            assert "stale" in container.classes

    @pytest.mark.asyncio
    async def test_title_update_reflects_in_ui(self) -> None:
        """Test that updating the title reflects in the UI."""
        app = PaneContainerTestApp(title="Original Title")
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            container.title = "Updated Title"
            await pilot.pause()
            title_bar = container.query_one("#title-bar", PaneTitleBar)
            assert title_bar.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_state_transition_loading_to_normal(self) -> None:
        """Test transitioning from loading to normal state."""
        app = PaneContainerTestApp(is_loading=True)
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            await pilot.pause()
            assert "loading" in container.classes

            container.stop_loading()
            await pilot.pause()
            assert "loading" not in container.classes

    @pytest.mark.asyncio
    async def test_state_transition_normal_to_error(self) -> None:
        """Test transitioning from normal to error state."""
        app = PaneContainerTestApp()
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            assert "error" not in container.classes

            container.set_error("Something went wrong")
            await pilot.pause()
            assert "error" in container.classes

    @pytest.mark.asyncio
    async def test_state_transition_error_to_normal(self) -> None:
        """Test transitioning from error to normal state."""
        app = PaneContainerTestApp(has_error=True, error_message="Initial error")
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)
            await pilot.pause()
            assert "error" in container.classes

            container.clear_error()
            await pilot.pause()
            assert "error" not in container.classes

    @pytest.mark.asyncio
    async def test_set_content_updates_display(self) -> None:
        """Test that set_content updates the displayed content."""
        initial_content = Label("Initial", id="initial-content")
        app = PaneContainerTestApp(content=initial_content)
        async with app.run_test() as pilot:
            container = app.query_one("#test-container", PaneContainer)

            new_content = Label("Updated", id="updated-content")
            container.set_content(new_content)
            await pilot.pause()

            # The container should have the new content widget stored
            assert container._content_widget == new_content


class TestContentArea:
    """Tests for ContentArea widget."""

    def test_content_area_initialization(self) -> None:
        """Test ContentArea initializes correctly."""
        content_area = ContentArea()
        assert content_area is not None


class TestPaneContainerCSS:
    """Tests for PaneContainer CSS styling."""

    def test_pane_container_has_default_css(self) -> None:
        """Test that PaneContainer has default CSS defined."""
        assert PaneContainer.DEFAULT_CSS is not None
        assert "border" in PaneContainer.DEFAULT_CSS
        assert "loading" in PaneContainer.DEFAULT_CSS
        assert "error" in PaneContainer.DEFAULT_CSS
        assert "stale" in PaneContainer.DEFAULT_CSS

    def test_pane_title_bar_has_default_css(self) -> None:
        """Test that PaneTitleBar has default CSS defined."""
        assert PaneTitleBar.DEFAULT_CSS is not None
        assert "PaneTitleBar" in PaneTitleBar.DEFAULT_CSS

    def test_error_display_has_default_css(self) -> None:
        """Test that ErrorDisplay has default CSS defined."""
        assert ErrorDisplay.DEFAULT_CSS is not None
        assert "ErrorDisplay" in ErrorDisplay.DEFAULT_CSS

    def test_content_area_has_default_css(self) -> None:
        """Test that ContentArea has default CSS defined."""
        assert ContentArea.DEFAULT_CSS is not None
        assert "ContentArea" in ContentArea.DEFAULT_CSS
