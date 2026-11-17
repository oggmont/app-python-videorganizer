# Video File Organizer: Requirements

A desktop app for sorting a large number of videos into folders: watch a video on the
left, click a destination folder on the right, and the video is moved there.

## 1. Window and layout

| ID | Requirement |
|----|-------------|
| L-1 | The app opens filling the whole screen (maximized or full screen). |
| L-2 | The window has two side-by-side sections: **Left** (player, log, status bar) and **Folders** (right). |
| L-3 | A draggable vertical divider between the sections changes their widths. |
| L-4 | Both sections fill the full height of the window, top to bottom. |
| L-5 | Each section has its own button to change its location (source folder / destination root). |
| L-6 | From top to bottom, the left section contains: a top bar with the **Change source folder** button and folder path, the **Undo** and **Delete** buttons, and the current file info; the **rename** row; the **video player** with its controls, a draggable divider, the **move log** (small, L-8), and the **status bar**. The status bar sits inside the left section so the folder list keeps the full window height. |
| L-7 | A mockup of the layout is in [`ui-mockup.png`](ui-mockup.png). |
| L-8 | A draggable horizontal divider sits between the player and the move log. Dragging it makes the log taller or shorter, and the video gets the rest. The log starts at half its original height (G-1). The divider position is remembered between launches (N-4). |

## 2. Player (left section)

| ID | Requirement |
|----|-------------|
| P-1 | A **Change source folder** button opens a folder picker. |
| P-2 | The app lists only the video files directly inside the source folder. Subfolders aren't searched. Hidden files are skipped, including the `._name.mp4` files macOS leaves on external drives. |
| P-3 | Supported extensions: `.mp4`, `.m4v`, `.mov`, `.avi`, `.mkv`, `.wmv`, `.flv`, `.webm`, `.mpg`, `.mpeg`, `.3gp`. Matching ignores upper/lower case. |
| P-4 | Videos are ordered by file size, **biggest first**. Each next video is the next smaller one. |
| P-5 | Only one video is loaded at a time: the first one in that order. |
| P-6 | The video starts playing automatically as soon as it is loaded. |
| P-7 | Controls: **Play/Pause**, **Stop**, **Rewind** (−10 s), **Forward** (+10 s), **Skip** (next video), and a seek bar showing current time and duration. |
| P-8 | When a video reaches the end, it **replays from the start**. It keeps looping until the user presses **Stop**, presses **Skip**, or moves it. |
| P-9 | **Stop** stops playback and keeps the same video loaded. **Play** starts it again. |
| P-10 | The current video changes **only** when (a) it is moved to a folder, (b) the user presses **Skip**, (c) the user presses the **Left/Right** arrow keys (section 8), (d) it is moved to the Trash, or (e) a video is brought back with **Undo** (section 7). |
| P-11 | **Skip** (or **→**) loads the next smaller video. **←** loads the previous one, which is the next bigger. Neither touches the file on disk. The videos go round like a carousel: after the smallest comes the biggest again, and before the biggest comes the smallest (K-3). |
| P-12 | The player shows the current file name, its size, and its position (e.g. `12 / 340`). |
| P-13 | When no videos are left in the source folder, the player shows a clear "No more videos" message. |
| P-14 | If a file can't be decoded, an error appears in the status bar and the user can skip the file. The app must not crash. |

## 3. Folders section (right)

| ID | Requirement |
|----|-------------|
| F-1 | A small **Change destination folder** button opens a folder picker. |
| F-2 | The section lists only the folders directly inside the chosen destination folder, sorted by name. Subfolders aren't searched. |
| F-3 | The list fills the rest of the section's height, below the search field and the recently used folders, and scrolls when there are more folders than fit. |
| F-4 | Hidden folders (names starting with `.`) are not shown. |
| F-5 | If the source folder is one of the listed folders, it is not shown as a destination. |
| F-6 | The list shows two different states. The **keyboard cursor** (moved with ↑/↓) is an outline around the row. The **selected** folder (after a first click or first Enter) is a filled highlight. |
| F-7 | Besides the **Change** button, the folder list can be browsed from the keyboard: **⌘↵** opens a folder, **⌘↑** goes to the parent (K-12, K-13). |
| F-8 | A small **New folder** button sits in the header of the right section, next to **Change** (also **⌘⇧N**, as in Finder). It's disabled until a destination folder is chosen, and while a move, undo or delete is running. |
| F-9 | Pressing it shows a row under the header, with no pop-up: an empty, active name field (placeholder *"Folder name"*), a **Create** button and a **Cancel** button. |
| F-10 | **Enter** or **Create** makes an empty folder with that name inside the destination folder, i.e. next to the folders in the list. |
| F-11 | The name follows the same rules as Rename (R-6). It's rejected when it's empty, contains `/` or `:`, starts with `.`, or matches a folder or file that already exists there (ignoring upper/lower case). The error shows in the status bar and the row stays open to fix the name. An existing folder is never reused or merged. |
| F-12 | **Esc**, **Cancel**, a click on a folder in the list, starting a rename, or changing location closes the row without creating anything. |
| F-13 | After it's created, the row closes and the list reloads with the cursor on the new folder. The search is cleared first, so the new folder is in the list (S-7). The status bar shows *"✓ Created folder “<name>”"* for 5 seconds. As when moving the cursor (K-6), the folder selection is cleared, so the usual **Enter, Enter** then sends the video into the new folder. |
| F-14 | For now the app only creates and names folders: it can't rename or delete them. Creating a folder isn't written to the move log, and Undo doesn't remove it. |

### Search (type to filter)

| ID | Requirement |
|----|-------------|
| S-1 | A search field sits under the header of the right section, above the folders: a magnifying glass, the placeholder *"Type a folder name to filter the list…"*, and a ✕ that clears it. |
| S-2 | The search field always holds the text cursor: at startup, after any click (buttons, lists and the video never take it), and after a rename or a new folder is finished or cancelled. So a folder name can be typed at any moment, without clicking first. |
| S-3 | Typing filters the folder list and the recently used folders as you type. A folder matches when its name contains the text, ignoring upper/lower case and accents (`ano` finds `Año`). In the folder list, names that start with the text come first, then the others, each group in name order. The list's caption says how many match (*"2 OF 22 FOLDERS MATCH"*). With no match, the list says so. |
| S-4 | Each change to the text puts the keyboard cursor on the first match in the folder list (or on the first recent folder, if only those match). As with ↑ / ↓ (K-6), if that isn't the selected folder, the selection is cleared, and **Enter, Enter** moves the video into the match. Clearing the text leaves the cursor on the folder it was on. |
| S-5 | While the search field has the text cursor, the keys of section 8 still work: **← / →** change the video, **↑ / ↓** move the folder cursor, and **Enter**, **Esc**, **⌘Z**, **⌘⌫**, **⌘↵**, **⌘↑** and **⌘⇧N** do what they always do. Letters, numbers, spaces, **⌘A** and **⌘V** edit the text, and **⌫** clears it (S-9). |
| S-6 | After a move, the search text stays and is selected (highlighted). The list stays filtered and the folder stays selected (M-12a), so one **Enter** sends the next video to the same folder, and typing a new name replaces the old text. |
| S-7 | **Esc** clears the search text (a pending delete is cancelled first, and the folder selection is cleared by the next Esc). Changing the destination folder (**Change**, **⌘↵**, **⌘↑**) and creating a folder also clear it. |
| S-8 | The search only changes what is shown. It never creates, renames or moves anything, and it isn't kept between launches. |
| S-9 | **⌫** (delete) in the search field clears the whole text at once, not just the last letter. So do fn ⌫ and ⌥⌫. The list shows all folders again and the cursor stays on its folder (S-4). **⌘⌫** still moves the video to the Trash (D-1). |

### Recently used folders

| ID | Requirement |
|----|-------------|
| RF-1 | Above the folder list, a **Recently used** section shows the 5 folders that videos were most recently moved into, newest first. It's hidden until the first move. |
| RF-2 | It looks different from the folder list: a violet-tinted block with a *"RECENTLY USED"* caption, a violet stripe on the left of each row, and slightly smaller rows. The folder list below it has its own caption, *"ALL FOLDERS · 22"*. |
| RF-3 | After each successful move, that folder goes to the top. Each folder is shown once. Undo and Delete don't change the list. |
| RF-4 | A recent folder that no longer exists (deleted, renamed, or on a drive that isn't connected) is hidden but not forgotten. The app remembers the last 10, so 5 can still be shown. The source folder is never shown (as in F-5). |
| RF-5 | A recent folder can be anywhere, e.g. a subfolder opened with ⌘↵. When it isn't directly inside the destination folder, its row says where it is (*"in Family"*), and its tooltip shows the full path. |
| RF-6 | Recent folders work like the folders in the list: the first click or Enter selects, the second moves, a double-click moves at once (M-1 to M-3), and **⌘↵** opens one (K-12). A folder shown in both sections is one folder: selecting it highlights both rows, and moving the cursor between its two rows keeps it selected. |
| RF-7 | The recently used folders are remembered between launches (N-4). |
| RF-8 | **↑ / ↓** move the cursor through the recently used folders and the folder list as one list: **↑** on the first folder of the list goes up into the recent folders (K-5). |

## 4. Move flow

There are **no pop-up dialogs**. All prompts and alerts appear in the status bar.

| ID | Requirement |
|----|-------------|
| M-1 | **First click** (or first **Enter**) on a folder selects it (highlight). The status bar shows: *"Click or press Enter on `<folder>` again to move `<video>`"*. |
| M-2 | **Second click** (or second **Enter**) on the same selected folder confirms the move. |
| M-3 | A quick **double-click** on a folder moves the video right away, with no separate selection step. Pressing **Enter twice** does the same from the keyboard. |
| M-4 | Clicking a different folder moves the selection to that folder and updates the status bar message. Nothing is moved. |
| M-5 | Only **Esc**, or changing either location, clears the selection. Nothing is moved. Moving or skipping a video does **not** clear it. |
| M-6 | Once the move is confirmed, the folder's color changes to a "moving" state. When the move finishes, it goes back to the normal selected color. |
| M-7 | Before moving, the player stops and releases the file, so the file is not locked. |
| M-8 | The file is moved into the selected folder. This also works when the destination is on another drive. |
| M-9 | If a file with the same name already exists in the destination, it is **never overwritten**. A suffix is added instead (e.g. `name (1).mp4`). |
| M-10 | **Verification:** the file exists in the destination with the same size as the original, and it no longer exists in the source folder. |
| M-11 | On success, the status bar shows *"Moved `<video>` → `<folder>`"*. The message stays for **5 seconds**, or until a new message replaces it. |
| M-12 | Right after a successful move, the next video loads and starts playing. Playback doesn't wait for the 5-second message. If the moved video was the smallest, the next one is the biggest left (P-11), so a skipped video comes round again. |
| M-12a | After a move, and after Skip or **← / →**, the same folder **stays selected**. One click or one **Enter** on it then moves the new video there. This makes it quick to send several videos in a row to the same folder. |
| M-12b | Once the 5-second "Moved" message ends, the status bar goes back to the prompt for the selected folder: *"Click or press Enter on `<folder>` to move `<video>`"*. |
| M-13 | If the move or verification fails, the error appears in the status bar and stays until a new message replaces it. The video stays where it was and the app does not advance. |
| M-14 | Clicks are ignored while a move is in progress, so the same file is never moved twice. |
| M-15 | A double-click, or a fast Enter-Enter, never moves more than one video. This matters once a folder stays selected (M-12a), where a single click already moves a video. After a move starts and after it ends, clicks and Enter on folders are ignored for one double-click interval (about half a second). The same applies to Undo, so a double-click on Undo brings back only one video. |
| M-16 | A move between drives runs in the background, so the window doesn't freeze. The app can't be closed while a move is running. |

## 5. Move log

| ID | Requirement |
|----|-------------|
| G-1 | The left section has a small log panel, below the player controls, listing the latest moves, newest first. It starts at 75 px high, half its original 150 px (about two entries), and scrolls. The divider above it makes it bigger (L-8). |
| G-2 | Each entry shows the time, the file name, and the destination folder name (e.g. `14:32:05  holiday.mp4 → Beach`). If the file was renamed (M-9), the entry shows the new name. |
| G-3 | Every successful move is also added to a text file in the project root: `moves_log.txt`. This includes Undo (a move back to the source folder) and Delete (a move to the Trash). Nothing is ever removed from this file. |
| G-4 | Each line in the file holds: date and time, full source path, full destination path, and file size, separated by tabs. |
| G-5 | At startup, the log panel loads the latest entries (up to 100) from `moves_log.txt`. |
| G-6 | Failed moves are not written to the log. They appear only in the status bar. |

## 6. Rename

The rename row only renames the current video. It never moves the file to another folder.

| ID | Requirement |
|----|-------------|
| R-1 | The left section has a rename row above the player: a text field with the current video's name, a **Change** button, and an **OK** button. |
| R-2 | The text field shows the name without the extension. The extension (e.g. `.mp4`) is shown next to it, can't be edited, and is always kept. |
| R-3 | The text field is read-only by default. **Change** makes it editable and selects the text. **OK** stays disabled until Change is pressed. |
| R-4 | **OK** (or Enter) renames the file in the same source folder. The field becomes read-only again. |
| R-5 | **Esc** while editing cancels the edit and restores the current name. Nothing is renamed. |
| R-6 | The new name is rejected, with an error in the status bar and nothing renamed, when it is empty, unchanged, contains `/` or `:`, starts with `.` (the file would become hidden), or matches a file that already exists in the folder. An existing file is **never overwritten**. A change of upper/lower case only (`clip` → `Clip`) is allowed. |
| R-7 | Renaming keeps the same video loaded. Playback continues from the same position. |
| R-8 | On success, the status bar shows *"Renamed `<old>` → `<new>`"* for 5 seconds, or until a new message replaces it. |
| R-9 | Clicking a folder in the right section, Skip, or changing a location cancels an edit in progress. |
| R-10 | Renames are not written to the move log (section 5), and Undo doesn't reverse them. |

## 7. Undo and delete

Two buttons sit in the top bar of the left section, between the folder path and the video
info: **Undo** and **Delete**.

### Undo (⌘Z)

| ID | Requirement |
|----|-------------|
| U-1 | The app keeps a list of the moves and deletes made since the source folder was chosen. |
| U-2 | **Undo** (or **⌘Z**) reverses the most recent one: the video comes back into the source folder, from its destination folder or from the Trash. Pressing it again reverses the one before, and so on. |
| U-3 | The video that comes back gets its original name and becomes the current video. It plays from the start. The folder selection stays as it was. |
| U-4 | Undo never overwrites. If a file with the original name is back in the source folder, a suffix is added (`name (1).mp4`), as in M-9. The move back is verified like any move (M-10). |
| U-5 | If the video can't be brought back (e.g. it was moved away in Finder, or the Trash was emptied), the status bar shows an error and that step is removed from the list. If the failure might be temporary (e.g. the drive isn't connected), the step stays so it can be tried again. |
| U-6 | The list is cleared when the source folder changes, so Undo always brings videos back into the folder on the left. It isn't kept between launches. |
| U-7 | The button is disabled when there is nothing to undo. Its tooltip names the video and where it will come back from. With nothing to undo, ⌘Z shows *"Nothing to undo."* |
| U-8 | On success the status bar shows *"↩ Brought `<video>` back from `<folder>`"* (or *"from the Trash"*) for 5 seconds. Messages after a move or delete end with *"· ⌘Z to undo"*. |

### Delete (⌘⌫)

| ID | Requirement |
|----|-------------|
| D-1 | **Delete** (or **⌘⌫**; ⌘ + forward delete works too) moves the current video to the **macOS Trash**. The app never deletes a file permanently. |
| D-2 | Delete needs confirmation, without a pop-up. The first press turns the button red (*"Confirm delete"*), and the status bar shows *"Press Delete again (or ⌘⌫) to move `<video>` to the Trash. Esc cancels."* The second press moves the video to the Trash. |
| D-3 | A double-click on the button, or ⌘⌫ pressed twice very quickly, doesn't count as a confirmation. The second press must come at least one double-click interval (about half a second) after the first. |
| D-4 | Before moving, the player releases the file (as in M-7). The app checks that the file left the folder and is in the Trash. Then the next video plays, as after a move (M-12). |
| D-5 | A pending delete is cancelled by **Esc**, after 5 seconds without confirmation, or by any other action: changing video, a folder click or Enter, typing in the search, Undo, Rename, or changing a location. After that, the next press asks again. |
| D-6 | The delete is written to the move log with the path inside the Trash as its destination. The log panel shows it as `name → Trash` in red. |
| D-7 | If the Trash refuses the file (e.g. some network drives have no Trash), an error appears in the status bar and the video stays where it was. It is never deleted permanently. |

## 8. Keyboard controls

The whole sorting flow works from the keyboard: **← / →** to pick a video, **↑ / ↓** or
typing its name to pick a folder, then **Enter, Enter** to move.

| Key | Action |
|-----|--------|
| *letters, numbers* | Typed into the search field: filters the folders (S-1 to S-9). **⌫** clears the whole search. |
| **→** | Next video (next smaller). Same as **Skip**. After the last video, back to the first. |
| **←** | Previous video (next bigger). Before the first video, the last one. |
| **↓** | Move the folder cursor down one row. |
| **↑** | Move the folder cursor up one row. From the top of the folder list, into the recently used folders. |
| **⌥↑** / **⌥↓** | Move the folder cursor to the top / the bottom (K-15). |
| **Enter** (1st) | Select the folder under the cursor. Same as a first click. |
| **Enter** (2nd) | Move the video into the selected folder. Same as a second click. Once a folder is selected, every later Enter moves the current video there. |
| **Esc** | Cancel a pending delete; otherwise clear the search; otherwise clear the folder selection. While renaming or naming a new folder, it cancels that. |
| **⌘↵** | Open the folder under the cursor: its subfolders are listed and it becomes the destination folder (K-12). |
| **⌘↑** | Go to the parent of the destination folder (K-13). |
| **⌘⇧N** | New folder in the list on the right (F-8). |
| **⌘Z** | Undo the last move or delete (U-2). |
| **⌘⌫** | Delete: the first press asks, the second moves the video to the Trash (D-2). |

| ID | Requirement |
|----|-------------|
| K-1 | The keys above work anywhere in the window. The folder list doesn't need focus first. The search field always holds the text cursor (S-2), but it leaves these keys to the app (S-5). |
| K-2 | **← / →** change the playing video. They do not seek inside the video; use the Rewind/Forward buttons for that. |
| K-3 | **← / →** go round like a carousel: at the last video, **→** (or Skip) goes to the first one, and at the first video, **←** goes to the last one. The status bar shows *"↻ Wrapped around to the first video."* (or *last*) for 5 seconds. With only one video they do nothing, and the status bar shows *"This is the only video."* |
| K-4 | **← / →** keep the current folder selection, the same as **Skip** (M-5, M-12a). |
| K-5 | **↑ / ↓** move through the recently used folders and the folder list as one list (RF-8). They stop at the top and bottom; they don't wrap around. The list scrolls to keep the cursor visible. On first load, the cursor is on the first folder of the folder list. |
| K-6 | Moving the cursor away from the selected folder clears the selection (as in M-4). The next **Enter** selects the folder under the cursor. Typing in the search moves the cursor too (S-4). Moving between the two rows of a folder that is both recent and in the list doesn't count (RF-6). |
| K-7 | **Enter** follows the same rules as clicks (M-1 to M-3). There is no time limit between the two presses. |
| K-8 | After a move, the cursor and the selection both stay on the same folder. A single **Enter** sends the next video there too (M-12a). |
| K-9 | While the rename field or the new-folder field is being typed in, arrows, Enter, Esc, ⌘Z and ⌘⌫ belong to the text field (Enter = OK, Esc = cancel, ⌘Z undoes typing, ⌘⌫ deletes text). They don't control videos, folders or files. The search field is different: it holds the text cursor the rest of the time and leaves these keys to the app (S-5). |
| K-10 | Keys pressed while a move, undo or delete is in progress are ignored (as in M-14). |
| K-11 | Holding down a key repeats only **↑ / ↓**. Holding **Enter** doesn't move a stream of videos, and holding **← / →** doesn't skip through dozens of videos. |
| K-12 | **⌘↵** (⌘ + Return) opens the folder under the cursor. Its subfolders replace the list, and it becomes the destination folder: shown in the header and remembered (N-4). The cursor starts at the top. It doesn't select or move anything. |
| K-13 | **⌘↑** goes to the parent of the destination folder, with the cursor on the folder you came from. At the top of the disk it does nothing and the status bar says *"This is the top folder."* |
| K-14 | Like **Change** (M-5), ⌘↵ and ⌘↑ clear the folder selection and the search (S-7), and cancel a pending delete or rename. |
| K-15 | **⌥↑** (Option + ↑) moves the folder cursor to the top: the first recently used folder, or the first folder of the list when there are none (the row where **↑** would stop, K-5). **⌥↓** moves it to the last folder. Like ↑ / ↓, this clears the selection when the cursor leaves the selected folder (K-6). |

## 9. Non-functional

| ID | Requirement |
|----|-------------|
| N-1 | Runs on macOS 13 (Ventura), Intel x86_64, as on the developer's machine. |
| N-2 | Plays common formats (MP4/H.264, H.265, AVI with Xvid/DivX/MJPEG, MKV, WMV) without the user installing extra codecs. |
| N-3 | A large folder (1,000+ files) is listed in under 2 seconds. Listing reads file sizes only, never file contents. |
| N-4 | The app remembers between launches: the last source and destination folders, the recently used folders (RF-7), and the positions of both dividers (L-3, L-8). |
| N-5 | No file is ever deleted permanently: Delete moves videos to the macOS Trash, and Undo can bring them back. Besides moving, trashing and renaming videos, the only thing the app writes to disk is `moves_log.txt` (plus its saved settings, N-4). |
| N-6 | The app can be opened with a double-click in Finder, from `Video File Organizer.app` (built by `make_app.sh`). In the Dock and menu bar it shows its own name and icon, not "Python". |

## 10. Recommended technology

**Python 3.14 + PySide6 (Qt 6.11) with QtMultimedia.**

- Qt 6's multimedia uses a built-in **FFmpeg** backend on macOS. The PySide6 wheels ship
  it, so AVI, MKV, WMV and others play without installing anything else. (Java and
  web/Electron players can't do this; see below.)
- Qt widgets that fit the requirements:
  - `QSplitter` for the resizable dividers.
  - `QListWidget` for the folder list. It reports both single clicks and double-clicks.
  - `QStatusBar.showMessage(text, 5000)` for the 5-second status messages.
  - A small `QListWidget` for the log panel.
  - `QLineEdit.setReadOnly()` for the rename field, and `os.rename` for the rename itself.
  - `QFile.moveToTrash()` for Delete. It uses the same Trash as Finder, including `.Trashes`
    on external drives, and reports where the file landed, which Undo needs.
  - `QShortcut` with `Qt.ApplicationShortcut` for keys that work anywhere in the window (K-1).
    On macOS, Qt's `Ctrl+Z` and `Ctrl+Backspace` are ⌘Z and ⌘⌫.
    It is turned off while the rename field is being edited (K-9).
  - A `QLineEdit` for the search field. It turns down Qt's `ShortcutOverride` request for the
    shortcut keys, so they reach the `QShortcut`s while it has the focus (S-5).
  - `QMediaPlayer.setLoops(QMediaPlayer.Infinite)` for replaying a video until it is stopped.
  - `showMaximized()` / `showFullScreen()` to fill the screen.
- `shutil.move` handles moves between drives. `os.path.getsize` is used for sorting and
  verification.
- **Fallback:** if a specific file won't decode, swap the player for `python-vlc`.
  VLC 3.0.20 is already installed in `/Applications`.

> Note: the default `python3` on this Mac is 3.15, and PySide6 doesn't support it yet.
> Create the virtual environment with `python3.14`, which is already installed.

```sh
python3.14 -m venv .venv
source .venv/bin/activate
pip install PySide6
```

### Why not the alternatives

| Option | Video support on macOS | Verdict |
|--------|-----------------------|---------|
| Java Swing | No video at all. You need JavaFX Media (MP4 only, **no AVI**) or VLCJ (needs VLC and native setup). | Most work, least reliable. |
| JS / Electron | Chromium `<video>` plays MP4/WebM, but **not AVI**, WMV, or most MKV. AVI would need FFmpeg transcoding or a libmpv add-on. | Fine for MP4 only. |
| Python + PySide6 | FFmpeg backend is built in. Handles MP4, AVI, MKV, MOV and WMV. | **Recommended.** |
| Python + python-vlc | VLC plays almost anything. Depends on VLC.app being installed. | Good fallback. |
