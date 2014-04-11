from django.core.signals import Signal

resource_created = Signal()
resource_changed = Signal(['old_data'])
resource_deleted = Signal()

request_future_resource_generation = Signal(['when'])

source_created = Signal()
source_moved = Signal()
source_changed = Signal(['old_data'])
source_deleted = Signal()

identifier_added = Signal()
identifier_changed = Signal(['old_value'])
identifier_removed = Signal()