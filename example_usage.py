#!/usr/bin/env python3
"""
Example usage of the Recursive Information Market models.

This script demonstrates how to:
1. Create a parent DecisionContext
2. Create InfoOffers in that context
3. Create a recursive DecisionContext that inspects specific parent offers
4. Query the relationships
"""

from sqlmodel import Session, create_engine, select
from infonomy_server.models import (
    User, HumanBuyer, DecisionContext, InfoOffer, HumanSeller,
    create_recursive_decision_context
)

# Create database engine (replace with your actual database URL)
engine = create_engine("sqlite:///example.db", echo=True)

# Create tables
from infonomy_server.models import SQLModel
SQLModel.metadata.create_all(engine)

def main():
    with Session(engine) as session:
        # Create a user and buyer
        user = User(username="example_user")
        session.add(user)
        session.flush()
        
        buyer = HumanBuyer(user_id=user.id)
        session.add(buyer)
        session.flush()
        
        # Create a seller
        seller = HumanSeller(user_id=user.id)
        session.add(seller)
        session.flush()
        
        # Create a parent DecisionContext
        parent_context = DecisionContext(
            buyer_id=buyer.user_id,
            query="What are the latest developments in AI safety?",
            max_budget=100.0,
            priority=1
        )
        session.add(parent_context)
        session.flush()
        
        # Create some InfoOffers in the parent context
        offer1 = InfoOffer(
            seller_id=seller.id,
            seller_type="human_seller",
            context_id=parent_context.id,
            private_info="Recent research shows that large language models can be jailbroken through prompt injection attacks.",
            public_info="AI safety research update",
            price=25.0
        )
        
        offer2 = InfoOffer(
            seller_id=seller.id,
            seller_type="human_seller",
            context_id=parent_context.id,
            private_info="The AI Safety Summit in London resulted in new international agreements on AI regulation.",
            public_info="AI regulation update",
            price=30.0
        )
        
        offer3 = InfoOffer(
            seller_id=seller.id,
            seller_type="human_seller",
            context_id=parent_context.id,
            private_info="OpenAI has released new safety guidelines for their models.",
            public_info="OpenAI safety update",
            price=20.0
        )
        
        session.add_all([offer1, offer2, offer3])
        session.flush()
        
        # Create a recursive DecisionContext that inspects offers 1 and 2
        recursive_context = create_recursive_decision_context(
            session=session,
            parent_context=parent_context,
            parent_offers=[offer1, offer2],
            buyer_id=buyer.user_id,
            query="Which of these AI safety developments are most credible?",
            max_budget=50.0,
            priority=0
        )
        
        # Commit all changes
        session.commit()
        
        # Now let's query the relationships
        print("=== Parent Context ===")
        print(f"ID: {parent_context.id}")
        print(f"Query: {parent_context.query}")
        print(f"Number of offers: {len(parent_context.info_offers)}")
        
        print("\n=== Recursive Context ===")
        print(f"ID: {recursive_context.id}")
        print(f"Parent ID: {recursive_context.parent_id}")
        print(f"Query: {recursive_context.query}")
        print(f"Is recursive: {recursive_context.is_recursive}")
        print(f"Parent offer IDs: {recursive_context.parent_offer_ids}")
        print(f"Number of parent offers being inspected: {len(recursive_context.parent_offers)}")
        
        print("\n=== Parent Offers Being Inspected ===")
        for offer in recursive_context.parent_offers:
            print(f"Offer {offer.id}: {offer.public_info} (${offer.price})")
        
        print("\n=== Inspecting Contexts for Offer 1 ===")
        offer1 = session.get(InfoOffer, offer1.id)
        print(f"Offer {offer1.id} is being inspected by {len(offer1.inspecting_contexts)} contexts")
        for ctx in offer1.inspecting_contexts:
            print(f"  - Context {ctx.id}: {ctx.query}")
        
        # Demonstrate the add_parent_offers method
        print("\n=== Adding another parent offer ===")
        recursive_context.add_parent_offers([offer3])
        session.commit()
        
        print(f"Updated parent offer IDs: {recursive_context.parent_offer_ids}")
        print(f"Updated number of parent offers: {len(recursive_context.parent_offers)}")

if __name__ == "__main__":
    main() 