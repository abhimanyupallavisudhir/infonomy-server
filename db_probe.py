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

    # show all inspections
    inspections = session.exec(
        select(Inspection).where(Inspection.buyer_id == user0.id)
    ).all()
    print(f"Inspections for {user0.username}: {inspections}")
    print(f"Total purchased for inspection 2: {inspections[0].total_purchased}")

    # show all info offers purchased by user0
    info_offers = session.exec(
        select(InfoOffer).where(InfoOffer.id.in_(user0.purchased_info_offers))
    ).all()
    print(f"Info offers purchased by {user0.username}: {info_offers}")