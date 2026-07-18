"""Shared local tool types."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


ToolArguments = Mapping[str, Any]
ToolOutput = Mapping[str, Any]
ParameterSchema = Mapping[str, Any]
ToolRunner = Callable[[ToolArguments], ToolOutput]


@dataclass(frozen=True)
class LocalTool:
    """Metadata and executable function for one local tool."""

    name: str
    description: str
    parameter_schema: ParameterSchema
    run: ToolRunner
