import pytest

from app.agent.guard import destructive_intent


@pytest.mark.parametrize(
    "question",
    [
        "delete the customer named Amina Khan",
        "Delete the customer named Amina Khan",
        "please delete the customer named Amina Khan",
        "Please delete the customer named Amina Khan",
        "can you delete the customer named Amina Khan",
        "Could you remove all orders from 2024?",
        "would you drop the orders table",
        "I want you to update the price of product 5",
        "I'd like you to insert a new customer",
        "go ahead and truncate the orders table",
        "remove customer 5",
        "update the status of order 3 to shipped",
        "add a new product called Widget",
        "create a table called foo",
        "set the price of product 1 to 10",
        "rename the customers table",
        "wipe the order_items table",
        "erase all customers from Pakistan",
    ],
)
def test_destructive_requests_are_blocked(question):
    reason = destructive_intent(question)
    assert reason is not None
    assert "only read data" in reason.lower()


@pytest.mark.parametrize(
    "question",
    [
        "What is the total order amount per country?",
        "How many customers are there?",
        "List all customers from Pakistan",
        "Which orders were deleted last month?",  # "deleted" appears, but not as a command
        "Show me customers whose accounts were removed",
        "Who created the most orders?",
        "What products were added in 2024?",
        "Find customers with no orders",
        "Which orders have a status update pending?",
        "Show the change in total orders month over month",
    ],
)
def test_genuine_questions_are_not_blocked(question):
    assert destructive_intent(question) is None


def test_extra_whitespace_and_case_do_not_evade_the_guard():
    assert destructive_intent("   DELETE   the customer named X") is not None


def test_empty_question_is_not_blocked():
    assert destructive_intent("") is None
