from django.core.signals import Signal

resource_created = Signal()
resource_changed = Signal(['old_data'])
resource_deleted = Signal()

sourcedata_created = Signal()
sourcedata_moved = Signal()
sourcedata_changed = Signal(['old_data'])
sourcedata_deleted = Signal()

identifier_added = Signal()
identifier_changed = Signal(['old_value'])
identifier_removed = Signal()