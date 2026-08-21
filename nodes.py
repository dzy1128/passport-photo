"""Passport photo sheet nodes for ComfyUI."""

import re
from dataclasses import dataclass

import torch
import torch.nn.functional as functional


INPUT_WIDTH = 1040
INPUT_HEIGHT = 1560
CROP_HEIGHT = 1456
CROP_TOP = 52
OUTPUT_WIDTH = 1040
OUTPUT_HEIGHT = 1560
MIN_VERTICAL_OFFSET = -52
MAX_VERTICAL_OFFSET = 52

WHITE = (255, 255, 255)
BACKGROUND_MODES = ("hex", "rgb")
DEFAULT_BACKGROUND_HEX = "#FFFFFF"
DEFAULT_BACKGROUND_RGB = "255, 255, 255"


@dataclass(frozen=True)
class LayoutSpec:
    """Fixed print layout for one passport-photo size."""

    tile_width: int
    tile_height: int
    positions: tuple[tuple[int, int], ...]


ONE_INCH_LAYOUT = LayoutSpec(
    tile_width=256,
    tile_height=358,
    positions=tuple(
        (x, y)
        for y in (28, 410, 792, 1174)
        for x in (67, 347, 627)
    ),
)

TWO_INCH_LAYOUT = LayoutSpec(
    tile_width=358,
    tile_height=502,
    positions=tuple(
        (x, y)
        for y in (262, 796)
        for x in (146, 536)
    ),
)


def parse_hex_color(value: str) -> tuple[int, int, int]:
    """Parse ``#RRGGBB`` or ``#RGB`` (the leading ``#`` is optional)."""

    if not isinstance(value, str):
        raise TypeError("background_hex must be a string")

    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(channel * 2 for channel in text)
    if len(text) != 6 or re.fullmatch(r"[0-9a-fA-F]{6}", text) is None:
        raise ValueError(
            f"background_hex must look like #RRGGBB or #RGB (received {value!r})"
        )

    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))


def parse_rgb_color(value: str) -> tuple[int, int, int]:
    """Parse three ``0-255`` channels separated by commas or whitespace."""

    if not isinstance(value, str):
        raise TypeError("background_rgb must be a string")

    parts = [part for part in re.split(r"[,\s]+", value.strip()) if part]
    if len(parts) != 3:
        raise ValueError(
            f"background_rgb must have 3 channels like 255, 255, 255 (received {value!r})"
        )

    channels = []
    for part in parts:
        if re.fullmatch(r"\d{1,3}", part) is None or not 0 <= int(part) <= 255:
            raise ValueError(
                f"background_rgb channels must be integers between 0 and 255 (received {part!r})"
            )
        channels.append(int(part))

    return tuple(channels)


def resolve_background_color(
    background_mode: str, background_hex: str, background_rgb: str
) -> tuple[int, int, int]:
    """Return the sheet background color from whichever input the mode selects."""

    if background_mode == "hex":
        return parse_hex_color(background_hex)
    if background_mode == "rgb":
        return parse_rgb_color(background_rgb)
    raise ValueError(
        f"background_mode must be one of {BACKGROUND_MODES} (received {background_mode!r})"
    )


class _PassportPhotoLayoutNode:
    """Shared implementation for the fixed one-inch and two-inch layouts."""

    LAYOUT: LayoutSpec

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "vertical_offset": (
                    "INT",
                    {
                        "default": 0,
                        "min": MIN_VERTICAL_OFFSET,
                        "max": MAX_VERTICAL_OFFSET,
                        "step": 1,
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "layout"
    CATEGORY = "Passport Photo/Layout"

    def layout(self, image: torch.Tensor, vertical_offset: int = 0):
        return (self._compose(image, vertical_offset, WHITE),)

    def _compose(
        self,
        image: torch.Tensor,
        vertical_offset: int,
        background: tuple[int, int, int],
    ) -> torch.Tensor:
        self._validate_input(image, vertical_offset)

        offset = int(vertical_offset)
        crop_top = CROP_TOP + offset
        cropped = image[:, crop_top : crop_top + CROP_HEIGHT, :, :]

        # ComfyUI IMAGE tensors are BHWC; interpolation expects BCHW.
        working = cropped.to(dtype=torch.float32).permute(0, 3, 1, 2)
        resized = functional.interpolate(
            working,
            size=(self.LAYOUT.tile_height, self.LAYOUT.tile_width),
            mode="bicubic",
            align_corners=False,
            antialias=True,
        )
        tile = resized.permute(0, 2, 3, 1).clamp(0.0, 1.0)

        canvas = torch.empty(
            (
                image.shape[0],
                OUTPUT_HEIGHT,
                OUTPUT_WIDTH,
                3,
            ),
            dtype=tile.dtype,
            device=tile.device,
        )
        canvas[:] = torch.tensor(
            [channel / 255.0 for channel in background],
            dtype=tile.dtype,
            device=tile.device,
        )
        for x, y in self.LAYOUT.positions:
            canvas[
                :, y : y + self.LAYOUT.tile_height, x : x + self.LAYOUT.tile_width, :
            ] = tile

        return canvas

    @staticmethod
    def _validate_input(image: torch.Tensor, vertical_offset: int) -> None:
        if not isinstance(image, torch.Tensor):
            raise TypeError("image must be a ComfyUI IMAGE tensor")
        if image.ndim != 4:
            raise ValueError("image must have shape [batch, height, width, channels]")

        _, height, width, channels = image.shape
        if (height, width) != (INPUT_HEIGHT, INPUT_WIDTH):
            raise ValueError(
                "passport photo input must be 1040x1560 pixels "
                f"(received {width}x{height})"
            )
        if channels != 3:
            raise ValueError(f"passport photo input must have 3 RGB channels (received {channels})")
        if not isinstance(vertical_offset, int):
            raise TypeError("vertical_offset must be an integer")
        if not MIN_VERTICAL_OFFSET <= vertical_offset <= MAX_VERTICAL_OFFSET:
            raise ValueError(
                f"vertical_offset must be between {MIN_VERTICAL_OFFSET} and {MAX_VERTICAL_OFFSET}"
            )


class _PassportPhotoCustomBackgroundNode(_PassportPhotoLayoutNode):
    """Same layout, but the sheet background color is chosen by the user."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "vertical_offset": (
                    "INT",
                    {
                        "default": 0,
                        "min": MIN_VERTICAL_OFFSET,
                        "max": MAX_VERTICAL_OFFSET,
                        "step": 1,
                    },
                ),
                "background_mode": (list(BACKGROUND_MODES), {"default": "hex"}),
                "background_hex": ("STRING", {"default": DEFAULT_BACKGROUND_HEX}),
                "background_rgb": ("STRING", {"default": DEFAULT_BACKGROUND_RGB}),
            }
        }

    def layout(
        self,
        image: torch.Tensor,
        vertical_offset: int = 0,
        background_mode: str = "hex",
        background_hex: str = DEFAULT_BACKGROUND_HEX,
        background_rgb: str = DEFAULT_BACKGROUND_RGB,
    ):
        # Only the selected mode's field is parsed, so the other one may hold anything.
        background = resolve_background_color(
            background_mode, background_hex, background_rgb
        )
        return (self._compose(image, vertical_offset, background),)


class PassportPhotoOneInchSheet(_PassportPhotoLayoutNode):
    """Create a 12-up one-inch passport photo sheet."""

    LAYOUT = ONE_INCH_LAYOUT


class PassportPhotoTwoInchSheet(_PassportPhotoLayoutNode):
    """Create a 4-up two-inch passport photo sheet."""

    LAYOUT = TWO_INCH_LAYOUT


class PassportPhotoOneInchSheetCustomBackground(_PassportPhotoCustomBackgroundNode):
    """Create a 12-up one-inch sheet on a user-defined background color."""

    LAYOUT = ONE_INCH_LAYOUT


class PassportPhotoTwoInchSheetCustomBackground(_PassportPhotoCustomBackgroundNode):
    """Create a 4-up two-inch sheet on a user-defined background color."""

    LAYOUT = TWO_INCH_LAYOUT


NODE_CLASS_MAPPINGS = {
    "PassportPhotoOneInchSheet": PassportPhotoOneInchSheet,
    "PassportPhotoTwoInchSheet": PassportPhotoTwoInchSheet,
    "PassportPhotoOneInchSheetCustomBackground": PassportPhotoOneInchSheetCustomBackground,
    "PassportPhotoTwoInchSheetCustomBackground": PassportPhotoTwoInchSheetCustomBackground,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PassportPhotoOneInchSheet": "One-Inch Passport Photo Sheet (12)",
    "PassportPhotoTwoInchSheet": "Two-Inch Passport Photo Sheet (4)",
    "PassportPhotoOneInchSheetCustomBackground": "One-Inch Passport Photo Sheet (12, Custom Background)",
    "PassportPhotoTwoInchSheetCustomBackground": "Two-Inch Passport Photo Sheet (4, Custom Background)",
}
