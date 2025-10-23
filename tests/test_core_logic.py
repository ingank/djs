import pytest
from djs.core.logic import do_something
from djs.core.errors import DomainError

def test_do_something_ok():
    assert do_something(5, mult=2) == 10

def test_do_something_invalid():
    with pytest.raises(DomainError):
        do_something(5, mult=0)
