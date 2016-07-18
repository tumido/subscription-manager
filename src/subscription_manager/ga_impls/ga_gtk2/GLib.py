import gobject

timeout_add = gobject.timeout_add
idle_add = gobject.idle_add
MainLoop = gobject.MainLoop

__all__ = [timeout_add, idle_add, MainLoop]
