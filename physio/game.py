"""Public entry point for the Zero-Keyboard AI Physiotherapy System.

Implementation is organized in ``physio.game_parts`` by responsibility: setup,
runtime, gameplay, clinical session handling, and screens.
"""

from physio.game_parts.setup import SetupMixin
from physio.game_parts.runtime import RuntimeMixin
from physio.game_parts.gameplay import GameplayMixin
from physio.game_parts.clinical import ClinicalMixin
from physio.game_parts.screens import ScreenMixin


class PhysioSystem(SetupMixin, RuntimeMixin, GameplayMixin, ClinicalMixin, ScreenMixin):
    """Main application assembled from focused implementation mixins."""


def main():
    app = PhysioSystem()
    app.run()


if __name__ == "__main__":
    main()
