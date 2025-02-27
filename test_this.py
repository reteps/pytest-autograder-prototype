import pytest

@pytest.mark.points(5)
def test_1(ref, st):
    assert st.fib(6) == ref.fib(6)

@pytest.mark.points(5)
@pytest.mark.name("X is correct")
def test_2(ref, st):
    assert st.x == ref.x

@pytest.mark.points(5)
def test_3(ref, st):
    assert st.fib(8) == ref.fib(8)

@pytest.mark.points(5)
def test_4(ref, st):
    assert st.fib(7) == ref.fib(7)