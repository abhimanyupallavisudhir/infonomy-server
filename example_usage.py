"""
Example usage of the Recursive Information Market models

This demonstrates how to create recursive DecisionContexts that inspect
specific InfoOffers from their parent context.
"""

from infonomy_server.models import (
    DecisionContext, 
    InfoOffer, 
    DecisionContextParentOffer,
    create_recursive_context,
    User,
    HumanBuyer,
    HumanSeller
)
from sqlmodel import Session, create_engine

# Example database setup (you would use your actual database URL)
# engine = create_engine("sqlite:///example.db")
# SQLModel.metadata.create_all(engine)

def example_usage():
    """
    Example of how to use the recursive context functionality
    """
    
    # This would be your actual database session
    # with Session(engine) as session:
    
    # 1. Create a parent context with some info offers
    parent_context = DecisionContext(
        query="What is the probability of AI alignment success?",
        buyer_id=1,  # Assuming user 1 exists
        max_budget=100.0,
        priority=1
    )
    
    # 2. Create some info offers in the parent context
    offer1 = InfoOffer(
        seller_id=1,
        seller_type="human_seller",
        context_id=parent_context.id,
        private_info="Based on recent papers, I estimate 30% chance of alignment success",
        public_info="Expert opinion on AI alignment",
        price=10.0
    )
    
    offer2 = InfoOffer(
        seller_id=2,
        seller_type="human_seller", 
        context_id=parent_context.id,
        private_info="Historical data shows 15% success rate for similar challenges",
        public_info="Historical analysis",
        price=5.0
    )
    
    # 3. Create a recursive context that inspects specific offers from the parent
    recursive_context = create_recursive_context(
        session=session,
        parent_context=parent_context,
        parent_offer_ids=[offer1.id, offer2.id],  # Inspect both offers
        query="Which of these offers provides the most reliable information?",
        buyer_id=1,
        max_budget=20.0,
        priority=0
    )
    
    # 4. Access the parent offers being inspected
    parent_offers = recursive_context.parent_offers
    print(f"Recursive context is inspecting {len(parent_offers)} offers:")
    for offer in parent_offers:
        print(f"- {offer.public_info} (${offer.price})")
    
    # 5. You can also access the parent context
    print(f"Parent context query: {recursive_context.parent.query}")
    
    # 6. And see all children of the parent context
    print(f"Parent has {len(parent_context.children)} child contexts")

if __name__ == "__main__":
    print("This is an example of the recursive context functionality.")
    print("To run this, you would need to set up a database and create the necessary users/sellers.")
    example_usage() 