import logging

from pytest_human.log import get_logger, traced


@traced()
def insert_db(data):
    query = "INSERT INTO flowers (petals) VALUES ('{{1,2,3,4,5}}');"
    logging.info(f"executing {query=}")
    return len(data)


def test_example(human):
    """This test demonstrates pytest-human logging."""
    human.log.info("Established test agent connection")

    with human.log.span.info("Generating sample data"):
        data = [1, 2, 3, 4, 5]
        human.log.info(f"Loaded sample data {data=} {len(data)=}", highlight=True)
        insert_db(data)

        with human.log.span.debug("Validating sample"):
            result = sum(data)
            human.log.debug(f"Sum {result=}", highlight=True)

    assert result == 15
