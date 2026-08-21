import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nodes import (  # noqa: E402
    INPUT_HEIGHT,
    INPUT_WIDTH,
    NODE_CLASS_MAPPINGS,
    ONE_INCH_LAYOUT,
    OUTPUT_HEIGHT,
    OUTPUT_WIDTH,
    PassportPhotoOneInchSheet,
    PassportPhotoOneInchSheetCustomBackground,
    PassportPhotoTwoInchSheet,
    PassportPhotoTwoInchSheetCustomBackground,
    parse_hex_color,
    parse_rgb_color,
    resolve_background_color,
)


def _solid_image(batch=1, color=(0.2, 0.4, 0.8)):
    image = torch.empty((batch, INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=torch.float32)
    image[:] = torch.tensor(color, dtype=image.dtype)
    return image


def test_nodes_are_registered():
    assert NODE_CLASS_MAPPINGS["PassportPhotoOneInchSheet"] is PassportPhotoOneInchSheet
    assert NODE_CLASS_MAPPINGS["PassportPhotoTwoInchSheet"] is PassportPhotoTwoInchSheet
    assert (
        NODE_CLASS_MAPPINGS["PassportPhotoOneInchSheetCustomBackground"]
        is PassportPhotoOneInchSheetCustomBackground
    )
    assert (
        NODE_CLASS_MAPPINGS["PassportPhotoTwoInchSheetCustomBackground"]
        is PassportPhotoTwoInchSheetCustomBackground
    )


@pytest.mark.parametrize(
    "node_class",
    [PassportPhotoOneInchSheet, PassportPhotoTwoInchSheet],
)
def test_original_nodes_keep_their_inputs(node_class):
    assert list(node_class.INPUT_TYPES()["required"]) == ["image", "vertical_offset"]

    output = node_class().layout(_solid_image())[0]
    x, y = node_class.LAYOUT.positions[0]
    assert torch.all(output[:, :y, :x, :] == 1.0)


@pytest.mark.parametrize(
    "node_class",
    [
        PassportPhotoOneInchSheetCustomBackground,
        PassportPhotoTwoInchSheetCustomBackground,
    ],
)
def test_custom_background_nodes_expose_color_inputs(node_class):
    assert list(node_class.INPUT_TYPES()["required"]) == [
        "image",
        "vertical_offset",
        "background_mode",
        "background_hex",
        "background_rgb",
    ]


@pytest.mark.parametrize(
    "node_class, expected_count",
    [
        (PassportPhotoOneInchSheet, 12),
        (PassportPhotoTwoInchSheet, 4),
        (PassportPhotoOneInchSheetCustomBackground, 12),
        (PassportPhotoTwoInchSheetCustomBackground, 4),
    ],
)
def test_layout_dimensions_and_tile_content(node_class, expected_count):
    output = node_class().layout(_solid_image())[0]

    assert output.shape == (1, OUTPUT_HEIGHT, OUTPUT_WIDTH, 3)
    assert output.dtype == torch.float32
    assert output.min().item() >= 0.0
    assert output.max().item() <= 1.0

    layout = node_class.LAYOUT
    assert len(layout.positions) == expected_count
    for x, y in layout.positions:
        tile = output[:, y : y + layout.tile_height, x : x + layout.tile_width, :]
        assert torch.allclose(tile, _solid_image()[:, : layout.tile_height, : layout.tile_width, :])


def test_one_inch_gutters_are_white():
    output = PassportPhotoOneInchSheet().layout(_solid_image())[0]

    # Horizontal gutter between the first two columns.
    assert torch.all(output[:, 28:386, 323:347, :] == 1.0)
    # Vertical gutter between the first two rows.
    assert torch.all(output[:, 386:410, 67:323, :] == 1.0)


def test_two_inch_gutters_are_white():
    output = PassportPhotoTwoInchSheet().layout(_solid_image())[0]

    assert torch.all(output[:, 262:764, 504:536, :] == 1.0)
    assert torch.all(output[:, 764:796, 146:504, :] == 1.0)


def test_batch_is_preserved():
    image = torch.cat([_solid_image(color=(1.0, 0.0, 0.0)), _solid_image(color=(0.0, 1.0, 0.0))])
    output = PassportPhotoTwoInchSheet().layout(image)[0]

    assert output.shape[0] == 2
    assert torch.allclose(output[0, 262, 146], torch.tensor([1.0, 0.0, 0.0]))
    assert torch.allclose(output[1, 262, 146], torch.tensor([0.0, 1.0, 0.0]))


def test_vertical_offset_changes_crop_before_layout():
    source = torch.zeros((1, INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=torch.float32)
    source[:, :, :, 0] = torch.arange(INPUT_HEIGHT, dtype=torch.float32).view(1, INPUT_HEIGHT, 1) / INPUT_HEIGHT

    centered = PassportPhotoOneInchSheet().layout(source, vertical_offset=0)[0]
    shifted = PassportPhotoOneInchSheet().layout(source, vertical_offset=52)[0]

    assert shifted[0, 28, 112, 0] > centered[0, 28, 112, 0]


@pytest.mark.parametrize(
    "bad_image",
    [
        torch.zeros((1, 1559, 1040, 3)),
        torch.zeros((1, 1560, 1039, 3)),
        torch.zeros((1, 1560, 1040, 4)),
    ],
)
def test_invalid_input_is_rejected(bad_image):
    with pytest.raises(ValueError):
        PassportPhotoOneInchSheet().layout(bad_image)


def test_invalid_offset_is_rejected():
    with pytest.raises(ValueError):
        PassportPhotoOneInchSheet().layout(_solid_image(), vertical_offset=53)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("#FFFFFF", (255, 255, 255)),
        ("ffffff", (255, 255, 255)),
        ("#0af", (0, 170, 255)),
        ("  #12AB34 ", (18, 171, 52)),
    ],
)
def test_parse_hex_color(value, expected):
    assert parse_hex_color(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("255, 255, 255", (255, 255, 255)),
        ("0 128 255", (0, 128, 255)),
        (" 12,  34 ,56 ", (12, 34, 56)),
    ],
)
def test_parse_rgb_color(value, expected):
    assert parse_rgb_color(value) == expected


@pytest.mark.parametrize("value", ["#12345", "xyzxyz", "", "#"])
def test_invalid_hex_color_is_rejected(value):
    with pytest.raises(ValueError):
        parse_hex_color(value)


@pytest.mark.parametrize("value", ["255,255", "256,0,0", "a,b,c", "1,2,3,4", "-1,0,0"])
def test_invalid_rgb_color_is_rejected(value):
    with pytest.raises(ValueError):
        parse_rgb_color(value)


def test_background_mode_selects_one_input():
    # The field the mode does not select is never parsed.
    assert resolve_background_color("hex", "#1a2b3c", "not a color") == (26, 43, 60)
    assert resolve_background_color("rgb", "not a color", "10, 20, 30") == (10, 20, 30)
    with pytest.raises(ValueError):
        resolve_background_color("cmyk", "#ffffff", "255, 255, 255")


@pytest.mark.parametrize(
    "background_mode, background_hex, background_rgb, expected",
    [
        ("hex", "#3366CC", "255, 255, 255", (0x33 / 255, 0x66 / 255, 0xCC / 255)),
        ("rgb", "#FFFFFF", "51, 102, 204", (51 / 255, 102 / 255, 204 / 255)),
    ],
)
def test_custom_background_fills_gutters_only(
    background_mode, background_hex, background_rgb, expected
):
    output = PassportPhotoOneInchSheetCustomBackground().layout(
        _solid_image(),
        background_mode=background_mode,
        background_hex=background_hex,
        background_rgb=background_rgb,
    )[0]

    gutter = output[:, 386:410, 67:323, :]
    assert torch.allclose(gutter, torch.tensor(expected, dtype=output.dtype), atol=1e-6)

    # Tile pixels keep the source photo background.
    layout = PassportPhotoOneInchSheetCustomBackground.LAYOUT
    x, y = layout.positions[0]
    tile = output[:, y : y + layout.tile_height, x : x + layout.tile_width, :]
    assert torch.allclose(tile, _solid_image()[:, : layout.tile_height, : layout.tile_width, :])


def test_invalid_background_input_is_rejected():
    with pytest.raises(ValueError):
        PassportPhotoOneInchSheetCustomBackground().layout(
            _solid_image(), background_mode="hex", background_hex="#nothex"
        )
