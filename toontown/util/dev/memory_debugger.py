import gc
import tracemalloc
import objgraph
import weakref
import time

from direct.directnotify import DirectNotifyGlobal


class MemoryDebugger:
    """
    Debugging class to help find server side memory leaks.
    """
    
    notify = DirectNotifyGlobal.directNotify.newCategory("MemoryDebugger")

    TRACK_WEAK_WARNING_FREQUENCY = 60 * 60  # How many seconds to wait in between warnings for track_weak() calls
    
    def __init__(self):
        self.snapshots = {}
        self.weak_refs = {}
        self.tracking_enabled = False
        self.last_warning = 0  # Last time we warned to the console about track_weak() calls w/o being enabled

    def start(self):
        self.notify.warning("Starting tracemalloc and enabling GC debug.")
        tracemalloc.start()
        gc.set_debug(gc.DEBUG_SAVEALL | gc.DEBUG_LEAK)
        self.tracking_enabled = True

    def is_enabled(self) -> bool:
        return self.tracking_enabled

    def take_snapshot(self, label: str = None):
        label = label or time.strftime('%Y%m%d-%H%M%S')
        self.snapshots[label] = tracemalloc.take_snapshot()
        self.notify.warning(f"Snapshot '{label}' taken.")
        return label

    def compare_snapshots(self, old_label: str, new_label: str, limit=10):
        old = self.snapshots.get(old_label)
        new = self.snapshots.get(new_label)
        if not old or not new:
            self.notify.warning(f"One or both snapshots not found: {old_label}, {new_label}")
            return

        stats = new.compare_to(old, 'lineno')
        self.notify.warning(f"Top {limit} differences between '{old_label}' and '{new_label}':")
        for stat in stats[:limit]:
            self.notify.warning(stat)

    def count_class_instances(self, class_name: str) -> int:
        count = sum(1 for obj in gc.get_objects() if type(obj).__name__ == class_name)
        self.notify.warning(f"Instances of '{class_name}': {count}")
        return count

    def find_uncollectable(self):
        self.notify.warning("Forcing GC collection...")
        gc.collect()
        self.notify.warning(f"Uncollectable objects: {len(gc.garbage)}")
        for obj in gc.garbage:
            self.notify.warning(f" - {repr(obj)}")

    def get_tracking_labels(self) -> list[str]:
        return list(self.weak_refs.keys())

    def track_weak(self, obj, label=None):
        if not self.tracking_enabled and time.time() - self.last_warning > self.TRACK_WEAK_WARNING_FREQUENCY:
            self.notify.warning("Tracking not enabled; call start() first.")
            self.last_warning = time.time()
            return

        label = label or type(obj).__name__
        if label not in self.weak_refs:
            self.weak_refs[label] = weakref.WeakSet()
        self.weak_refs[label].add(obj)
        self.notify.warning(f"Tracking object of type '{label}'")

    def is_tracking_weakrefs_for(self, label):
        return label in self.weak_refs

    def count_tracked_weak(self, label):
        count = len(self.weak_refs.get(label, []))
        self.notify.warning(f"Weak-tracked objects for '{label}': {count}")
        return count

    def show_objgraph_backrefs(self, obj, depth=5, filename="leak_graph.png"):
        self.notify.warning(f"Generating backref graph for object {repr(obj)}")
        objgraph.show_backrefs([obj], filename=filename, max_depth=depth)
        self.notify.warning(f"Graph written to '{filename}'")

    def show_most_common_types(self, limit=20):
        self.notify.warning(f"Most common object types:")
        objgraph.show_most_common_types(limit=limit)
