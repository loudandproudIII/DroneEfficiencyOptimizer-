"""
Propeller Analyzer Configuration Module
========================================

This module contains configuration settings for the Propeller Analyzer.
All paths, filenames, and default values are centralized here for easy
modification and deployment flexibility.

Configuration Classes:
---------------------
- PropAnalyzerConfig: Main configuration class with all settings

Usage:
------
    from src.prop_analyzer.config import PropAnalyzerConfig

    # Use default configuration
    config = PropAnalyzerConfig()

    # Or customize paths
    config = PropAnalyzerConfig(
        data_root="/custom/path/to/data",
        database_filename="custom-database.pkl"
    )
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PropAnalyzerConfig:
    """
    Configuration settings for the Propeller Analyzer module.

    This class centralizes all configuration parameters including file paths,
    database locations, and default values used throughout the prop analyzer.

    Attributes:
    ----------
    data_root : Path
        Root directory containing all propeller data files.
        Default: "Prop analysis Tool" folder relative to project root.

    interpolator_dir : str
        Subdirectory name containing the interpolator pickle files.
        These files contain pre-computed scipy interpolator objects for
        each propeller, enabling fast thrust/power lookups.

    performance_dir : str
        Subdirectory name containing raw APC performance DAT files.
        These are the original data files from APC's website.

    database_filename : str
        Filename of the propeller database (pickle format).
        Contains consolidated performance data for all propellers.

    database_csv_filename : str
        Filename of the propeller database in CSV format.
        Human-readable version of the database for inspection.

    default_verbose : bool
        Default verbosity setting for function outputs.
        When True, functions will print warnings and status messages.

    Example:
    -------
        config = PropAnalyzerConfig()
        print(config.interpolator_path)  # Full path to interpolator files
        print(config.database_path)      # Full path to database file
    """

    # -------------------------------------------------------------------------
    # Path Configuration
    # -------------------------------------------------------------------------

    # Root directory for propeller data (relative to project root)
    # This can be overridden for different deployment configurations
    data_root: Optional[Path] = None

    # Subdirectory names within data_root
    interpolator_dir: str = "20_APC_interpolator_files"
    performance_dir: str = "10_APC_PERFILES"
    resources_dir: str = "00_resources"

    # Database filenames
    database_filename: str = "APC-Prop-DB.pkl"
    database_csv_filename: str = "APC-Prop-DB.csv"

    # -------------------------------------------------------------------------
    # Runtime Configuration
    # -------------------------------------------------------------------------

    # Default verbosity for function outputs
    default_verbose: bool = False

    # Interpolator return value when query is out of bounds
    out_of_bounds_value: float = -99.0

    # Root finding tolerance for power calculations
    root_finding_tolerance: float = 0.001

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    def __post_init__(self):
        """
        Initialize computed paths after dataclass initialization.

        This method determines the project root directory and sets up
        all path attributes based on the data_root configuration.
        """
        # Determine project root (three levels up from this file)
        # File location: src/prop_analyzer/config.py
        # Path: config.py -> prop_analyzer/ -> src/ -> PROJECT_ROOT/
        self._project_root = Path(__file__).parent.parent.parent

        # Set default data_root if not provided
        if self.data_root is None:
            self.data_root = self._project_root / "Prop analysis Tool"
        elif isinstance(self.data_root, str):
            self.data_root = Path(self.data_root)

    @property
    def project_root(self) -> Path:
        """Get the project root directory."""
        return self._project_root

    @property
    def interpolator_path(self) -> Path:
        """
        Get the full path to the interpolator files directory.

        Returns:
        -------
        Path
            Absolute path to the directory containing interpolator pickle files.
        """
        return self.data_root / self.interpolator_dir

    @property
    def performance_path(self) -> Path:
        """
        Get the full path to the raw performance data directory.

        Returns:
        -------
        Path
            Absolute path to the directory containing APC DAT files.
        """
        return self.data_root / self.performance_dir

    @property
    def resources_path(self) -> Path:
        """
        Get the full path to the resources directory.

        Returns:
        -------
        Path
            Absolute path to the directory containing resource files (images, etc.).
        """
        return self.data_root / self.resources_dir

    @property
    def database_path(self) -> Path:
        """
        Get the full path to the propeller database file.

        Returns:
        -------
        Path
            Absolute path to the pickle database file.
        """
        return self.data_root / self.database_filename

    @property
    def database_csv_path(self) -> Path:
        """
        Get the full path to the CSV database file.

        Returns:
        -------
        Path
            Absolute path to the CSV database file.
        """
        return self.data_root / self.database_csv_filename

    def get_thrust_interpolator_path(self, prop_name: str) -> Path:
        """
        Get the path to a specific propeller's thrust interpolator file.

        Parameters:
        ----------
        prop_name : str
            The propeller identifier (e.g., "7x7E", "10x5").

        Returns:
        -------
        Path
            Full path to the thrust interpolator pickle file.

        Example:
        -------
            config = PropAnalyzerConfig()
            path = config.get_thrust_interpolator_path("7x7E")
            # Returns: .../20_APC_interpolator_files/7x7E_thrust_interpolator.pkl
        """
        filename = f"{prop_name}_thrust_interpolator.pkl"
        return self.interpolator_path / filename

    def get_power_interpolator_path(self, prop_name: str) -> Path:
        """
        Get the path to a specific propeller's power interpolator file.

        Parameters:
        ----------
        prop_name : str
            The propeller identifier (e.g., "7x7E", "10x5").

        Returns:
        -------
        Path
            Full path to the power interpolator pickle file.

        Example:
        -------
            config = PropAnalyzerConfig()
            path = config.get_power_interpolator_path("7x7E")
            # Returns: .../20_APC_interpolator_files/7x7E_power_interpolator.pkl
        """
        filename = f"{prop_name}_power_interpolator.pkl"
        return self.interpolator_path / filename

    def validate_paths(self) -> dict:
        """
        Validate that all required paths exist.

        Returns:
        -------
        dict
            Dictionary with path names as keys and existence status as values.

        Example:
        -------
            config = PropAnalyzerConfig()
            status = config.validate_paths()
            if not all(status.values()):
                print("Warning: Some paths are missing!")
        """
        return {
            "data_root": self.data_root.exists(),
            "interpolator_dir": self.interpolator_path.exists(),
            "performance_dir": self.performance_path.exists(),
            "database_file": self.database_path.exists(),
        }

    def list_available_props(self) -> list:
        """
        List all available propeller models in the interpolator directory.

        Scans the interpolator directory for thrust interpolator files and
        extracts the propeller names from the filenames.

        Returns:
        -------
        list
            Sorted list of available propeller model names.

        Example:
        -------
            config = PropAnalyzerConfig()
            props = config.list_available_props()
            print(props[:5])  # ['10x10', '10x10E', '10x12WE', ...]
        """
        if not self.interpolator_path.exists():
            return []

        # Find all thrust interpolator files and extract prop names
        props = []
        for filepath in self.interpolator_path.glob("*_thrust_interpolator.pkl"):
            # Extract prop name from filename (remove suffix)
            prop_name = filepath.stem.replace("_thrust_interpolator", "")
            props.append(prop_name)

        return sorted(props)


# -------------------------------------------------------------------------
# Module-level default configuration instance
# -------------------------------------------------------------------------

# Create a default configuration instance for convenience
# This can be imported directly: from config import DEFAULT_CONFIG
DEFAULT_CONFIG = PropAnalyzerConfig()
