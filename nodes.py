"""Passport photo sheet nodes for ComfyUI."""

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
        for x in (74, 354, 634)
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

        canvas = torch.ones(
            (
                image.shape[0],
                OUTPUT_HEIGHT,
                OUTPUT_WIDTH,
                3,
            ),
            dtype=tile.dtype,
            device=tile.device,
        )
        for x, y in self.LAYOUT.positions:
            canvas[
                :, y : y + self.LAYOUT.tile_height, x : x + self.LAYOUT.tile_width, :
            ] = tile

        return (canvas,)

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


class PassportPhotoOneInchSheet(_PassportPhotoLayoutNode):
    """Create a 12-up one-inch passport photo sheet."""

    LAYOUT = ONE_INCH_LAYOUT


class PassportPhotoTwoInchSheet(_PassportPhotoLayoutNode):
    """Create a 4-up two-inch passport photo sheet."""

    LAYOUT = TWO_INCH_LAYOUT


NODE_CLASS_MAPPINGS = {
    "PassportPhotoOneInchSheet": PassportPhotoOneInchSheet,
    "PassportPhotoTwoInchSheet": PassportPhotoTwoInchSheet,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PassportPhotoOneInchSheet": "One-Inch Passport Photo Sheet (12)",
    "PassportPhotoTwoInchSheet": "Two-Inch Passport Photo Sheet (4)",
}
