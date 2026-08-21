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
    PassportPhotoTwoInchSheet,
)


def _solid_image(batch=1, color=(0.2, 0.4, 0.8)):
    image = torch.empty((batch, INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=torch.float32)
    image[:] = torch.tensor(color, dtype=image.dtype)
    return image


def test_nodes_are_registered():
    assert NODE_CLASS_MAPPINGS["PassportPhotoOneInchSheet"] is PassportPhotoOneInchSheet
    assert NODE_CLASS_MAPPINGS["PassportPhotoTwoInchSheet"] is PassportPhotoTwoInchSheet


@pytest.mark.parametrize(
    "node_class, expected_count",
    [
        (PassportPhotoOneInchSheet, 12),
        (PassportPhotoTwoInchSheet, 4),
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
