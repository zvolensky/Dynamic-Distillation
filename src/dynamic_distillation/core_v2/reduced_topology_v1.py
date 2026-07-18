"""Role-based five-volume topology for the DD-077 structural gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlVolume:
    volume_id: str
    role: str
    equilibrium_vapor_outlet: bool


@dataclass(frozen=True)
class InternalStream:
    stream_id: str
    source_volume: str
    destination_volume: str
    phase: str
    flow_symbol: str
    flow_owner: str
    hydraulic_unknown: bool = False


@dataclass(frozen=True)
class ExternalStream:
    stream_id: str
    volume_id: str
    direction: str
    phase: str
    flow_symbol: str
    flow_owner: str


@dataclass(frozen=True)
class ReducedColumnTopology:
    control_volumes: tuple[ControlVolume, ...]
    internal_streams: tuple[InternalStream, ...]
    external_streams: tuple[ExternalStream, ...]
    feed_volume_id: str

    @property
    def volume_ids(self) -> tuple[str, ...]:
        return tuple(volume.volume_id for volume in self.control_volumes)


def build_five_volume_topology() -> ReducedColumnTopology:
    """Return the generic reduced topology selected by DD-076.

    The total condenser is represented by the condensing vapor stream entering
    the reflux drum. It is not an inventory-bearing control volume.
    """
    drum = "reflux_drum"
    rectifying = "rectifying_tray"
    feed = "feed_tray"
    stripping = "stripping_tray"
    bottom = "combined_reboiler_sump"

    volumes = (
        ControlVolume(drum, "reflux_drum", False),
        ControlVolume(rectifying, "rectifying_tray", True),
        ControlVolume(feed, "feed_tray", True),
        ControlVolume(stripping, "stripping_tray", True),
        ControlVolume(bottom, "combined_reboiler_sump", True),
    )
    internal = (
        InternalStream(
            "reflux",
            drum,
            rectifying,
            "liquid",
            "R",
            "terminal_specification",
        ),
        InternalStream(
            "rectifying_liquid",
            rectifying,
            feed,
            "liquid",
            f"L[{rectifying}]",
            "francis_hydraulics",
            hydraulic_unknown=True,
        ),
        InternalStream(
            "feed_liquid",
            feed,
            stripping,
            "liquid",
            f"L[{feed}]",
            "francis_hydraulics",
            hydraulic_unknown=True,
        ),
        InternalStream(
            "stripping_liquid",
            stripping,
            bottom,
            "liquid",
            f"L[{stripping}]",
            "francis_hydraulics",
            hydraulic_unknown=True,
        ),
        InternalStream(
            "bottom_boilup",
            bottom,
            stripping,
            "vapor",
            "V_stripping",
            "prescribed_section_vapor",
        ),
        InternalStream(
            "stripping_vapor",
            stripping,
            feed,
            "vapor",
            "V_stripping",
            "prescribed_section_vapor",
        ),
        InternalStream(
            "feed_vapor",
            feed,
            rectifying,
            "vapor",
            "V_rectifying",
            "prescribed_section_vapor",
        ),
        InternalStream(
            "overhead_vapor",
            rectifying,
            drum,
            "condensing_vapor",
            "V_rectifying",
            "prescribed_section_vapor",
        ),
    )
    external = (
        ExternalStream(
            "feed",
            feed,
            "in",
            "feed",
            "F",
            "feed_specification",
        ),
        ExternalStream(
            "distillate",
            drum,
            "out",
            "liquid",
            "D",
            "terminal_inventory_specification",
        ),
        ExternalStream(
            "bottoms",
            bottom,
            "out",
            "liquid",
            "B",
            "terminal_inventory_specification",
        ),
    )
    return ReducedColumnTopology(
        control_volumes=volumes,
        internal_streams=internal,
        external_streams=external,
        feed_volume_id=feed,
    )
