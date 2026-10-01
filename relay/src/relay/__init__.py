"""TicketTailor outbox relay.

A standalone deployable (ADR-0002) whose poll loop performs two phases per tick
(ADR-0010):

1. Scheduled visibility transition (FR5) - flip club-only events whose
   ``transition_at`` has passed to public, writing a ``visibility_changed``
   outbox row in the same transaction.
2. Outbox publish (ADR-0006) - drain unpublished ``shared.outbox`` rows and
   publish them to the message bus.

Both phases use ``FOR UPDATE SKIP LOCKED`` so multiple relay replicas run safely.
"""
