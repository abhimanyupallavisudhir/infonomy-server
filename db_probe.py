# example script for probing database for things

from infonomy_server.database import engine
from infonomy_server.models import User, BotSeller, MatcherInbox, DecisionContext, InfoOffer
from sqlmodel import Session, select

# Create a database session
with Session(engine) as session:
    # Find user by username
    user0 = session.exec(
        select(User).where(User.username == "new_user0")
    ).first()
    user1 = session.exec(
        select(User).where(User.username == "new_user1")
    ).first()

    if user0:
        print(f"Found user: {user0.username} (ID: {user0.id})")

        # Get all DecisionContexts posted by this user
        questions = session.exec(
            select(DecisionContext).where(DecisionContext.buyer_id == user0.id)
        ).all()
        print(f"Questions for {user0.username}:")
        for question in questions:
            print(f"  - ID: {question.id}")
            print(f"  - Query: {question.query}")

        # get InfoOffers to DecisionContext 1
        answers = session.exec(
            select(InfoOffer).where(InfoOffer.context_id == 1)
        ).all()
        print(f"{len(answers)} Answers for DecisionContext 1: {answers}")
        
    if user1:
        print(f"Found user: {user1.username} (ID: {user1.id})")
        
        # Get all bot sellers for this user
        bot_sellers = session.exec(
            select(BotSeller).where(BotSeller.user_id == user1.id)
        ).all()
        
        print(f"Bot sellers for {user1.username}:")
        for bot_seller in bot_sellers:
            print(f"  - ID: {bot_seller.id}")
            print(f"    Type: {bot_seller.type}")
            print(f"    Info: {bot_seller.info}")
            print(f"    Price: {bot_seller.price}")
            print(f"    LLM Model: {bot_seller.llm_model}")
            print(f"    LLM Prompt: {bot_seller.llm_prompt}")
            print(f"    Matchers: {bot_seller.matchers}")
            print("    ---")
    else:
        print("User not found")
    
    # show inbox corresponding to matcher 3
    inbox = session.exec(
        select(MatcherInbox).where(MatcherInbox.matcher_id == 3)
    ).all()
    print(f"Inbox for matcher 3: {inbox}")

    # show inbox corresponding to matcher 4
    inbox = session.exec(
        select(MatcherInbox).where(MatcherInbox.matcher_id == 4)
    ).all()
    print(f"Inbox for matcher 4: {inbox}")

    