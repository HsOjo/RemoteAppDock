"""流式布局：子控件从左到右排列，超出宽度自动换行。

基于 Qt 官方 FlowLayout 示例移植，用于托盘图标区域按窗口宽度自动换行。
"""

from PySide6.QtCore import Qt, QMargins, QPoint, QRect, QSize
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget


class FlowLayout(QLayout):
    """从左到右排列、超出可用宽度自动换行的布局。"""

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = -1,
                 centered: bool = False):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._centered = centered
        self.setContentsMargins(QMargins(margin, margin, margin, margin))
        self.setSpacing(spacing)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(),
                      margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(),
                                  -margins.right(), -margins.bottom())
        spacing = self.spacing()

        # 先分行：把 item 按可用宽度切成若干行，记录每行的项与总宽度。
        rows: list[tuple[list[QLayoutItem], int]] = []
        current: list[QLayoutItem] = []
        line_width = 0
        for item in self._items:
            w = item.sizeHint().width()
            add_width = w if not current else line_width + spacing + w
            if add_width > effective.width() and current:
                rows.append((current, line_width))
                current = [item]
                line_width = w
            else:
                current.append(item)
                line_width = add_width
        if current:
            rows.append((current, line_width))

        # 再逐行定位；centered 时按行剩余空间计算水平居中偏移。
        y = effective.y()
        for row_items, row_width in rows:
            x = effective.x()
            if self._centered:
                x += max(0, (effective.width() - row_width) // 2)
            row_height = 0
            for item in row_items:
                item_size = item.sizeHint()
                if not test_only:
                    item.setGeometry(QRect(QPoint(x, y), item_size))
                x += item_size.width() + spacing
                row_height = max(row_height, item_size.height())
            y += row_height + spacing

        # 末行不需要行后 spacing，减回来。
        if rows:
            y -= spacing
        return y - rect.y() + margins.bottom()
