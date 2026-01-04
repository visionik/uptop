"""Tests for uptop theming system."""

import pytest

from uptop.config import Config, TUIConfig
from uptop.tui.themes import (
    AVAILABLE_THEMES,
    DARK_THEME,
    DEFAULT_THEME_NAME,
    GRUVBOX_THEME,
    LIGHT_THEME,
    NORD_THEME,
    SOLARIZED_THEME,
    Theme,
    ThemeColors,
    generate_theme_css,
    get_theme,
    get_theme_css,
    get_theme_css_from_config,
    get_theme_from_config,
    is_valid_theme,
    list_themes,
)


class TestThemeColors:
    """Tests for ThemeColors dataclass."""

    def test_theme_colors_immutable(self) -> None:
        """Test that ThemeColors is immutable (frozen)."""
        colors = ThemeColors(
            background="#000000",
            background_secondary="#111111",
            foreground="#ffffff",
            foreground_muted="#cccccc",
            accent="#0000ff",
            accent_secondary="#0088ff",
            border="#333333",
            border_focused="#0000ff",
            success="#00ff00",
            warning="#ffff00",
            error="#ff0000",
            info="#00ffff",
            table_header="#222222",
            table_row_odd="#000000",
            table_row_even="#111111",
            scrollbar="#222222",
            scrollbar_thumb="#444444",
            progress_bar="#0000ff",
            progress_bar_background="#222222",
        )
        with pytest.raises(AttributeError):
            colors.background = "#ffffff"  # type: ignore[misc]

    def test_theme_colors_has_all_required_fields(self) -> None:
        """Test that ThemeColors requires all color fields."""
        with pytest.raises(TypeError):
            ThemeColors(background="#000000")  # type: ignore[call-arg]


class TestTheme:
    """Tests for Theme dataclass."""

    def test_theme_immutable(self) -> None:
        """Test that Theme is immutable (frozen)."""
        theme = DARK_THEME
        with pytest.raises(AttributeError):
            theme.name = "modified"  # type: ignore[misc]

    def test_theme_has_required_attributes(self) -> None:
        """Test that themes have all required attributes."""
        for theme_name in AVAILABLE_THEMES:
            theme = get_theme(theme_name)
            assert hasattr(theme, "name")
            assert hasattr(theme, "display_name")
            assert hasattr(theme, "description")
            assert hasattr(theme, "colors")
            assert hasattr(theme, "is_dark")
            assert isinstance(theme.colors, ThemeColors)

    def test_default_is_dark_true(self) -> None:
        """Test that is_dark defaults to True."""
        colors = DARK_THEME.colors
        theme = Theme(
            name="test",
            display_name="Test",
            description="Test theme",
            colors=colors,
        )
        assert theme.is_dark is True


class TestBuiltInThemes:
    """Tests for built-in theme definitions."""

    def test_dark_theme_exists(self) -> None:
        """Test dark theme is available."""
        assert "dark" in AVAILABLE_THEMES
        assert DARK_THEME.name == "dark"
        assert DARK_THEME.is_dark is True

    def test_light_theme_exists(self) -> None:
        """Test light theme is available."""
        assert "light" in AVAILABLE_THEMES
        assert LIGHT_THEME.name == "light"
        assert LIGHT_THEME.is_dark is False

    def test_solarized_theme_exists(self) -> None:
        """Test solarized theme is available."""
        assert "solarized" in AVAILABLE_THEMES
        assert SOLARIZED_THEME.name == "solarized"
        assert SOLARIZED_THEME.is_dark is True

    def test_nord_theme_exists(self) -> None:
        """Test nord theme is available."""
        assert "nord" in AVAILABLE_THEMES
        assert NORD_THEME.name == "nord"
        assert NORD_THEME.is_dark is True

    def test_gruvbox_theme_exists(self) -> None:
        """Test gruvbox theme is available."""
        assert "gruvbox" in AVAILABLE_THEMES
        assert GRUVBOX_THEME.name == "gruvbox"
        assert GRUVBOX_THEME.is_dark is True

    def test_all_themes_have_valid_colors(self) -> None:
        """Test all themes have valid hex color values."""
        hex_pattern = r"^#[0-9a-fA-F]{6}$"
        import re

        for theme_name in AVAILABLE_THEMES:
            theme = get_theme(theme_name)
            colors = theme.colors
            # Check all color fields are valid hex
            for field_name in [
                "background",
                "background_secondary",
                "foreground",
                "foreground_muted",
                "accent",
                "accent_secondary",
                "border",
                "border_focused",
                "success",
                "warning",
                "error",
                "info",
                "table_header",
                "table_row_odd",
                "table_row_even",
                "scrollbar",
                "scrollbar_thumb",
                "progress_bar",
                "progress_bar_background",
            ]:
                color = getattr(colors, field_name)
                assert re.match(
                    hex_pattern, color
                ), f"Theme '{theme_name}' has invalid color for {field_name}: {color}"

    def test_theme_colors_match_guidelines(self) -> None:
        """Test theme colors match the specified guidelines."""
        # Dark theme
        assert DARK_THEME.colors.background == "#1e1e2e"
        assert DARK_THEME.colors.foreground == "#cdd6f4"
        assert DARK_THEME.colors.accent == "#89b4fa"

        # Light theme
        assert LIGHT_THEME.colors.background == "#eff1f5"
        assert LIGHT_THEME.colors.foreground == "#4c4f69"
        assert LIGHT_THEME.colors.accent == "#1e66f5"

        # Solarized theme
        assert SOLARIZED_THEME.colors.background == "#002b36"
        assert SOLARIZED_THEME.colors.foreground == "#839496"
        assert SOLARIZED_THEME.colors.accent == "#268bd2"

        # Nord theme
        assert NORD_THEME.colors.background == "#2e3440"
        assert NORD_THEME.colors.foreground == "#eceff4"
        assert NORD_THEME.colors.accent == "#88c0d0"

        # Gruvbox theme
        assert GRUVBOX_THEME.colors.background == "#282828"
        assert GRUVBOX_THEME.colors.foreground == "#ebdbb2"
        assert GRUVBOX_THEME.colors.accent == "#fabd2f"


class TestGetTheme:
    """Tests for get_theme function."""

    def test_get_existing_theme(self) -> None:
        """Test getting an existing theme by name."""
        theme = get_theme("dark")
        assert theme.name == "dark"

        theme = get_theme("light")
        assert theme.name == "light"

    def test_get_nonexistent_theme_returns_default(self) -> None:
        """Test getting a non-existent theme returns dark theme."""
        theme = get_theme("nonexistent")
        assert theme.name == DEFAULT_THEME_NAME
        assert theme.name == "dark"

    def test_get_theme_case_sensitive(self) -> None:
        """Test theme lookup is case-sensitive."""
        theme = get_theme("DARK")  # Uppercase should not match
        assert theme.name == "dark"  # Falls back to default

    def test_get_all_available_themes(self) -> None:
        """Test all available themes can be retrieved."""
        for theme_name in AVAILABLE_THEMES:
            theme = get_theme(theme_name)
            assert theme.name == theme_name


class TestGetThemeCss:
    """Tests for get_theme_css function."""

    def test_get_css_for_existing_theme(self) -> None:
        """Test getting CSS for an existing theme."""
        css = get_theme_css("dark")
        assert isinstance(css, str)
        assert len(css) > 0
        assert "uptop theme: dark" in css

    def test_get_css_for_nonexistent_theme(self) -> None:
        """Test getting CSS for non-existent theme returns dark theme CSS."""
        css = get_theme_css("nonexistent")
        assert "uptop theme: dark" in css

    def test_css_contains_color_variables(self) -> None:
        """Test generated CSS contains expected color variables."""
        css = get_theme_css("dark")
        assert "$background:" in css
        assert "$foreground:" in css
        assert "$accent:" in css
        assert "$border:" in css
        assert "$success:" in css
        assert "$warning:" in css
        assert "$error:" in css

    def test_css_contains_widget_styles(self) -> None:
        """Test generated CSS contains widget styles."""
        css = get_theme_css("dark")
        assert "Screen {" in css
        assert "DataTable" in css
        assert "ProgressBar" in css
        assert "Button" in css
        assert "Input" in css


class TestGenerateThemeCss:
    """Tests for generate_theme_css function."""

    def test_generate_css_from_theme(self) -> None:
        """Test generating CSS from a theme object."""
        css = generate_theme_css(DARK_THEME)
        assert isinstance(css, str)
        assert "dark" in css

    def test_generate_css_includes_theme_colors(self) -> None:
        """Test generated CSS includes the theme's actual colors."""
        css = generate_theme_css(DARK_THEME)
        assert DARK_THEME.colors.background in css
        assert DARK_THEME.colors.foreground in css
        assert DARK_THEME.colors.accent in css


class TestThemeFromConfig:
    """Tests for config-based theme loading."""

    def test_get_theme_from_config(self) -> None:
        """Test getting theme from config object."""
        config = Config(tui=TUIConfig(theme="nord"))
        theme = get_theme_from_config(config)
        assert theme.name == "nord"

    def test_get_theme_from_config_default(self) -> None:
        """Test getting theme from default config."""
        config = Config()  # Default config has theme="dark"
        theme = get_theme_from_config(config)
        assert theme.name == "dark"

    def test_get_theme_from_config_fallback(self) -> None:
        """Test fallback when config has invalid theme."""
        config = Config(tui=TUIConfig(theme="invalid_theme"))
        theme = get_theme_from_config(config)
        assert theme.name == "dark"  # Falls back to default

    def test_get_css_from_config(self) -> None:
        """Test getting theme CSS from config object."""
        config = Config(tui=TUIConfig(theme="solarized"))
        css = get_theme_css_from_config(config)
        assert "solarized" in css


class TestListThemes:
    """Tests for list_themes function."""

    def test_list_themes_returns_all(self) -> None:
        """Test list_themes returns all available themes."""
        themes = list_themes()
        assert len(themes) == len(AVAILABLE_THEMES)

    def test_list_themes_returns_tuples(self) -> None:
        """Test list_themes returns proper tuple format."""
        themes = list_themes()
        for name, display_name, description in themes:
            assert isinstance(name, str)
            assert isinstance(display_name, str)
            assert isinstance(description, str)
            assert len(name) > 0
            assert len(display_name) > 0
            assert len(description) > 0

    def test_list_themes_includes_expected(self) -> None:
        """Test list_themes includes expected themes."""
        themes = list_themes()
        theme_names = [t[0] for t in themes]
        assert "dark" in theme_names
        assert "light" in theme_names
        assert "solarized" in theme_names
        assert "nord" in theme_names
        assert "gruvbox" in theme_names


class TestIsValidTheme:
    """Tests for is_valid_theme function."""

    def test_valid_themes_return_true(self) -> None:
        """Test valid theme names return True."""
        for theme_name in AVAILABLE_THEMES:
            assert is_valid_theme(theme_name) is True

    def test_invalid_theme_returns_false(self) -> None:
        """Test invalid theme names return False."""
        assert is_valid_theme("nonexistent") is False
        assert is_valid_theme("DARK") is False
        assert is_valid_theme("") is False


class TestDefaultTheme:
    """Tests for default theme constant."""

    def test_default_theme_name_is_dark(self) -> None:
        """Test that default theme is 'dark'."""
        assert DEFAULT_THEME_NAME == "dark"

    def test_default_theme_exists(self) -> None:
        """Test that default theme exists in available themes."""
        assert DEFAULT_THEME_NAME in AVAILABLE_THEMES

    def test_default_theme_is_valid(self) -> None:
        """Test that default theme can be loaded."""
        theme = get_theme(DEFAULT_THEME_NAME)
        assert theme is not None
        assert isinstance(theme, Theme)


class TestAvailableThemes:
    """Tests for AVAILABLE_THEMES constant."""

    def test_available_themes_is_list(self) -> None:
        """Test AVAILABLE_THEMES is a list."""
        assert isinstance(AVAILABLE_THEMES, list)

    def test_available_themes_contains_expected(self) -> None:
        """Test AVAILABLE_THEMES contains all expected themes."""
        expected = ["dark", "light", "solarized", "nord", "gruvbox"]
        for theme in expected:
            assert theme in AVAILABLE_THEMES

    def test_available_themes_count(self) -> None:
        """Test correct number of themes."""
        assert len(AVAILABLE_THEMES) == 5


class TestThemeIntegration:
    """Integration tests for theming system."""

    def test_all_themes_generate_valid_css(self) -> None:
        """Test all themes generate syntactically reasonable CSS."""
        for theme_name in AVAILABLE_THEMES:
            css = get_theme_css(theme_name)
            # Basic CSS structure checks
            assert "{" in css
            assert "}" in css
            # Should have screen styling
            assert "Screen" in css
            # Should reference theme name
            assert theme_name in css

    def test_theme_round_trip(self) -> None:
        """Test theme can be retrieved after being registered."""
        for theme_name in AVAILABLE_THEMES:
            # Get theme
            theme = get_theme(theme_name)
            # Theme name should match
            assert theme.name == theme_name
            # Colors should be accessible
            assert theme.colors.background is not None
            # CSS should be generatable
            css = generate_theme_css(theme)
            assert len(css) > 100  # Non-trivial CSS
