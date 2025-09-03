"""
Integration tests for database operations.
These tests use a real database but with proper isolation.
"""

import pytest
from sqlmodel import select
from infonomy_server.models import User, HumanBuyer, HumanSeller, DecisionContext, InfoOffer


@pytest.mark.integration
class TestDatabaseOperations:
    """Test database operations with proper isolation."""
    
    def test_user_creation_and_retrieval(self, test_db):
        """Test creating and retrieving users from database."""
        # Create user
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$test_hash"
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        
        # Retrieve user
        retrieved_user = test_db.get(User, user.id)
        assert retrieved_user is not None
        assert retrieved_user.username == "testuser"
        assert retrieved_user.email == "test@example.com"
    
    def test_decision_context_creation(self, test_db, sample_user, sample_buyer):
        """Test creating decision contexts."""
        context = DecisionContext(
            buyer_id=sample_buyer.id,  # Use id, not user_id
            query="What is the best approach to AI safety?",
            max_budget=100.0,
            priority=1
        )
        test_db.add(context)
        test_db.commit()
        test_db.refresh(context)
        
        # Verify creation
        assert context.id is not None
        assert context.buyer_id == sample_buyer.id
        assert context.query == "What is the best approach to AI safety?"
        assert context.max_budget == 100.0
    
    def test_info_offer_creation(self, test_db, sample_seller, sample_decision_context):
        """Test creating info offers."""
        offer = InfoOffer(
            human_seller_id=sample_seller.id,
            context_id=sample_decision_context.id,
            private_info="This is private information about AI safety.",
            public_info="AI Safety Research Update",
            price=25.0
        )
        test_db.add(offer)
        test_db.commit()
        test_db.refresh(offer)
        
        # Verify creation
        assert offer.id is not None
        assert offer.human_seller_id == sample_seller.id
        assert offer.context_id == sample_decision_context.id
        assert offer.price == 25.0
    
    def test_relationships(self, test_db, sample_user, sample_buyer, sample_seller):
        """Test model relationships."""
        # Refresh to load relationships
        test_db.refresh(sample_user)
        
        # Test buyer relationship
        assert sample_user.buyer_profile is not None
        assert sample_user.buyer_profile.id == sample_user.id
        
        # Test seller relationship
        assert sample_user.seller_profile is not None
        assert sample_user.seller_profile.id == sample_user.id
    
    def test_decision_context_with_offers(self, test_db, sample_decision_context, sample_info_offer):
        """Test decision context with associated offers."""
        # Refresh to get relationships
        test_db.refresh(sample_decision_context)
        
        # Check that the offer is associated with the context
        assert len(sample_decision_context.info_offers) == 1
        assert sample_decision_context.info_offers[0].id == sample_info_offer.id
    
    def test_user_balance_operations(self, test_db, sample_user):
        """Test user balance operations."""
        # Test initial balance
        assert sample_user.balance == 0.0
        assert sample_user.available_balance == 0.0
        
        # Update balance
        sample_user.balance = 100.0
        sample_user.available_balance = 100.0
        test_db.add(sample_user)
        test_db.commit()
        test_db.refresh(sample_user)
        
        # Verify update
        assert sample_user.balance == 100.0
        assert sample_user.available_balance == 100.0
    
    def test_query_operations(self, test_db, sample_buyer, sample_decision_context):
        """Test complex query operations."""
        # Test querying decision contexts by buyer
        contexts = test_db.exec(
            select(DecisionContext).where(DecisionContext.buyer_id == sample_buyer.id)
        ).all()
        
        assert len(contexts) == 1
        assert contexts[0].id == sample_decision_context.id
    
    def test_cascade_operations(self, test_db, sample_user):
        """Test cascade operations (if any are defined)."""
        # This would test any cascade delete/update operations
        # For now, just verify that we can delete a user
        user_id = sample_user.id
        test_db.delete(sample_user)
        test_db.commit()
        
        # Verify deletion
        deleted_user = test_db.get(User, user_id)
        assert deleted_user is None


@pytest.mark.integration
class TestBusinessLogic:
    """Test business logic that involves database operations."""
    
    def test_balance_deduction_logic(self, test_db, sample_user, sample_buyer):
        """Test the balance deduction logic for decision contexts."""
        # Set initial balance
        sample_user.balance = 100.0
        sample_user.available_balance = 100.0
        test_db.add(sample_user)
        test_db.commit()
        
        # Simulate balance deduction for decision context
        max_budget = 25.0
        sample_user.available_balance -= max_budget
        test_db.add(sample_user)
        test_db.commit()
        test_db.refresh(sample_user)
        
        # Verify balance deduction
        assert sample_user.available_balance == 75.0
        assert sample_user.balance == 100.0  # Total balance unchanged
    
    def test_purchase_logic(self, test_db, sample_user, sample_info_offer):
        """Test the purchase logic for info offers."""
        # Set initial balance
        sample_user.balance = 100.0
        test_db.add(sample_user)
        test_db.commit()
        
        # Simulate purchase
        offer_price = sample_info_offer.price
        sample_user.balance -= offer_price
        sample_info_offer.purchased = True
        test_db.add(sample_user)
        test_db.add(sample_info_offer)
        test_db.commit()
        test_db.refresh(sample_user)
        test_db.refresh(sample_info_offer)
        
        # Verify purchase
        assert sample_user.balance == 75.0  # 100 - 25
        assert sample_info_offer.purchased is True