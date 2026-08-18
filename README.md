# Passport Photo Layout Nodes

这是一个 ComfyUI 自定义节点插件，用于把一张 `1040x1560` 的蓝底证件照排版到一张 `1200x1800` 的 4x6 英寸打印图中。

## 节点

- `One-Inch Passport Photo Sheet (12)`：25x35 mm，295x413 px，3列x4行。
- `Two-Inch Passport Photo Sheet (4)`：35x49 mm，413x579 px，2列x2行。

两个节点都接收 `IMAGE` 和 `vertical_offset`，输出一张 `1200x1800` 的 RGB `IMAGE`。照片之间保留白色间隔，便于裁剪。

## vertical_offset

输入图片先从 `1040x1560` 居中裁剪为 `1040x1456`，再缩放到证件照尺寸。

- 默认值 `0`：上下各裁52 px。
- 范围 `-52` 到 `52`。
- 负值保留更多头顶，正值保留更多肩部。

## 工作流接法

将节点69 `LayerUtility: ImageScaleByAspectRatio V2` 的输出分别连接到两个排版节点。两个排版节点后面各连接一个 `SaveImage` 即可。

## 打印要求

输出像素模板按 4x6 英寸、300 DPI 设计。打印时应选择原始尺寸或 100% 比例，关闭“适应纸张”“填充裁剪”和自动缩放。普通 `IMAGE` 张量不携带可强制打印软件遵守的 DPI 设置，因此实际尺寸取决于打印软件的缩放设置。

## 开发测试

在 ComfyUI 使用的 Python 环境中执行：

```bash
pytest -q
```
