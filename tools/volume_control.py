"""Windows system master volume via pycaw."""
from __future__ import annotations


class VolumeController:
    """Control the default output device master volume."""

    def __init__(self) -> None:
        self._volume = self._get_volume_interface()

    def _get_volume_interface(self):
        try:
            from pycaw.pycaw import AudioUtilities
        except ImportError as exc:
            raise ImportError(
                "Volume control requires pycaw. Install with: pip install pycaw comtypes"
            ) from exc

        device = AudioUtilities.GetSpeakers()
        if device is None:
            raise RuntimeError("No default speaker device found.")
        return device.EndpointVolume

    def set_volume_percent(self, percent: int) -> int:
        percent = max(0, min(100, int(percent)))
        self._volume.SetMasterVolumeLevelScalar(percent / 100.0, None)
        return percent

    def get_volume_percent(self) -> int:
        return int(round(self._volume.GetMasterVolumeLevelScalar() * 100))

    def increase(self, step: int = 10) -> int:
        return self.set_volume_percent(self.get_volume_percent() + step)

    def decrease(self, step: int = 10) -> int:
        return self.set_volume_percent(self.get_volume_percent() - step)

    def mute(self) -> None:
        self._volume.SetMute(1, None)

    def unmute(self) -> None:
        self._volume.SetMute(0, None)

    def toggle_mute(self) -> bool:
        muted = bool(self._volume.GetMute())
        self._volume.SetMute(0 if muted else 1, None)
        return not muted
