# Passport Photo Layout Nodes

这是一个 ComfyUI 自定义节点插件，用于把一张 `1040x1560` 的蓝底证件照排版到一张同尺寸的 `1040x1560` 4x6 英寸打印图中。

## 节点

- `One-Inch Passport Photo Sheet (12)`：25x35 mm，256x358 px，3列x4行，底图白色。
- `Two-Inch Passport Photo Sheet (4)`：35x49 mm，358x502 px，2列x2行，底图白色。
- `One-Inch Passport Photo Sheet (12, Custom Background)`：排版同上，底图颜色可自定义。
- `Two-Inch Passport Photo Sheet (4, Custom Background)`：排版同上，底图颜色可自定义。

所有节点都接收 `IMAGE` 和 `vertical_offset`，输出一张 `1040x1560` 的 RGB `IMAGE`。照片之间保留间隔，便于裁剪。

## 自定义背景色

带 `Custom Background` 的两个节点多出三个输入，用来控制底图（照片之间的间隔和四周留白）的颜色，证件照本身的背景不受影响。

- `background_mode`：`hex` 或 `rgb`，决定读取下面哪一个输入框，另一个会被忽略。
- `background_hex`：`#RRGGBB` 或 `#RGB`，`#` 可省略，默认 `#FFFFFF`。
- `background_rgb`：三个 `0-255` 的整数，逗号或空格分隔，默认 `255, 255, 255`。

填写格式不合法时节点会报错，而不是悄悄回退到白色。

## vertical_offset

输入图片先从 `1040x1560` 居中裁剪为 `1040x1456`，再缩放到证件照尺寸。

- 默认值 `0`：上下各裁52 px。
- 范围 `-52` 到 `52`。
- 负值保留更多头顶，正值保留更多肩部。

## 工作流接法

将节点69 `LayerUtility: ImageScaleByAspectRatio V2` 的输出分别连接到两个排版节点。两个排版节点后面各连接一个 `SaveImage` 即可。

## 打印要求

输出像素模板按 4x6 英寸、约260 DPI 设计。打印时应选择原始尺寸或 100% 比例，关闭“适应纸张”“填充裁剪”和自动缩放。普通 `IMAGE` 张量不携带可强制打印软件遵守的 DPI 设置，因此实际尺寸取决于打印软件的缩放设置。

## 开发测试

在 ComfyUI 使用的 Python 环境中执行：

```bash
pytest -q
```
