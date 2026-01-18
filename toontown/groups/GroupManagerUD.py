import typing

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD


if typing.TYPE_CHECKING:
    from toontown.uberdog.ToontownUberRepository import ToontownUberRepository


class GroupManagerUD(DistributedObjectGlobalUD):

    air: "ToontownUberRepository"
    Notify = DirectNotifyGlobal.directNotify.newCategory('GroupManagerUD')

    def generate(self):
        super().generate()
        self.Notify.debug("Starting up...")

    def delete(self):
        super().delete()
        self.Notify.info("Shutting down...")