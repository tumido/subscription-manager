import gobject

timeout_add = gobject.timeout_add
idle_add = gobject.idle_add
source_remove = gobject.source_remove

__all__ = [timeout_add, idle_add, source_remove]
