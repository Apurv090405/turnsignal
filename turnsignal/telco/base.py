from __future__ import annotations

from turnsignal.core.pipeline import Stage


class TelcoAdapter(Stage):
    """Marker base class for stages bridging audio to/from a telephony medium.

    Contract:
      - Publish AudioFrame(direction=INBOUND) for audio received from telco.
      - Subscribe to AudioFrame(direction=OUTBOUND) and forward to telco.
      - Publish EventFrame(HANGUP) when the call ends."""
