import pytest
from types import SimpleNamespace
from grading_utils import StudentContext

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "points(value): mark test as worth 'value' points",
    )
    config.addinivalue_line(
        "markers", "name(value): mark test with a name"
    )
def pytest_collection_modifyitems(session, config, items):
    for item in items:
        for marker in item.iter_markers(name="points"):
            test_id = marker.args[0]
            item.user_properties.append(("points", test_id))
        for marker in item.iter_markers(name="name"):
            item.user_properties.append(("name", marker.args[0]))

@pytest.fixture
def ref():
    def fib(n):
        if n <= 1:
            return n
        return fib(n-1) + fib(n-2)
    return SimpleNamespace(**{'x': 5, 'fib': fib})

@pytest.fixture(autouse=True, scope='module')
def st():
    """
    This fixture is used to create a context for the student code.
    It will connect to the student's code, and exit when the tests are done.
    """
    ctx = StudentContext()
    ctx.ping()
    yield ctx
    ctx.exit()

