"""
Gulf of Mexico Environment Facade.

This module provides the primary interface to the temporal engine, re-exporting
all core components for seamless integration.
"""

from gom.runtime.types import MutabilityFlavor, LifetimeUnit
from gom.runtime.temporal import TemporalAnchor, TimelinePoint, VariableTimeline
from gom.stdlib.collections import GOMArray, GOMObject
from gom.runtime.engine import RealityDistortionField
from gom.runtime.executor import GOMExecutor

__all__ = [
    'MutabilityFlavor',
    'LifetimeUnit',
    'TemporalAnchor',
    'TimelinePoint',
    'VariableTimeline',
    'GOMArray',
    'GOMObject',
    'RealityDistortionField',
    'GOMExecutor',
]
