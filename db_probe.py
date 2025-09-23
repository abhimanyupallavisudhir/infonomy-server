# example script for probing database for things

from infonomy_server.database import engine
from infonomy_server.models import User, BotSeller, MatcherInbox, DecisionContext, InfoOffer, Inspection, SellerMatcher
from sqlmodel import Session, select

# Create a database session
with Session(engine) as session:
    # Find user by username
    user0 = session.exec(
        select(User).where(User.username == "new@user.a")
    ).first()

    if user0:
        print(f"Found user: {user0.username} (ID: {user0.id})")
        print(f"Available balance: {user0.available_balance}")
        print(f"Balance: {user0.balance}")
        print(f"Purchased info offers: {user0.purchased_info_offers}")
    
    # show all matchers
    matchers = session.exec(
        select(SellerMatcher).where(SellerMatcher.human_seller_id == user0.id)
    ).all()
    print(f"Matchers for {user0.username}: {matchers}")

    # show inbox for matcher id=14
    inbox = session.exec(
        select(MatcherInbox).where(MatcherInbox.matcher_id == 14)
    ).all()
    print(f"Inbox for matcher 14: {inbox}")
    
    