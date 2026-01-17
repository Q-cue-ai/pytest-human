"""Example test showcasing pytest-human features"""

import logging
import os
import time

import pytest

from pytest_human.log import get_logger
from pytest_human.tracing import trace_public_api, traced
from tests.examples.external_delivery import ExternalDeliveryService

log = get_logger(__name__)


@traced
def prepare_dough(size: str):
    """Prepares the pizza dough."""
    log.info(f"Kneading {size} dough ball.")
    time.sleep(0.05)
    log.debug("Dough is ready.")
    return f"{size}_dough"


@traced(log_level=logging.DEBUG)
def add_sauce_and_cheese(dough, sauce, cheese):
    """Adds sauce and cheese to the dough."""
    log.info(f"Adding {sauce} sauce and {cheese} cheese.")
    time.sleep(0.02)
    return f"{dough}_with_{sauce}_and_{cheese}"


@traced(suppress_return=True)
def add_toppings(pizza_base, toppings: list):
    """Adds a list of toppings to the pizza."""
    log.info(f"Adding {len(toppings)} toppings...")
    for topping in toppings:
        log.trace(f"Adding {topping}")

    return {"base": pizza_base, "toppings": toppings, "preparation_time": 0.1}


@traced
def bake_pizza(pizza_details):
    """
    Bakes the pizza.
    """
    # Use a standard Python logger; its logs will still be captured
    std_logger = logging.getLogger("kitchen.oven")
    std_logger.info(f"Oven preheated. Baking pizza with {pizza_details['toppings']}")
    time.sleep(0.1)
    std_logger.warning("Onions topping running low, substituting with olives.")
    pizza_details["toppings"][-1] = "olives"
    return f"baked_pizza_with_{'_'.join(pizza_details['toppings'])}"


@traced
def get_current_topping(pizza):
    log = get_logger(__name__)
    log.info("Getting current topping on the pizza")
    return pizza["toppings"]


@pytest.fixture(autouse=True)
def _trace_delivery_service():
    """
    This autouse fixture monkey-patches the external delivery
    service to trace all its public methods.
    """
    with trace_public_api(ExternalDeliveryService):
        yield


@pytest.fixture
def should_fail_test() -> bool:
    """Used to generate failing logs for demo."""
    return "SHOULD_FAIL_TEST" in os.environ


@pytest.fixture
def expected_toppings(should_fail_test: bool) -> list[str]:
    if should_fail_test:
        return ["pepperoni", "mushrooms", "onions"]
    return ["pepperoni", "mushrooms", "olives"]


def test_full_pizza_order_workflow(human, expected_toppings):
    """
    Tests the full workflow from ordering a pizza to delivery,
    showcasing all major pytest-human features.
    """
    human.log.info("Starting new pizza order: 'The Works'")
    order_details = {
        "customer": "Jane Doe",
        "size": "large",
        "toppings": ["pepperoni", "mushrooms", "onions"],
        "address": "123 Main St",
    }
    # Use highlight=True to syntax highlight the order details
    human.log.debug(f"Order details: {order_details}", highlight=True)

    with human.span.info("Phase 1: Preparing Pizza"):
        dough = prepare_dough(order_details["size"])
        pizza_base = add_sauce_and_cheese(dough, "tomato", "mozzarella")

        # Simulate an internal kitchen log being added as an artifact
        kitchen_ticket = f"ORDER 123\n{order_details['size'].upper()} - {order_details['toppings']}"
        human.artifacts.add_log_text(kitchen_ticket, "kitchen_ticket.log", "Kitchen Printer Log")

        with human.span.debug("Adding toppings"):
            pizza_in_progress = add_toppings(pizza_base, order_details["toppings"])

        human.log.info("Preparation complete. Ready for oven.")

    with human.span.info("Phase 2: Baking Pizza"):
        baked_pizza = bake_pizza(pizza_in_progress)

        # This print statement will be captured as stdout
        print(f"KITCHEN_ALARM: Pizza {baked_pizza} is ready!")

    with human.span.info("Phase 3: Delivery"):
        human.log.debug(f"Contacting delivery partner for {order_details['address']}")

        # These methods will be automatically traced by our fixture
        service = ExternalDeliveryService(order_details["address"])
        dispatch_info = service.dispatch_driver(priority=True)
        status = service.get_delivery_status()

        human.log.info(f"Dispatch info: {dispatch_info}", highlight=True)
        human.log.info("Verifying final order on pickup...")
        current_toppings = get_current_topping(pizza_in_progress)

        assert set(current_toppings) == set(expected_toppings), "Toppings mismatch at pickup!"
        human.log.info(f"Delivery status: {status}")

    assert status == "out_for_delivery", "Pizza was not out for delivery!"
