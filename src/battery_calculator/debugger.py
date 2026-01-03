"""
Calculation Debugger
====================

Traces and records all calculation steps for debugging and verification.
Provides detailed output of every variable and formula used.
"""

from dataclasses import dataclass, field
from typing import List, Any, Optional
from datetime import datetime


@dataclass
class CalculationStep:
    """A single calculation step with inputs, formula, and result."""
    category: str           # e.g., "Voltage", "Thermal", "Energy"
    description: str        # Human-readable description
    formula: str            # Mathematical formula (optional)
    variables: dict         # Input variables with values
    result: Any             # Calculated result
    result_name: str        # Name of the result variable
    result_unit: str        # Unit of the result
    comment: str = ""       # Additional explanation


class CalculationDebugger:
    """
    Traces and records all calculation steps for debugging.

    Usage:
        debugger = CalculationDebugger()
        debugger.start_section("Voltage Calculations")
        debugger.add_step(
            category="Voltage",
            description="Calculate open circuit voltage",
            formula="V_oc = SOC_to_OCV(SOC) * Series",
            variables={"SOC": 80, "Series": 6},
            result=24.0,
            result_name="V_oc",
            result_unit="V",
            comment="Using NMC SOC-OCV curve"
        )
        print(debugger.get_report())
    """

    def __init__(self):
        """Initialize the debugger."""
        self.steps: List[CalculationStep] = []
        self.sections: List[tuple] = []  # (index, section_name)
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.metadata: dict = {}

    def clear(self):
        """Clear all recorded steps."""
        self.steps = []
        self.sections = []
        self.start_time = None
        self.end_time = None
        self.metadata = {}

    def start(self, **metadata):
        """Start a new debugging session."""
        self.clear()
        self.start_time = datetime.now()
        self.metadata = metadata

    def finish(self):
        """Finish the debugging session."""
        self.end_time = datetime.now()

    def start_section(self, name: str):
        """Start a new section of calculations."""
        self.sections.append((len(self.steps), name))

    def add_step(
        self,
        category: str,
        description: str,
        formula: str,
        variables: dict,
        result: Any,
        result_name: str,
        result_unit: str = "",
        comment: str = ""
    ):
        """Add a calculation step."""
        self.steps.append(CalculationStep(
            category=category,
            description=description,
            formula=formula,
            variables=variables,
            result=result,
            result_name=result_name,
            result_unit=result_unit,
            comment=comment
        ))

    def add_input(self, name: str, value: Any, unit: str = "", description: str = ""):
        """Add an input variable (convenience method)."""
        self.add_step(
            category="Input",
            description=description or f"Input parameter: {name}",
            formula="",
            variables={},
            result=value,
            result_name=name,
            result_unit=unit
        )

    def add_constant(self, name: str, value: Any, unit: str = "", description: str = ""):
        """Add a constant value (convenience method)."""
        self.add_step(
            category="Constant",
            description=description or f"Constant: {name}",
            formula="",
            variables={},
            result=value,
            result_name=name,
            result_unit=unit
        )

    def get_report(self, include_sections: bool = True) -> str:
        """
        Generate a formatted text report of all calculations.

        Parameters:
        ----------
        include_sections : bool
            Include section headers in the report

        Returns:
        -------
        str
            Formatted calculation trace
        """
        lines = []

        # Header
        lines.append("=" * 70)
        lines.append("CALCULATION DEBUG REPORT")
        lines.append("=" * 70)

        if self.start_time:
            lines.append(f"Generated: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Metadata
        if self.metadata:
            lines.append("")
            lines.append("Configuration:")
            for key, value in self.metadata.items():
                lines.append(f"  {key}: {value}")

        lines.append("")

        # Build section index for quick lookup
        section_indices = {idx: name for idx, name in self.sections}

        # Process each step
        current_category = None
        step_num = 0

        for i, step in enumerate(self.steps):
            # Check for section header
            if include_sections and i in section_indices:
                lines.append("")
                lines.append("=" * 70)
                lines.append(f">>> {section_indices[i]}")
                lines.append("=" * 70)
                lines.append("")

            # Category header
            if step.category != current_category and step.category not in ["Input", "Constant"]:
                if current_category is not None:
                    lines.append("")
                lines.append(f"--- {step.category} ---")
                lines.append("")
                current_category = step.category

            step_num += 1

            # Step header
            lines.append(f"[{step_num}] {step.description}")

            # Variables
            if step.variables:
                var_strs = []
                for name, value in step.variables.items():
                    if isinstance(value, float):
                        var_strs.append(f"{name}={value:.6g}")
                    else:
                        var_strs.append(f"{name}={value}")
                lines.append(f"    Inputs: {', '.join(var_strs)}")

            # Formula
            if step.formula:
                lines.append(f"    Formula: {step.formula}")

            # Result
            if isinstance(step.result, float):
                if step.result_unit:
                    lines.append(f"    => {step.result_name} = {step.result:.6g} {step.result_unit}")
                else:
                    lines.append(f"    => {step.result_name} = {step.result:.6g}")
            else:
                if step.result_unit:
                    lines.append(f"    => {step.result_name} = {step.result} {step.result_unit}")
                else:
                    lines.append(f"    => {step.result_name} = {step.result}")

            # Comment
            if step.comment:
                lines.append(f"    // {step.comment}")

            lines.append("")

        # Footer
        lines.append("=" * 70)
        lines.append(f"Total Steps: {len(self.steps)}")
        if self.start_time and self.end_time:
            elapsed = (self.end_time - self.start_time).total_seconds()
            lines.append(f"Elapsed Time: {elapsed:.3f} seconds")
        lines.append("=" * 70)

        return "\n".join(lines)

    def get_step_count(self) -> int:
        """Return the number of recorded steps."""
        return len(self.steps)

    def find_steps_by_category(self, category: str) -> List[CalculationStep]:
        """Find all steps in a given category."""
        return [s for s in self.steps if s.category == category]

    def find_step_by_result(self, result_name: str) -> Optional[CalculationStep]:
        """Find the step that produced a specific result."""
        for step in reversed(self.steps):  # Search from end for most recent
            if step.result_name == result_name:
                return step
        return None


# Global debugger instance for easy access
_debugger: Optional[CalculationDebugger] = None


def get_debugger() -> CalculationDebugger:
    """Get the global debugger instance."""
    global _debugger
    if _debugger is None:
        _debugger = CalculationDebugger()
    return _debugger


def set_debugger(debugger: Optional[CalculationDebugger]):
    """Set the global debugger instance."""
    global _debugger
    _debugger = debugger


def debug_step(
    category: str,
    description: str,
    formula: str,
    variables: dict,
    result: Any,
    result_name: str,
    result_unit: str = "",
    comment: str = ""
):
    """Add a step to the global debugger (if active)."""
    if _debugger is not None:
        _debugger.add_step(
            category=category,
            description=description,
            formula=formula,
            variables=variables,
            result=result,
            result_name=result_name,
            result_unit=result_unit,
            comment=comment
        )
