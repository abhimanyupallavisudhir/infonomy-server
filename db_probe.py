# example script for probing database for things

from infonomy_server.database import engine
from infonomy_server.models import User, BotSeller, MatcherInbox
from sqlmodel import Session, select

# Create a database session
with Session(engine) as session:
    # Find user by username
    user = session.exec(
        select(User).where(User.username == "new@user.a")
    ).first()
    
    if user:
        print(f"Found user: {user.username} (ID: {user.id})")
        
        # Get all bot sellers for this user
        bot_sellers = session.exec(
            select(BotSeller).where(BotSeller.user_id == user.id)
        ).all()
        
        print(f"Bot sellers for {user.username}:")
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
    
    # show inbox corresponding to matcher 6
    inbox = session.exec(
        select(MatcherInbox).where(MatcherInbox.matcher_id == 6)
    ).all()
    print(f"Inbox for matcher 6: {inbox}")
