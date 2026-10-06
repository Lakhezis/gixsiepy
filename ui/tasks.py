# SPDX-FileCopyrightText: 2026 GixsiePy contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Un trabajador para Git; todos los callbacks de UI vuelven al hilo principal."""

from concurrent.futures import ThreadPoolExecutor

from gi.repository import GLib


class TaskRunner:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="git")
        self.busy = False
        self._closed = False

    def submit(self, operation, on_success, on_error):
        if self.busy or self._closed:
            return False
        self.busy = True
        future = self._executor.submit(operation)
        future.add_done_callback(
            lambda completed: GLib.idle_add(self._finish, completed, on_success, on_error)
        )
        return True

    def _finish(self, future, on_success, on_error):
        self.busy = False
        if self._closed:
            return GLib.SOURCE_REMOVE
        try:
            value = future.result()
        except Exception as error:
            on_error(error)
        else:
            on_success(value)
        return GLib.SOURCE_REMOVE

    def close(self):
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)
