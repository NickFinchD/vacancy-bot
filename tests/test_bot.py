"""Тесты хранилища и отбора вакансий.

Бот целиком не поднимается: вся логика, которую стоит проверять,
вынесена в чистые функции и в storage.
"""

import pytest

from bot.matcher import MAX_PER_RUN, extract_new, format_salary, format_vacancy
from bot.storage import Storage


@pytest.fixture
def storage(tmp_path):
    return Storage(str(tmp_path / "test.db"))


def test_add_subscription(storage):
    assert storage.add_subscription(1, "python") is True
    assert [s.query for s in storage.list_subscriptions(1)] == ["python"]


def test_add_subscription_is_idempotent(storage):
    """Повторная подписка на тот же запрос не создаёт дубль."""
    assert storage.add_subscription(1, "python") is True
    assert storage.add_subscription(1, "python") is False
    assert len(storage.list_subscriptions(1)) == 1


def test_subscription_query_is_normalized(storage):
    """Регистр и пробелы не должны создавать разные подписки."""
    storage.add_subscription(1, "Python")
    assert storage.add_subscription(1, "  python  ") is False


def test_remove_subscription(storage):
    storage.add_subscription(1, "python")
    assert storage.remove_subscription(1, "python") is True
    assert storage.remove_subscription(1, "python") is False
    assert storage.list_subscriptions(1) == []


def test_subscriptions_are_isolated_per_chat(storage):
    storage.add_subscription(1, "python")
    storage.add_subscription(2, "golang")

    assert [s.query for s in storage.list_subscriptions(1)] == ["python"]
    assert len(storage.all_subscriptions()) == 2


def test_mark_sent_prevents_duplicates(storage):
    storage.mark_sent(1, [100, 200])
    storage.mark_sent(1, [200, 300])  # 200 повторно — не должно упасть

    assert storage.already_sent(1) == {100, 200, 300}


def test_sent_history_is_per_chat(storage):
    storage.mark_sent(1, [100])
    assert storage.already_sent(2) == set()


def test_extract_new_filters_sent():
    vacancies = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert [v["id"] for v in extract_new(vacancies, {2})] == ["1", "3"]


def test_extract_new_respects_limit():
    vacancies = [{"id": str(i)} for i in range(20)]
    assert len(extract_new(vacancies, set())) == MAX_PER_RUN


@pytest.mark.parametrize(
    "salary,expected",
    [
        (None, "з/п не указана"),
        ({"from": 100000, "to": 200000, "currency": "RUR"}, "100 000 – 200 000 ₽"),
        ({"from": 100000, "to": None, "currency": "RUR"}, "от 100 000 ₽"),
        ({"from": None, "to": 200000, "currency": "RUR"}, "до 200 000 ₽"),
        ({"from": None, "to": None, "currency": "RUR"}, "з/п не указана"),
    ],
)
def test_format_salary(salary, expected):
    assert format_salary(salary) == expected


def test_format_vacancy_escapes_html():
    """Название с < и > не должно ломать разметку сообщения."""
    vacancy = {
        "id": "1",
        "name": "Разработчик <C++>",
        "employer": {"name": "ООО «Рога & Копыта»"},
        "area": {"name": "Москва"},
        "salary": None,
    }
    text = format_vacancy(vacancy)

    assert "&lt;C++&gt;" in text
    assert "&amp;" in text
    assert "https://hh.ru/vacancy/1" in text
