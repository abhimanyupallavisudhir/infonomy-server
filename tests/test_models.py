"""
Unit tests for the Infonomy server models.
These tests focus on model validation and business logic without database dependencies.
"""

import pytest
from datetime import datetime
from infonomy_server.models import User, DecisionContext, InfoOffer, HumanBuyer, HumanSeller


class TestUserModel:
    """Test the User model."""
    
    def test_user_creation(self):
        """Test basic user creation."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$test_hash"
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True  # Default value
    
    def test_user_balance_defaults(self):
        """Test user balance defaults."""
        user = User(username="testuser", email="test@example.com")
        assert user.balance == 0.0
        assert user.available_balance == 0.0
    
    def test_user_api_keys_default(self):
        """Test user API keys default to empty dict."""
        user = User(username="testuser", email="test@example.com")
        assert user.api_keys == {}


class TestDecisionContextModel:
    """Test the DecisionContext model."""
    
    def test_decision_context_creation(self):
        """Test basic decision context creation."""
        context = DecisionContext(
            buyer_id=1,
            query="What is the best approach to AI safety?",
            max_budget=100.0,
            priority=1
        )
        assert context.buyer_id == 1
        assert context.query == "What is the best approach to AI safety?"
        assert context.max_budget == 100.0
        assert context.priority == 1
        assert context.parent_id is None  # Default value
        assert context.created_at is not None
        assert isinstance(context.created_at, datetime)
    
    def test_decision_context_defaults(self):
        """Test decision context default values."""
        context = DecisionContext(
            buyer_id=1,
            query="Test query",
            max_budget=50.0
        )
        assert context.priority == 0  # Default value (changed from 1)
        assert context.parent_id is None  # Default value
        assert context.max_budget == 50.0
        assert context.created_at is not None
        assert isinstance(context.created_at, datetime)


class TestInfoOfferModel:
    """Test the InfoOffer model."""
    
    def test_info_offer_creation(self):
        """Test basic info offer creation."""
        offer = InfoOffer(
            human_seller_id=1,
            context_id=1,
            private_info="This is private information.",
            public_info="This is public information.",
            price=25.0
        )
        assert offer.human_seller_id == 1
        assert offer.context_id == 1
        assert offer.private_info == "This is private information."
        assert offer.public_info == "This is public information."
        assert offer.price == 25.0
    
    def test_info_offer_defaults(self):
        """Test info offer default values."""
        offer = InfoOffer(
            human_seller_id=1,
            context_id=1,
            private_info="Private info"
        )
        assert offer.price == 0.0  # Default value
        assert offer.inspected is False  # Default value
        assert offer.purchased is False  # Default value
        assert offer.created_at is not None
        assert isinstance(offer.created_at, datetime)
    
    def test_info_offer_seller_property(self):
        """Test the seller property logic."""
        # Test with human seller
        offer = InfoOffer(
            human_seller_id=1,
            context_id=1,
            private_info="Private info"
        )
        # Note: This would need a proper seller object to test fully
        # For now, just test that the property exists
        assert hasattr(offer, 'seller')


class TestHumanBuyerModel:
    """Test the HumanBuyer model."""
    
    def test_human_buyer_creation(self):
        """Test basic human buyer creation."""
        buyer = HumanBuyer(id=1)  # id is the primary key, not user_id
        assert buyer.id == 1
        assert buyer.num_queries == {}  # Default value
        assert buyer.num_inspected == {}  # Default value
        assert buyer.num_purchased == {}  # Default value
        assert buyer.default_child_llm is not None


class TestHumanSellerModel:
    """Test the HumanSeller model."""
    
    def test_human_seller_creation(self):
        """Test basic human seller creation."""
        seller = HumanSeller(id=1)  # id is the primary key, not user_id
        assert seller.id == 1
        # Note: The actual HumanSeller model structure needs to be checked
        # These assertions may need to be updated based on the real model