import logging
import time


class ExternalDeliveryService:
    """A simulated third-party class we don't own and can't add @traced to."""

    def __init__(self, address):
        self._address = address
        self._driver = "None"
        logging.getLogger("ExternalDeliveryService").info("Service initialized.")

    def dispatch_driver(self, priority=False):
        """Dispatches a driver to the address."""
        logging.getLogger("ExternalDeliveryService").debug("Dispatching...")
        time.sleep(0.05)
        self._driver = "Dave"
        return {"driver_id": "dave-007", "eta_minutes": 15}

    def get_delivery_status(self):
        """Gets the current delivery status."""
        if self._driver == "None":
            return "pending_dispatch"
        return "out_for_delivery"

    def _calculate_route(self):
        return "Route calculated"
