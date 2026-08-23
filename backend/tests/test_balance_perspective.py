import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import SplitHistory, SplitType, Transaction, User
from app.routes.transaction_routes import _calculate_balance


class BalancePerspectiveTest(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user_1 = User(email="user1@example.com", amex_account_number="-1")
        self.user_2 = User(email="user2@example.com", amex_account_number="-2")
        self.db.add_all([self.user_1, self.user_2])
        self.db.flush()

    def tearDown(self) -> None:
        self.db.close()

    def test_both_users_see_the_same_equal_split_balance(self) -> None:
        # The odd cent is intentionally assigned to user 1. Recalculating the
        # split from user 2's perspective would produce a one-cent mismatch.
        transaction = Transaction(
            amex_reference="test-1",
            date=date(2026, 8, 23),
            description_raw="Dinner",
            description_normalized="dinner",
            merchant_key="dinner",
            amount="100.01",
            account_number="-1",
            uploaded_by=self.user_1.id,
            synced=True,
            is_custom=False,
        )
        self.db.add(transaction)
        self.db.flush()
        self.db.add(
            SplitHistory(
                transaction_id=transaction.id,
                merchant_key="dinner",
                split_type=SplitType.equal,
                split_for_user_id=self.user_1.id,
            )
        )
        self.db.commit()

        user_1_balance = _calculate_balance(self.db, self.user_1, generate=False)
        user_2_balance = _calculate_balance(self.db, self.user_2, generate=False)

        self.assertEqual(user_1_balance.settlement_amount, 50.0)
        self.assertEqual(user_2_balance.settlement_amount, 50.0)
        self.assertEqual(user_1_balance.settlement_from, "user2")
        self.assertEqual(user_2_balance.settlement_from, "user2")
        self.assertEqual(user_1_balance.settlement_to, "user1")
        self.assertEqual(user_2_balance.settlement_to, "user1")

    def test_percent_split_is_reversed_for_the_other_user(self) -> None:
        transaction = Transaction(
            amex_reference="test-2",
            date=date(2026, 8, 23),
            description_raw="Rent",
            description_normalized="rent",
            merchant_key="rent",
            amount="100.00",
            account_number="-1",
            uploaded_by=self.user_1.id,
            synced=True,
            is_custom=False,
        )
        self.db.add(transaction)
        self.db.flush()
        self.db.add(
            SplitHistory(
                transaction_id=transaction.id,
                merchant_key="rent",
                split_type=SplitType.percent,
                percent_you=75,
                split_for_user_id=self.user_1.id,
            )
        )
        self.db.commit()

        user_1_balance = _calculate_balance(self.db, self.user_1, generate=False)
        user_2_balance = _calculate_balance(self.db, self.user_2, generate=False)

        self.assertEqual(user_1_balance.settlement_amount, 25.0)
        self.assertEqual(user_2_balance.settlement_amount, 25.0)
        self.assertEqual(user_1_balance.settlement_from, "user2")
        self.assertEqual(user_2_balance.settlement_from, "user2")


if __name__ == "__main__":
    unittest.main()
