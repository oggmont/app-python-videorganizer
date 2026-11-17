"""The right section: destination folders (section 3), the search field (S-1..S-8) and the
recently used folders (RF-1..RF-8).

Both lists, the recent folders on top and all folders below, share one keyboard cursor
and one selected folder. Rows hold the folder's full path, so the same folder in both
lists is one folder: selecting it in one list highlights it in the other too.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeyEvent, QKeySequence, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileIconProvider,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from ..fileops import filter_names, name_matches
from ..theme import (
    CURSOR,
    HOVER,
    MOVING,
    MUTED,
    RECENT_ACCENT,
    RECENT_BG,
    RECENT_HINT,
    RECENT_HOVER,
    RECENT_SEPARATOR,
    SELECTED,
    SEPARATOR,
    TEXT,
)
from .common import EditField, ElidedLabel, make_button

ROW_HEIGHT = 35
RECENT_ROW_HEIGHT = 30
SELECTED_HINT = "selected · Enter / click to move"
MOVING_HINT = "moving…"
PATH_ROLE = Qt.ItemDataRole.UserRole
HINT_ROLE = Qt.ItemDataRole.UserRole + 1


def _folder_icon() -> QIcon:
    icon = QFileIconProvider().icon(QFileIconProvider.IconType.Folder)
    return icon if not icon.isNull() else QIcon()


def _search_icon() -> QIcon:
    """A magnifying glass, drawn at 2x so it's sharp on Retina screens."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(MUTED))
    pen.setWidthF(3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawEllipse(QRectF(6, 6, 14, 14))
    painter.drawLine(QPointF(18, 18), QPointF(25, 25))
    painter.end()
    return QIcon(pixmap)


class FolderDelegate(QStyledItemDelegate):
    """Paints each row: fill for the selected folder, outline for the keyboard cursor (F-6).
    Rows of the recent list also get a violet tint and a stripe on the left (RF-2)."""

    def __init__(self, folder_list: FolderList):
        super().__init__(folder_list)
        self._list = folder_list

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        # Width 0: the list makes every row as wide as itself. A real width would be too wide
        # once the scroll bar appears, and the hint on the right would be cut off.
        return QSize(0, self._list.row_height)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        lst = self._list
        rect = option.rect
        recent = lst.recent
        selected = lst.armed is not None and index.data(PATH_ROLE) == str(lst.armed)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if selected:
            painter.fillRect(rect, QColor(MOVING if lst.moving else SELECTED))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor(RECENT_HOVER if recent else HOVER))
        elif recent:
            painter.fillRect(rect, QColor(RECENT_BG))
        if recent:
            painter.fillRect(QRect(rect.left(), rect.top(), 3, rect.height()), QColor(RECENT_ACCENT))
        painter.setPen(QColor(RECENT_SEPARATOR if recent else SEPARATOR))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        icon = index.data(Qt.ItemDataRole.DecorationRole)
        size = 16 if recent else 18
        icon_rect = QRect(rect.left() + 14, rect.center().y() - size // 2, size, size)
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, icon_rect)

        small = QFont(option.font)
        small.setPointSizeF(max(8.0, option.font.pointSizeF() - 2))
        if selected:
            hint, hint_color = (MOVING_HINT if lst.moving else SELECTED_HINT), "#dbe8ff"
        else:
            hint, hint_color = str(index.data(HINT_ROLE) or ""), RECENT_HINT  # RF-5: where it is
        hint_width = 0
        if hint:
            painter.setFont(small)
            hint_width = painter.fontMetrics().horizontalAdvance(hint) + 16

        text_left = icon_rect.right() + 10
        text_rect = QRect(text_left, rect.top(), max(0, rect.right() - text_left - hint_width - 8), rect.height())
        painter.setFont(option.font)
        painter.setPen(QColor("#ffffff" if selected else TEXT))
        name = painter.fontMetrics().elidedText(
            str(index.data(Qt.ItemDataRole.DisplayRole)), Qt.TextElideMode.ElideMiddle, text_rect.width()
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, name)

        if hint:
            painter.setFont(small)
            painter.setPen(QColor(hint_color))
            hint_rect = QRect(rect.right() - hint_width - 6, rect.top(), hint_width, rect.height())
            painter.drawText(hint_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, hint)

        if index.row() == lst.currentRow():
            pen = QPen(QColor(CURSOR))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
        painter.restore()


class FolderList(QListWidget):
    """Folder list where every mouse press counts as one click.

    The second press of a double-click arrives as a double-click event, so it's
    treated as a second click: a double-click is "select, then move" (M-3).
    Qt's own selection isn't used: the selected folder is `armed`, and the keyboard
    cursor is the current row, which the FolderPanel sets.
    """

    folder_clicked = Signal(int)

    def __init__(self, recent: bool = False):
        super().__init__()
        self.recent = recent
        self.row_height = RECENT_ROW_HEIGHT if recent else ROW_HEIGHT
        self.setObjectName("recentList" if recent else "folderList")
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # keys are handled by window shortcuts (K-1)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        if recent:  # always fully shown: at most a few rows (RF-1)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(FolderDelegate(self))
        font = self.font()
        font.setPixelSize(13 if recent else 14)
        self.setFont(font)
        self.armed: Path | None = None
        self.moving = False
        self._icon = _folder_icon()
        self.currentRowChanged.connect(lambda _row: self.viewport().update())

    def set_rows(self, rows: list[tuple[Path, str]]) -> None:
        """One row per (folder, hint). The row shows the folder's name."""
        self.clear()
        for path, hint in rows:
            item = QListWidgetItem(self._icon, path.name)
            item.setData(PATH_ROLE, str(path))
            item.setData(HINT_ROLE, hint)
            if self.recent:
                item.setToolTip(str(path))
            self.addItem(item)
        if self.recent:
            self.setFixedHeight(self.count() * self.row_height)

    def path_at(self, row: int) -> Path | None:
        item = self.item(row) if row >= 0 else None
        return Path(item.data(PATH_ROLE)) if item is not None else None

    def row_of(self, path: Path) -> int:
        target = str(path)
        return next((i for i in range(self.count()) if self.item(i).data(PATH_ROLE) == target), -1)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            self.folder_clicked.emit(index.row())
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        self.mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        event.accept()


class SearchField(QLineEdit):
    """The search field above the folders (S-1).

    It keeps the keyboard focus, so typing always filters the folders (S-2). A text field
    normally keeps keys like ←/→, ⌘Z or ⌘⌫ for itself. This one lets the window's shortcut
    keys through, so the arrows, Enter, Esc, ⌘Z and ⌘⌫ work as before (S-5, K-1).
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("searchField")
        self.setPlaceholderText("Type a folder name to filter the list…")
        self.setClearButtonEnabled(True)
        self.addAction(_search_icon(), QLineEdit.ActionPosition.LeadingPosition)
        self._command_keys: set[tuple[int, int]] = set()

    def add_command_key(self, sequence: QKeySequence) -> None:
        """A key that belongs to a window shortcut, not to the text."""
        combo = sequence[0]
        self._command_keys.add((int(combo.key().value), combo.keyboardModifiers().value))

    def is_command_key(self, event: QKeyEvent) -> bool:
        modifiers = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier  # macOS sets it on the arrows
        return (event.key(), modifiers.value) in self._command_keys

    def event(self, event) -> bool:
        # Before a key press, Qt asks the focused widget whether it wants the key for itself
        # (ShortcutOverride). Saying no lets the window's shortcut run instead.
        if event.type() == QEvent.Type.ShortcutOverride and self.is_command_key(event):
            event.ignore()
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # S-9: ⌫ (also fn ⌫ and ⌥⌫) clears the whole search, not one letter. ⌘⌫ never gets
        # here: it's the Delete shortcut (D-1).
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete) and not (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.clear()
            return
        super().keyPressEvent(event)


class FolderPanel(QWidget):
    change_dest_clicked = Signal()
    folder_clicked = Signal(object)  # the folder's Path
    filter_changed = Signal()
    new_folder_clicked = Signal()
    create_requested = Signal(str)
    new_folder_mode_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._creating = False
        self._root: Path | None = None
        self._listed_root: Path | None = None  # the root folder `_names` were listed from
        self._names: list[str] = []  # every folder in the root folder, before the search
        self._recent: list[Path] = []
        self._armed: Path | None = None
        self._empty_message = ""
        self.setObjectName("rightPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        title = QLabel("Folders")
        title.setObjectName("folderTitle")
        self._path_label = ElidedLabel(name="mutedLabel")
        self.change_button = make_button(
            "Change", self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), small=True
        )
        self.change_button.setToolTip("Change destination folder")
        self.change_button.clicked.connect(self.change_dest_clicked)
        self.new_folder_button = make_button(
            "New folder", self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), small=True
        )
        self.new_folder_button.setToolTip("Create a folder in this list (⌘⇧N)")
        self.new_folder_button.setEnabled(False)
        self.new_folder_button.clicked.connect(self.new_folder_clicked)

        header = QWidget()
        header.setObjectName("folderHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        header_layout.setSpacing(10)
        header_layout.addWidget(title)
        header_layout.addWidget(self._path_label, 1)
        header_layout.addWidget(self.new_folder_button)
        header_layout.addWidget(self.change_button)

        # New folder row (F-9): hidden until New folder is pressed.
        caption = QLabel("New folder")
        caption.setObjectName("mutedLabel")
        self.new_folder_field = EditField()
        self.new_folder_field.setPlaceholderText("Folder name")
        self.new_folder_field.setProperty("editing", True)  # blue border, like the rename field while editing
        self.new_folder_field.returnPressed.connect(self._submit_new_folder)
        self.new_folder_field.cancel_requested.connect(self.cancel_new_folder)
        self.create_button = make_button("Create", small=True, name="okButton")
        self.create_button.clicked.connect(self._submit_new_folder)
        cancel_button = make_button("Cancel", small=True)
        cancel_button.clicked.connect(self.cancel_new_folder)
        self._new_folder_row = QWidget()
        self._new_folder_row.setObjectName("newFolderRow")
        self._new_folder_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QHBoxLayout(self._new_folder_row)
        row_layout.setContentsMargins(14, 8, 14, 8)
        row_layout.setSpacing(8)
        row_layout.addWidget(caption)
        row_layout.addWidget(self.new_folder_field, 1)
        row_layout.addWidget(self.create_button)
        row_layout.addWidget(cancel_button)
        self._new_folder_row.hide()

        # Search (S-1): always there, always holding the text cursor.
        self.search_field = SearchField()
        self.search_field.textChanged.connect(self._on_search_changed)
        search_row = QWidget()
        search_row.setObjectName("searchRow")
        search_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(14, 8, 14, 8)
        search_layout.addWidget(self.search_field)

        # Recently used folders (RF-1, RF-2): a tinted block above the folder list.
        recent_title = QLabel("RECENTLY USED")
        recent_title.setObjectName("recentTitle")
        self.recent_list = FolderList(recent=True)
        self.recent_list.folder_clicked.connect(lambda row: self._on_row_clicked(self.recent_list, row))
        self._recent_box = QWidget()
        self._recent_box.setObjectName("recentBox")
        self._recent_box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        recent_layout = QVBoxLayout(self._recent_box)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(0)
        recent_layout.addWidget(recent_title)
        recent_layout.addWidget(self.recent_list)
        self._recent_box.hide()

        self._list_title = QLabel()
        self._list_title.setObjectName("listTitle")
        self.list = FolderList()
        self.list.folder_clicked.connect(lambda row: self._on_row_clicked(self.list, row))

        self._empty_label = QLabel()
        self._empty_label.setObjectName("mutedLabel")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.hide()

        hint_items = [
            (["abc"], "search"), (["←", "→"], "video"), (["↑", "↓"], "folder"), (["Enter"], "select"),
            (["Enter"], "again:&nbsp;move"), (["⌥↑", "⌥↓"], "top/bottom"), (["⌘↵"], "open&nbsp;folder"),
            (["⌘↑"], "parent"),
            (["⌘⇧N"], "new&nbsp;folder"), (["Esc"], "clear"), (["⌘Z"], "undo"), (["⌘⌫"], "delete"),
        ]
        # Inside an item everything is joined with &nbsp;, so lines only wrap between items.
        hints = QLabel(" &nbsp; ".join("".join(_key(k) for k in keys) + label for keys, label in hint_items))
        hints.setObjectName("keyHints")
        hints.setTextFormat(Qt.TextFormat.RichText)
        hints.setContentsMargins(14, 8, 14, 8)
        hints.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self._new_folder_row)
        layout.addWidget(search_row)
        layout.addWidget(self._recent_box)
        layout.addWidget(self._list_title)
        layout.addWidget(self._empty_label)
        layout.addWidget(self.list, 1)
        layout.addWidget(hints)
        self.set_root(None)
        self._rebuild()

    # -- new folder (F-8..F-14) --------------------------------------------------
    @property
    def creating(self) -> bool:
        return self._creating

    def start_new_folder(self) -> None:
        if self._creating:
            self.new_folder_field.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._creating = True
        self.new_folder_field.clear()
        self._new_folder_row.show()
        self.new_folder_field.setFocus(Qt.FocusReason.OtherFocusReason)
        self.new_folder_mode_changed.emit(True)

    def cancel_new_folder(self) -> None:
        """Hide the row without creating anything (F-12). Also used after a successful create."""
        if not self._creating:
            return
        self._creating = False
        self.new_folder_field.clearFocus()
        self.new_folder_field.clear()
        self._new_folder_row.hide()
        self.new_folder_mode_changed.emit(False)

    def _submit_new_folder(self) -> None:
        if self._creating:
            self.create_requested.emit(self.new_folder_field.text())

    # -- search (S-1..S-8) ---------------------------------------------------------
    def search_text(self) -> str:
        return self.search_field.text()

    def clear_search(self) -> None:
        self.search_field.clear()

    def select_search_text(self) -> None:
        """S-6: after a move the text stays, selected, so typing a new name replaces it."""
        self.search_field.selectAll()

    def focus_search(self) -> None:
        self.search_field.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_search_changed(self, text: str) -> None:
        if text.strip():
            self._rebuild()  # S-4: the cursor goes to the best match
        else:
            self._rebuild(*self._cursor_target())  # cleared: the cursor stays on its folder
        self.filter_changed.emit()

    # -- location and folders --------------------------------------------------------
    def set_root(self, path: Path | None) -> None:
        self._root = path
        self._path_label.set_full_text(str(path) if path else "No folder chosen")

    def set_folders(self, names: list[str], message_if_empty: str = "", cursor_on: str | None = None) -> None:
        """Show `names`, the folders inside the root folder. The cursor goes to `cursor_on`,
        or stays on the same folder when it's still listed, or starts at the top (K-5).
        The selection is cleared."""
        if cursor_on is not None:
            target = (self.list, self._root / cursor_on if self._root is not None and cursor_on else None)
        elif self._root == self._listed_root:
            target = self._cursor_target()  # the same folder again: the cursor stays where it is
        else:
            target = (None, None)  # another folder: start at the top
        self._listed_root = self._root
        self._names = list(names)
        self._empty_message = message_if_empty
        self._armed = None
        self._rebuild(*target)

    def set_recent(self, folders: list[Path]) -> None:
        """The recently used folders, newest first (RF-1). The cursor stays on its folder."""
        self._recent = list(folders)
        self._rebuild(*self._cursor_target())

    def _location_hint(self, folder: Path) -> str:
        """RF-5: say where a recent folder is when it isn't in the folder list below."""
        parent = folder.parent
        if parent == self._root:
            return ""
        return f"in {parent.name or parent}"

    def _rebuild(self, cursor_list: FolderList | None = None, cursor_path: Path | None = None) -> None:
        """Fill both lists from the folders, the recent folders and the search text."""
        text = self.search_field.text()
        query = text.strip()
        recent = [p for p in self._recent if name_matches(p.name, text)]
        names = filter_names(self._names, text)
        self.recent_list.set_rows([(p, self._location_hint(p)) for p in recent])
        self._recent_box.setVisible(bool(recent))
        root = self._root
        self.list.set_rows([(root / name, "") for name in names] if root is not None else [])
        for lst in (self.recent_list, self.list):
            lst.armed = self._armed

        if root is None:
            self._list_title.setText("ALL FOLDERS")
        elif query:
            self._list_title.setText(f"{len(names)} OF {len(self._names)} FOLDERS MATCH")
        else:
            self._list_title.setText(f"ALL FOLDERS · {len(self._names)}")
        if names:
            self._empty_label.hide()
            self.list.show()
        else:
            if query and self._names:
                self._empty_label.setText(f"No folder here matches “{query}”.\nEsc clears the search.")
            else:
                self._empty_label.setText(self._empty_message or "No folders here.")
            self._empty_label.show()
            self.list.hide()
        self._place_cursor(cursor_list, cursor_path)

    # -- cursor and selection --------------------------------------------------
    def _cursor_target(self) -> tuple[FolderList | None, Path | None]:
        for lst in (self.recent_list, self.list):
            row = lst.currentRow()
            if row >= 0:
                return lst, lst.path_at(row)
        return None, None

    def _place_cursor(self, lst: FolderList | None, path: Path | None) -> None:
        """Put the cursor on `path` in `lst`, else on the first folder of the list (K-5)."""
        if lst is not None and path is not None:
            # A folder that dropped out of the recent folders may still be in the folder list.
            for target in (lst, self.list) if lst is self.recent_list else (lst,):
                row = target.row_of(path)
                if row >= 0:
                    self._set_cursor(target, row)
                    return
        if self.list.count():
            self._set_cursor(self.list, 0)
        elif self.recent_list.count():
            self._set_cursor(self.recent_list, 0)
        else:
            self._set_cursor(None, -1)

    def _set_cursor(self, lst: FolderList | None, row: int) -> None:
        for other in (self.recent_list, self.list):
            if other is not lst:
                other.setCurrentRow(-1)
        if lst is not None:
            lst.setCurrentRow(row)
            lst.scrollToItem(lst.item(row))

    def _on_row_clicked(self, lst: FolderList, row: int) -> None:
        folder = lst.path_at(row)
        if folder is not None:
            self._set_cursor(lst, row)
            self.folder_clicked.emit(folder)

    def armed_folder(self) -> Path | None:
        return self._armed

    def armed_name(self) -> str | None:
        return self._armed.name if self._armed is not None else None

    def cursor_folder(self) -> Path | None:
        return self._cursor_target()[1]

    def cursor_name(self) -> str | None:
        folder = self.cursor_folder()
        return folder.name if folder is not None else None

    def cursor_in_recent(self) -> bool:
        return self.recent_list.currentRow() >= 0

    def set_armed(self, folder: Path | None) -> None:
        self._armed = folder
        for lst in (self.recent_list, self.list):
            lst.armed = folder
            lst.viewport().update()

    def clear_armed(self) -> None:
        self.set_armed(None)

    def set_moving(self, moving: bool) -> None:
        for lst in (self.recent_list, self.list):
            lst.moving = moving
            lst.viewport().update()

    def move_cursor(self, delta: int) -> bool:
        """Move the keyboard cursor through the recent folders and then the folder list,
        as one list. It stops at the ends (K-5). Returns True if it moved."""
        recent_count = self.recent_list.count()
        total = recent_count + self.list.count()
        if total == 0:
            return False
        if self.recent_list.currentRow() >= 0:
            current = self.recent_list.currentRow()
        elif self.list.currentRow() >= 0:
            current = recent_count + self.list.currentRow()
        else:
            current = -1
        if current < 0:
            new = recent_count if self.list.count() else 0
        else:
            new = max(0, min(total - 1, current + delta))
        if new == current:
            return False
        if new < recent_count:
            self._set_cursor(self.recent_list, new)
        else:
            self._set_cursor(self.list, new - recent_count)
        return True

    def row_count(self) -> int:
        """Rows the cursor can be on: the recent folders and the folder list."""
        return self.recent_list.count() + self.list.count()

    def names(self) -> list[str]:
        """The folders shown in the folder list (after the search)."""
        return [self.list.item(i).text() for i in range(self.list.count())]

    def recent_names(self) -> list[str]:
        """The recent folders shown (after the search)."""
        return [self.recent_list.item(i).text() for i in range(self.recent_list.count())]


def _key(text: str) -> str:
    return (
        '<span style="background-color:#3a3a3a; color:#eeeeee; font-size:11px">'
        f"&nbsp;{text}&nbsp;</span>&nbsp;"
    )
