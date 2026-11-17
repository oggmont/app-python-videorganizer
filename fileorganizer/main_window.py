"""The main window. It holds the app state and connects the panels.

Requirement IDs refer to REQUIREMENTS.md.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QMainWindow, QVBoxLayout, QWidget

from .fileops import (
    MoveError,
    FolderError,
    RenameError,
    TrashError,
    TrashFunction,
    Video,
    create_folder,
    existing_folders,
    list_folders,
    list_videos,
    move_verified,
    rename_video,
    trash_verified,
)
from .movelog import MoveLog, default_log_path
from .widgets.common import GripSplitter
from .widgets.folder_panel import FolderPanel
from .widgets.log_panel import DEFAULT_HEIGHT as LOG_HEIGHT
from .widgets.log_panel import LogPanel
from .widgets.player_panel import PlayerPanel
from .widgets.status_line import MESSAGE_MS, StatusLine

DELETE_CONFIRM_MS = 5000  # D-5: an unconfirmed delete is cancelled after 5 s
RECENT_SHOWN = 5  # RF-1
RECENT_KEPT = 10  # RF-4: a few more are remembered, so 5 are still shown when some folders are gone


@dataclass(frozen=True)
class UndoEntry:
    """One move or delete that Undo can reverse (U-1)."""

    kind: str          # "move" or "delete"
    original: Path     # where the video was in the source folder
    current: Path      # where it is now: in a destination folder, or in the Trash
    size: int
    place: str         # for messages: "Beach" or "the Trash"

    @property
    def name(self) -> str:
        return self.original.name


class _JobSignals(QObject):
    finished = Signal(object, object)  # (resulting Path or None, error message or None)


class FileJob(QRunnable):
    """Runs one file operation on a worker thread, so a slow copy between drives
    doesn't freeze the window (M-16)."""

    def __init__(self, work: Callable[[], Path]):
        super().__init__()
        self.setAutoDelete(False)
        self._work = work
        self.signals = _JobSignals()

    def run(self) -> None:
        try:
            path, error = self._work(), None
        except (MoveError, TrashError) as e:
            path, error = None, str(e)
        except Exception as e:  # never let a worker thread die silently
            path, error = None, f"Unexpected error: {e}"
        self.signals.finished.emit(path, error)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: QSettings | None = None,
        log_path: Path | None = None,
        trash: TrashFunction | None = None,
    ):
        super().__init__()
        self.setWindowTitle("Video File Organizer")
        self.settings = settings or QSettings()
        self.move_log = MoveLog(log_path or default_log_path())
        if trash is None:
            from .trash import move_to_trash

            trash = move_to_trash
        self._trash = trash

        self.source: Path | None = None
        self.dest: Path | None = None
        self.recent: list[Path] = self._load_recent()  # folders videos were moved into, newest first
        self.videos: list[Video] = []
        self.index = 0
        self.busy = False  # a move, undo or delete is running (M-14)
        self._ignore_activations_until = 0.0
        self._job: FileJob | None = None
        self._job_kind = ""
        self._job_context: tuple = ()
        self._undo: list[UndoEntry] = []
        self._delete_pending_since: float | None = None
        self._delete_timer = QTimer(self)
        self._delete_timer.setSingleShot(True)
        self._delete_timer.timeout.connect(lambda: self._cancel_delete("Delete cancelled."))

        # -- left section (L-6) ---------------------------------------------------
        self.player_panel = PlayerPanel()
        self.log_panel = LogPanel()
        self.status_line = StatusLine(self._idle_status)

        log_holder = QWidget()
        log_layout = QVBoxLayout(log_holder)
        log_margins = (14, 6, 14, 8)
        log_layout.setContentsMargins(*log_margins)
        log_layout.addWidget(self.log_panel)

        # L-8: a divider between the player and the log. Drag it to make the log bigger.
        self.left_splitter = GripSplitter(Qt.Orientation.Vertical)
        self.left_splitter.setHandleWidth(6)
        self.left_splitter.setChildrenCollapsible(False)
        self.left_splitter.addWidget(self.player_panel)
        self.left_splitter.addWidget(log_holder)
        self.left_splitter.setStretchFactor(0, 1)  # a bigger window makes the video bigger,
        self.left_splitter.setStretchFactor(1, 0)  # not the log
        self.left_splitter.setSizes([10_000, LOG_HEIGHT + log_margins[1] + log_margins[3]])

        left = QWidget()
        left.setObjectName("leftPanel")
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.left_splitter, 1)
        left_layout.addWidget(self.status_line)

        # -- right section and divider (L-2, L-3, L-4) ----------------------------
        self.folder_panel = FolderPanel()
        self.splitter = GripSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(left)
        self.splitter.addWidget(self.folder_panel)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([650, 350])
        self.setCentralWidget(self.splitter)

        # -- wiring -----------------------------------------------------------------
        self.player_panel.change_source_clicked.connect(self.choose_source)
        self.player_panel.undo_clicked.connect(self.undo)
        self.player_panel.delete_clicked.connect(self.request_delete)
        self.player_panel.skip_clicked.connect(self.next_video)
        self.player_panel.rename_submitted.connect(self.rename_current)
        self.player_panel.rename_mode_changed.connect(self._on_rename_mode)
        self.folder_panel.new_folder_clicked.connect(self.start_new_folder)
        self.folder_panel.create_requested.connect(self.create_new_folder)
        self.folder_panel.new_folder_mode_changed.connect(self._on_new_folder_mode)
        self.player_panel.playback_error.connect(lambda text: self.status_line.show_message(text, "error"))
        self.folder_panel.change_dest_clicked.connect(self.choose_dest)
        self.folder_panel.folder_clicked.connect(self._on_folder_clicked)
        self.folder_panel.filter_changed.connect(self._on_filter_changed)

        self._shortcuts: list[QShortcut] = []
        self._add_shortcuts()

        self.log_panel.set_entries(self.move_log.latest())
        self._restore_settings()
        self._update_action_buttons()
        self.status_line.show_idle()
        self.folder_panel.focus_search()  # S-2: typing a folder name works right away
        QGuiApplication.instance().focusWindowChanged.connect(self._on_focus_window_changed)

    # ======================================================================
    # Keyboard (section 8)
    # ======================================================================
    def _add_shortcuts(self) -> None:
        self._shortcut(["Right"], self.next_video)
        self._shortcut(["Left"], self.previous_video)
        self._shortcut(["Down"], lambda: self.move_cursor(1), auto_repeat=True)
        self._shortcut(["Up"], lambda: self.move_cursor(-1), auto_repeat=True)
        # K-15: ⌥↑ / ⌥↓ (Qt's "Alt" is the Option key on macOS) jump to the top or the bottom.
        self._shortcut(["Alt+Up"], lambda: self.move_cursor(-self.folder_panel.row_count()))
        self._shortcut(["Alt+Down"], lambda: self.move_cursor(self.folder_panel.row_count()))
        self._shortcut(["Return", "Enter"], self.press_enter)
        self._shortcut(["Escape"], self.press_escape)
        # On macOS, Qt's "Ctrl" is the ⌘ key: ⌘Z and ⌘⌫ (⌘ + forward delete also works).
        self._shortcut(["Ctrl+Z"], self.undo)
        self._shortcut(["Ctrl+Backspace", "Ctrl+Del"], self.request_delete)
        # K-12, K-13: browse the destination folders: ⌘↵ opens the folder under the cursor,
        # ⌘↑ goes to the parent folder.
        self._shortcut(["Ctrl+Return", "Ctrl+Enter"], self.open_cursor_folder)
        self._shortcut(["Ctrl+Up"], self.open_parent_folder)
        self._shortcut(["Ctrl+Shift+N"], self.start_new_folder)  # F-8, same key as in Finder

    def _shortcut(self, keys: list[str], slot, auto_repeat: bool = False) -> None:
        for key in keys:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)  # K-1: anywhere in the window
            # K-11: holding Enter must not move a stream of videos, and holding ←/→ must
            # not load dozens of videos, so only ↑/↓ repeat.
            shortcut.setAutoRepeat(auto_repeat)
            shortcut.activated.connect(slot)
            self._shortcuts.append(shortcut)
            # S-5: the search field holds the text cursor but leaves these keys to the window.
            self.folder_panel.search_field.add_command_key(QKeySequence(key))

    def _on_rename_mode(self, editing: bool) -> None:
        if editing:
            self.folder_panel.cancel_new_folder()  # only one text field at a time
        self._on_text_mode(editing, "Type the new name. Enter or OK renames, Esc cancels.")

    def _on_new_folder_mode(self, creating: bool) -> None:
        if creating:
            self.player_panel.cancel_rename()
        self._on_text_mode(creating, "Type the folder name. Enter or Create makes it, Esc cancels.")

    def _on_text_mode(self, editing: bool, prompt: str) -> None:
        # K-9: while the rename or new-folder field is being typed in, keys belong to the
        # text field (there, ⌘Z undoes typing and ⌘⌫ deletes text).
        typing = self.player_panel.editing or self.folder_panel.creating
        for shortcut in self._shortcuts:
            shortcut.setEnabled(not typing)
        if editing:
            self._cancel_delete()
            self.status_line.show_message(prompt, "prompt")
        elif not typing:
            self.status_line.refresh()
            self.folder_panel.focus_search()  # S-2: the text cursor goes back to the search field

    def _cancel_text_edits(self) -> None:
        self.player_panel.cancel_rename()
        self.folder_panel.cancel_new_folder()

    def _on_focus_window_changed(self, focus_window) -> None:
        """S-2: the video is drawn in a window of its own, inside this one. If it ever takes
        the focus, typed letters would go nowhere, so give the focus back to the search field.
        (macOS doesn't focus it, as it ignores input, but some Qt platforms do when it's shown.)"""
        own = self.windowHandle()
        if own is None or focus_window is None or focus_window is own:
            return
        parent = focus_window.parent()
        while parent is not None and parent is not own:
            parent = parent.parent()
        if parent is own:
            own.requestActivate()
            if not (self.player_panel.editing or self.folder_panel.creating):
                self.folder_panel.focus_search()

    def press_escape(self) -> None:
        """Esc cancels a pending delete first, then clears the search, then the folder selection."""
        if self._cancel_delete("Delete cancelled."):
            return
        if self.folder_panel.search_text():
            self.folder_panel.clear_search()  # S-7
            return
        self.clear_selection()

    # ======================================================================
    # Status bar and buttons
    # ======================================================================
    def _idle_status(self) -> tuple[str, str]:
        if self.busy:
            return ("Working…", "prompt")
        if self.source is None:
            return ("Choose a source folder to start.", "muted")
        video = self.current_video
        if video is None:
            return ("No more videos in this folder.", "muted")
        armed = self.folder_panel.armed_name()
        if armed:
            return (f"Click or press Enter on “{armed}” to move {video.name}", "prompt")  # M-12b
        if self.dest is None:
            return ("Choose a destination folder on the right.", "muted")
        return ("Pick a folder: click it, or type its name or use ↑ ↓, then press Enter. "
                "Click or Enter again moves the video.", "muted")

    def _update_action_buttons(self) -> None:
        panel = self.player_panel
        panel.undo_button.setEnabled(bool(self._undo) and not self.busy)
        if self._undo:
            last = self._undo[-1]
            panel.undo_button.setToolTip(f"Undo: bring {last.name} back from {last.place} (⌘Z)")
        else:
            panel.undo_button.setToolTip("Nothing to undo (⌘Z)")
        panel.delete_button.setEnabled(self.current_video is not None and not self.busy)
        self.folder_panel.new_folder_button.setEnabled(self.dest is not None and not self.busy)  # F-8

    # ======================================================================
    # Locations (P-1, F-1, M-5, U-6, N-4)
    # ======================================================================
    def choose_source(self) -> None:
        if self.busy:
            return
        start = str(self.source or Path.home())
        path = QFileDialog.getExistingDirectory(self, "Choose the folder with the videos", start)
        if path:
            self.set_source(Path(path))

    def choose_dest(self) -> None:
        if self.busy:
            return
        start = str(self.dest or self.source or Path.home())
        path = QFileDialog.getExistingDirectory(self, "Choose the folder that holds the destination folders", start)
        if path:
            self.set_dest(Path(path))

    def set_source(self, path: Path, save: bool = True) -> None:
        self._cancel_text_edits()  # R-9, F-12
        self._cancel_delete()  # D-5
        self.folder_panel.clear_armed()  # M-5
        self._undo.clear()  # U-6: Undo always brings videos back into the current source folder
        self.source = path
        self.player_panel.set_source_path(path)
        if save:
            self.settings.setValue("source", str(path))
        self._refresh_folders()  # F-5 depends on the source folder
        error = self._reload_videos()
        self._load_current()
        if error:
            self.status_line.show_message(error, "error")
        else:
            self.status_line.show_idle()

    def set_dest(self, path: Path, save: bool = True, cursor_on: str | None = None) -> None:
        self._cancel_text_edits()  # R-9, F-12
        self._cancel_delete()
        self.folder_panel.clear_armed()  # M-5
        self.folder_panel.clear_search()  # S-7: a new list starts unfiltered
        self.dest = path
        if save:
            self.settings.setValue("dest", str(path))
        error = self._refresh_folders(cursor_on)
        self._update_action_buttons()  # New folder needs a destination (F-8)
        if error:
            self.status_line.show_message(error, "error")
        else:
            self.status_line.show_idle()

    def _refresh_folders(self, cursor_on: str | None = None) -> str | None:
        self.folder_panel.set_root(self.dest)
        error = None
        if self.dest is None:
            self.folder_panel.set_folders([], "Choose a destination folder with the Change button above.")
        else:
            try:
                names = list_folders(self.dest, exclude=self.source)
            except OSError as e:
                self.folder_panel.set_folders([], "This folder can't be read.")
                error = f"✗ Can't read {self.dest}: {e.strerror or e}"
            else:
                self.folder_panel.set_folders(
                    names, "There are no folders inside this folder. ⌘↑ goes back to the parent folder.", cursor_on
                )
        self.folder_panel.set_recent(self._shown_recent())  # F-5 and RF-4 depend on the source folder
        return error

    # -- recently used folders (RF-1..RF-8) ---------------------------------------------
    def _load_recent(self) -> list[Path]:
        value = self.settings.value("recent_folders")
        if isinstance(value, str):  # some settings formats return a one-item list as a string
            value = [value]
        if not isinstance(value, (list, tuple)):
            return []
        return [Path(v) for v in value if isinstance(v, str) and v][:RECENT_KEPT]

    def _shown_recent(self) -> list[Path]:
        """The 5 newest recent folders that still exist, without the source folder (RF-4)."""
        return existing_folders(self.recent, exclude=self.source, limit=RECENT_SHOWN)

    def _remember_folder(self, folder: Path) -> None:
        """RF-3: a video was moved into `folder`, so it goes to the top of the recent folders."""
        self.recent = [folder, *(p for p in self.recent if p != folder)][:RECENT_KEPT]
        self.settings.setValue("recent_folders", [str(p) for p in self.recent])
        self.folder_panel.set_recent(self._shown_recent())

    def open_cursor_folder(self) -> None:
        """⌘↵: the folder under the cursor becomes the destination folder (K-12)."""
        if self.busy or self.dest is None:
            return
        folder = self.folder_panel.cursor_folder()
        if folder is None:
            return
        self.set_dest(folder, cursor_on="")  # start at the top of the new list

    def open_parent_folder(self) -> None:
        """⌘↑: the parent folder becomes the destination folder, with the cursor on the
        folder we came from (K-13)."""
        if self.busy or self.dest is None:
            return
        parent = self.dest.parent
        if parent == self.dest:
            self.status_line.show_message("This is the top folder.", "muted", MESSAGE_MS)
            return
        self.set_dest(parent, cursor_on=self.dest.name)

    # ======================================================================
    # New folder (F-8..F-14)
    # ======================================================================
    def start_new_folder(self) -> None:
        """New folder button or ⌘⇧N: show the name row in the right panel."""
        if self.busy or self.dest is None:
            return
        self.folder_panel.start_new_folder()

    def create_new_folder(self, name: str) -> None:
        if self.busy or self.dest is None:
            return
        try:
            folder = create_folder(self.dest, name)
        except FolderError as e:
            self.status_line.show_message(f"✗ {e}", "error")  # F-11: stay in the row to fix the name
            return
        self.folder_panel.cancel_new_folder()
        # F-13: the list is reloaded with the cursor on the new folder. Like moving the cursor
        # with ↑/↓, this clears the selection (K-6); nothing is moved. The search is cleared
        # so the new folder is in the list (S-7).
        self.folder_panel.clear_armed()
        self.folder_panel.clear_search()
        error = self._refresh_folders(cursor_on=folder.name)
        if error:
            self.status_line.show_message(error, "error")
        else:
            self.status_line.show_message(f"✓ Created folder “{folder.name}”", "ok", MESSAGE_MS)

    def _restore_settings(self) -> None:
        splitter_state = self.settings.value("splitter")
        if splitter_state:
            self.splitter.restoreState(splitter_state)
        left_state = self.settings.value("left_splitter")  # L-8: the log's height
        if left_state:
            self.left_splitter.restoreState(left_state)
        dest = self.settings.value("dest")
        if dest and Path(dest).is_dir():
            self.set_dest(Path(dest), save=False)
        source = self.settings.value("source")
        if source and Path(source).is_dir():
            self.set_source(Path(source), save=False)

    # ======================================================================
    # Videos (P-4, P-10, P-11, K-2, K-3)
    # ======================================================================
    @property
    def current_video(self) -> Video | None:
        return self.videos[self.index] if 0 <= self.index < len(self.videos) else None

    def _reload_videos(self, after: tuple[int, str] | None = None, keep: Video | None = None) -> str | None:
        """Re-read the source folder.

        `keep`: stay on this video if it's still there. `after`: go to the first video
        that sorts after this key, i.e. the next smaller one. Otherwise start at the top.
        """
        if self.source is None:
            self.videos = []
            self.index = 0
            return None
        try:
            self.videos = list_videos(self.source)
        except OSError as e:
            self.videos = []
            self.index = 0
            return f"✗ Can't read {self.source}: {e.strerror or e}"
        if keep is not None:
            for i, video in enumerate(self.videos):
                if video.path == keep.path:
                    self.index = i
                    return None
            after = keep.sort_key
        if after is not None:
            # After the smallest video, start again at the biggest one (M-12, K-3).
            self.index = next((i for i, v in enumerate(self.videos) if v.sort_key > after), 0)
        else:
            self.index = 0
        return None

    def _load_current(self, position_ms: int = 0, autoplay: bool = True) -> None:
        video = self.current_video
        self.player_panel.set_video(video, self.index + 1, len(self.videos))
        if video is not None:
            self.player_panel.play_file(video.path, position_ms, autoplay)
        elif self.source is None:
            self.player_panel.show_message("Choose a source folder to start.")
        else:
            self.player_panel.show_message("No more videos.")  # P-13
        self._update_action_buttons()

    def next_video(self) -> None:
        """→ and Skip: the next smaller video. After the smallest, the biggest (K-3)."""
        self._step_video(1)

    def previous_video(self) -> None:
        """←: the previous (next bigger) video. Before the biggest, the smallest (K-3)."""
        self._step_video(-1)

    def _step_video(self, step: int) -> None:
        """Go round the videos like a carousel (P-11, K-3). The folder selection stays (M-12a, K-4)."""
        if self.busy:
            return
        self._cancel_text_edits()  # R-9, F-12
        self._cancel_delete()  # D-5
        count = len(self.videos)
        if count == 0:
            return
        if self.current_video is None:  # not on a video: start at one end
            self.index = 0 if step > 0 else count - 1
            wrapped = False
        elif count == 1:
            self.status_line.show_message("This is the only video.", "muted", MESSAGE_MS)
            return
        else:
            previous = self.index
            self.index = (previous + step) % count
            wrapped = (self.index < previous) if step > 0 else (self.index > previous)
        self._load_current()
        if wrapped:
            where = "first" if step > 0 else "last"
            self.status_line.show_message(f"↻ Wrapped around to the {where} video.", "muted", MESSAGE_MS)
        else:
            self.status_line.refresh()

    # ======================================================================
    # Folder cursor and selection (section 4, K-5..K-8)
    # ======================================================================
    def move_cursor(self, delta: int) -> None:
        if self.busy:
            return  # K-10
        self._cancel_delete()
        if self.folder_panel.move_cursor(delta):
            self._clear_selection_if_cursor_left()  # K-6
            self.status_line.refresh()

    def _clear_selection_if_cursor_left(self) -> None:
        """K-6: the selection is cleared when the cursor leaves the selected folder. The same
        folder in the other list (recent folders or all folders) counts as the same folder."""
        armed = self.folder_panel.armed_folder()
        if armed is not None and armed != self.folder_panel.cursor_folder():
            self.folder_panel.clear_armed()

    def _on_filter_changed(self) -> None:
        """The search text changed and the cursor moved to the best match (S-4)."""
        if self.busy:
            return  # the folder being moved into stays selected (M-6)
        self._cancel_delete()  # D-5
        self._clear_selection_if_cursor_left()  # K-6
        self.status_line.refresh()

    def press_enter(self) -> None:
        folder = self.folder_panel.cursor_folder()
        if folder is not None:
            self._activate_folder(folder)

    def clear_selection(self) -> None:
        if self.busy:
            return
        self.folder_panel.clear_armed()  # M-5
        self.status_line.show_idle()

    def _on_folder_clicked(self, folder: Path) -> None:
        if self.player_panel.editing or self.folder_panel.creating:
            # R-9, F-12: the click only cancels the typing, so a half-typed name never moves a file.
            what = "Rename" if self.player_panel.editing else "New folder"
            self._cancel_text_edits()
            self.status_line.show_message(f"{what} cancelled.", "muted", MESSAGE_MS)
            return
        self._activate_folder(folder)

    def _activate_folder(self, folder: Path) -> None:
        """One click or one Enter on `folder`, in the folder list or the recent folders
        (M-1..M-4, K-7, RF-6)."""
        if self.busy or self._recently_busy():
            return  # M-14, M-15, K-10
        self._cancel_delete()  # D-5
        if folder == self.folder_panel.armed_folder():
            self._start_move(folder)
            return
        self.folder_panel.set_armed(folder)  # M-1, M-4
        video = self.current_video
        if video is None:
            self.status_line.show_message(f"“{folder.name}” selected. There's no video to move.", "muted")
        else:
            self.status_line.show_message(
                f"Click or press Enter on “{folder.name}” again to move {video.name}", "prompt"
            )

    # ======================================================================
    # File jobs: move, delete and undo all run on a worker thread (M-16)
    # ======================================================================
    def _run_job(self, kind: str, context: tuple, work: Callable[[], Path], message: str) -> None:
        self.busy = True
        self._block_activations_briefly()
        self.player_panel.show_message(message)  # also releases the playing file (M-7)
        self.status_line.show_message(message, "prompt")
        self._update_action_buttons()
        job = FileJob(work)
        job.signals.finished.connect(self._on_job_finished)
        self._job, self._job_kind, self._job_context = job, kind, context
        QThreadPool.globalInstance().start(job)

    def _on_job_finished(self, path: Path | None, error: str | None) -> None:
        kind, context = self._job_kind, self._job_context
        self.busy = False
        self._job, self._job_kind, self._job_context = None, "", ()
        self._block_activations_briefly()
        self.folder_panel.set_moving(False)
        if kind == "move":
            self._finish_move(*context, path, error)
        elif kind == "delete":
            self._finish_delete(*context, path, error)
        elif kind == "undo":
            self._finish_undo(*context, path, error)
        self._update_action_buttons()

    def _recently_busy(self) -> bool:
        return time.monotonic() < self._ignore_activations_until

    def _block_activations_briefly(self) -> None:
        """Ignore folder clicks, Enter and Undo for one double-click interval (M-15).

        Once a folder stays selected (M-12a), a single click moves a video. Without this,
        a double-click on that folder, or a fast Enter-Enter, would move two videos.
        """
        self._ignore_activations_until = time.monotonic() + self._double_click_seconds()

    @staticmethod
    def _double_click_seconds() -> float:
        return max(0.4, QGuiApplication.styleHints().mouseDoubleClickInterval() / 1000)

    def _log(self, source: Path, destination: Path, size: int) -> str | None:
        """Write one line to moves_log.txt and the panel. Returns an error text on failure."""
        try:
            self.log_panel.add_entry(self.move_log.append(source, destination, size))
        except OSError as e:
            return f"couldn't write {self.move_log.path.name}: {e.strerror or e}"
        return None

    def _show_done(self, message: str, log_error: str | None) -> None:
        if log_error:
            self.status_line.show_message(f"{message}, but {log_error}", "error")
        else:
            self.status_line.show_message(message, "ok", MESSAGE_MS)  # M-11

    # -- move (M-6..M-14) ---------------------------------------------------------------------
    def _start_move(self, folder: Path) -> None:
        video = self.current_video
        if video is None:
            self.status_line.show_message("There's no video to move.", "muted", MESSAGE_MS)
            return
        self.folder_panel.set_moving(True)  # M-6
        self._run_job("move", (video, folder), lambda: move_verified(video.path, folder),
                      f"Moving {video.name} → {folder.name}…")

    def _finish_move(self, video: Video, folder: Path, destination: Path | None, error: str | None) -> None:
        if error is not None or destination is None:
            # M-13: show the error and stay on the same video.
            self._reload_videos(keep=video)
            self._load_current()
            self.status_line.show_message(f"✗ {error}", "error")
            return
        log_error = self._log(video.path, destination, video.size)
        self._undo.append(UndoEntry("move", video.path, destination, video.size, folder.name))  # U-1
        # M-12: the next smaller video plays right away. The folder stays selected (M-12a).
        self._reload_videos(after=video.sort_key)
        self._load_current()
        self._remember_folder(folder)  # RF-3
        self.folder_panel.select_search_text()  # S-6
        message = f"✓ Moved {video.name} → {folder.name}"
        if destination.name != video.name:
            message += f" as {destination.name}"  # M-9
        self._show_done(message + " · ⌘Z to undo", log_error)

    # -- delete (section 7) ----------------------------------------------------------------------
    def request_delete(self) -> None:
        """Delete button or ⌘⌫. The first press asks, the second moves the video to the Trash (D-2, D-3)."""
        if self.busy:
            return
        self._cancel_text_edits()
        video = self.current_video
        if video is None:
            self.status_line.show_message("There's no video to delete.", "muted", MESSAGE_MS)
            return
        now = time.monotonic()
        if self._delete_pending_since is None:
            self._delete_pending_since = now
            self.player_panel.set_delete_pending(True)
            self._delete_timer.start(DELETE_CONFIRM_MS)
            self.status_line.show_message(
                f"Press Delete again (or ⌘⌫) to move {video.name} to the Trash. Esc cancels.", "danger"
            )
            return
        if now - self._delete_pending_since < self._double_click_seconds():
            return  # D-3: a double-click doesn't count as a confirmation
        self._cancel_delete()
        self._run_job("delete", (video,), lambda: trash_verified(video.path, self._trash),
                      f"Moving {video.name} to the Trash…")

    def _cancel_delete(self, message: str | None = None) -> bool:
        """Drop a pending delete (D-5). Returns True if one was pending."""
        if self._delete_pending_since is None:
            return False
        self._delete_pending_since = None
        self._delete_timer.stop()
        self.player_panel.set_delete_pending(False)
        if message:
            self.status_line.show_message(message, "muted", MESSAGE_MS)
        return True

    @property
    def delete_pending(self) -> bool:
        return self._delete_pending_since is not None

    def _finish_delete(self, video: Video, trashed: Path | None, error: str | None) -> None:
        if error is not None or trashed is None:
            self._reload_videos(keep=video)
            self._load_current()
            self.status_line.show_message(f"✗ {error}", "error")
            return
        log_error = self._log(video.path, trashed, video.size)  # D-6
        self._undo.append(UndoEntry("delete", video.path, trashed, video.size, "the Trash"))  # U-1
        self._reload_videos(after=video.sort_key)  # D-4: the next video plays, as after a move
        self._load_current()
        self._show_done(f"🗑 Moved {video.name} to the Trash · ⌘Z to undo", log_error)

    # -- undo (section 7) --------------------------------------------------------------------------
    def undo(self) -> None:
        """Undo button or ⌘Z: bring back the last moved or deleted video and play it (U-2, U-3)."""
        if self.busy or self._recently_busy():
            return
        self._cancel_text_edits()
        self._cancel_delete()
        if not self._undo or self.source is None:
            self.status_line.show_message("Nothing to undo.", "muted", MESSAGE_MS)
            return
        entry = self._undo[-1]
        previous = self.current_video
        source = self.source
        self._run_job(
            "undo", (entry, previous),
            lambda: move_verified(entry.current, source, name=entry.original.name),
            f"Bringing {entry.name} back from {entry.place}…",
        )

    def _finish_undo(self, entry: UndoEntry, previous: Video | None, restored: Path | None, error: str | None) -> None:
        if error is not None or restored is None:
            if not os.path.lexists(entry.current):
                self._undo.remove(entry)  # U-5: it can never be undone, e.g. the Trash was emptied
                error = f"{entry.name} is no longer in {entry.place}"
            if previous is not None:
                self._reload_videos(keep=previous)
            else:  # the folder was empty ("No more videos")
                self._reload_videos()
            self._load_current()
            self.status_line.show_message(f"✗ Can't undo: {error}", "error")
            return
        self._undo.remove(entry)
        log_error = self._log(entry.current, restored, entry.size)  # G-3
        # U-3: the restored video becomes the current video and plays from the start.
        self._reload_videos(keep=Video(restored, entry.size))
        self._load_current()
        message = f"↩ Brought {entry.name} back from {entry.place}"
        if restored.name != entry.name:
            message += f" as {restored.name}"  # U-4: never overwrite
        self._show_done(message, log_error)

    # ======================================================================
    # Rename (section 6)
    # ======================================================================
    def rename_current(self, text: str) -> None:
        video = self.current_video
        if video is None or self.busy:
            return
        try:
            new_path = rename_video(video.path, text)
        except RenameError as e:
            self.status_line.show_message(f"✗ {e}", "error")  # R-6: stay in edit mode
            return
        renamed = Video(new_path, video.size)
        self.videos[self.index] = renamed
        position = self.player_panel.position()
        stopped = self.player_panel.is_stopped()
        playing = self.player_panel.is_playing()
        self.player_panel.finish_rename()
        self.player_panel.set_video(renamed, self.index + 1, len(self.videos))
        # R-7: same video, same position and play/pause state. Reload so the player points at the new name.
        self.player_panel.play_file(new_path, 0 if stopped else position, autoplay=playing)
        if stopped:
            self.player_panel.stop()
        self.status_line.show_message(f"✓ Renamed {video.name} → {new_path.name}", "ok", MESSAGE_MS)  # R-8

    # ======================================================================
    # Window
    # ======================================================================
    def closeEvent(self, event) -> None:
        if self.busy:
            self.status_line.show_message("Wait for the file operation to finish before closing.", "error")
            event.ignore()
            return
        self.settings.setValue("splitter", self.splitter.saveState())
        self.settings.setValue("left_splitter", self.left_splitter.saveState())
        self.player_panel.release()
        super().closeEvent(event)
