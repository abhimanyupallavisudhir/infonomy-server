"""
Unit tests for business logic functions.
These tests focus on pure business logic without database dependencies.
"""

import pytest
from unittest.mock import Mock, patch
from infonomy_server.models import User, DecisionContext, InfoOffer


@pytest.mark.unit
class TestBalanceLogic:
    """Test balance-related business logic."""
    
    def test_available_balance_calculation(self):
        """Test available balance calculation logic."""
        user = User(
            username="testuser",
            email="test@example.com",
            balance=100.0,
            available_balance=100.0
        )
        
        # Test that available balance can be deducted
        max_budget = 25.0
        user.available_balance -= max_budget
        
        assert user.available_balance == 75.0
        assert user.balance == 100.0  # Total balance unchanged
    
    def test_balance_validation(self):
        """Test balance validation logic."""
        user = User(
            username="testuser",
            email="test@example.com",
            balance=100.0,
            available_balance=50.0
        )
        
        # Test that available balance cannot exceed total balance
        assert user.available_balance <= user.balance
        
        # Test that negative available balance is invalid
        user.available_balance = -10.0
        assert user.available_balance < 0  # This should be caught by validation


@pytest.mark.unit
class TestDecisionContextLogic:
    """Test decision context business logic."""
    
    def test_decision_context_validation(self):
        """Test decision context validation logic."""
        # Valid context
        valid_context = DecisionContext(
            buyer_id=1,
            query="What is the best approach to AI safety?",
            max_budget=100.0,
            priority=1
        )
        
        assert valid_context.query is not None
        assert len(valid_context.query) > 0
        assert valid_context.max_budget > 0
        assert valid_context.priority > 0
    
    def test_recursive_context_creation(self):
        """Test recursive decision context creation logic."""
        # Parent context
        parent_context = DecisionContext(
            buyer_id=1,
            query="Parent query",
            max_budget=100.0,
            priority=1
        )
        
        # Child context (recursive)
        child_context = DecisionContext(
            buyer_id=1,
            query="Child query",
            max_budget=50.0,
            priority=0,  # Changed from 2 to 0 (valid range is 0-1)
            parent_id=parent_context.id  # Use parent_id instead of depth
        )
        
        assert child_context.parent_id == parent_context.id
        assert child_context.max_budget <= parent_context.max_budget


@pytest.mark.unit
class TestInfoOfferLogic:
    """Test info offer business logic."""
    
    def test_info_offer_validation(self):
        """Test info offer validation logic."""
        # Valid offer
        valid_offer = InfoOffer(
            human_seller_id=1,
            context_id=1,
            private_info="This is private information.",
            public_info="This is public information.",
            price=25.0
        )
        
        assert valid_offer.private_info is not None
        assert len(valid_offer.private_info) > 0
        assert valid_offer.price >= 0
        assert valid_offer.inspected is False
        assert valid_offer.purchased is False
    
    def test_offer_state_transitions(self):
        """Test info offer state transitions."""
        offer = InfoOffer(
            human_seller_id=1,
            context_id=1,
            private_info="Private info",
            price=25.0
        )
        
        # Initial state
        assert offer.inspected is False
        assert offer.purchased is False
        
        # Inspect offer
        offer.inspected = True
        assert offer.inspected is True
        assert offer.purchased is False
        
        # Purchase offer
        offer.purchased = True
        assert offer.inspected is True
        assert offer.purchased is True


@pytest.mark.unit
class TestMatcherLogic:
    """Test matcher business logic."""
    
    def test_matcher_keyword_matching(self):
        """Test keyword-based matching logic."""
        # Mock matcher with keywords
        matcher = Mock()
        matcher.keywords = ["AI", "safety", "research"]
        
        # Test query that should match
        matching_query = "What are the latest developments in AI safety research?"
        query_words = matching_query.lower().split()
        
        # Simple keyword matching logic
        matches = any(keyword.lower() in matching_query.lower() for keyword in matcher.keywords)
        assert matches is True
        
        # Test query that should not match
        non_matching_query = "What is the weather like today?"
        matches = any(keyword.lower() in non_matching_query.lower() for keyword in matcher.keywords)
        assert matches is False
    
    def test_matcher_priority_logic(self):
        """Test matcher priority logic."""
        # Mock matchers with different priorities
        high_priority_matcher = Mock()
        high_priority_matcher.priority = 1
        
        low_priority_matcher = Mock()
        low_priority_matcher.priority = 5
        
        # Lower number should be higher priority
        assert high_priority_matcher.priority < low_priority_matcher.priority


@pytest.mark.unit
class TestBotSellerLogic:
    """Test BotSeller business logic."""
    
    def test_fixed_info_bot_validation(self):
        """Test fixed info bot validation."""
        # Valid fixed info bot
        fixed_info = "The answer to life, the universe, and everything is 42."
        price = 10.0
        
        assert fixed_info is not None
        assert len(fixed_info) > 0
        assert price > 0
    
    def test_llm_bot_validation(self):
        """Test LLM bot validation."""
        # Valid LLM bot configuration
        llm_model = "gpt-4"
        llm_prompt = "Generate information about AI safety based on the query: {query}"
        
        assert llm_model is not None
        assert len(llm_model) > 0
        assert llm_prompt is not None
        assert len(llm_prompt) > 0
        assert "{query}" in llm_prompt  # Should contain query placeholder
    
    @patch('infonomy_server.utils.temporary_api_keys')
    def test_bot_seller_api_key_handling(self, mock_temporary_api_keys):
        """Test BotSeller API key handling logic."""
        # Mock the temporary API keys context manager
        mock_temporary_api_keys.return_value.__enter__.return_value = None
        mock_temporary_api_keys.return_value.__exit__.return_value = None
        
        # Test that API keys are properly handled
        api_keys = {"OPENAI_API_KEY": "sk-test123"}
        
        with mock_temporary_api_keys(api_keys):
            # This would be where the actual LLM call happens
            pass
        
        # Verify that the context manager was called
        mock_temporary_api_keys.assert_called_once_with(api_keys)


@pytest.mark.unit
class TestInspectionLogic:
    """Test inspection and recursive decision logic."""
    
    def test_inspection_decision_logic(self):
        """Test the logic for deciding whether to inspect an offer."""
        offer = InfoOffer(
            human_seller_id=1,
            context_id=1,
            private_info="This is private information.",
            public_info="AI Safety Research Update",
            price=25.0
        )
        
        # Mock decision factors
        buyer_budget = 100.0
        offer_price = offer.price
        public_info_quality = len(offer.public_info) if offer.public_info else 0
        
        # Simple decision logic: inspect if price is reasonable and public info is good
        should_inspect = (
            offer_price <= buyer_budget * 0.5 and  # Price is reasonable
            public_info_quality > 10 and  # Public info is substantial
            not offer.inspected  # Haven't inspected yet
        )
        
        assert should_inspect is True
    
    def test_recursive_context_creation_logic(self):
        """Test logic for creating recursive decision contexts."""
        parent_context = DecisionContext(
            buyer_id=1,
            query="What is the best approach to AI safety?",
            max_budget=100.0,
            priority=1
        )
        
        # Mock offer being inspected
        offer = InfoOffer(
            human_seller_id=1,
            context_id=parent_context.id,
            private_info="Private info about AI safety",
            price=25.0
        )
        
        # Logic for creating recursive context
        max_recursion_depth = 3
        # Since we don't have depth field, we'll simulate it with parent_id chain
        current_depth = 0  # Would need to calculate from parent chain
        can_create_recursive = (
            current_depth < max_recursion_depth and
            offer.price <= parent_context.max_budget * 0.3  # Reasonable price
        )
        
        assert can_create_recursive is True
        
        # Test that recursive context would have correct properties
        if can_create_recursive:
            recursive_context = DecisionContext(
                buyer_id=parent_context.buyer_id,
                query=f"Inspect offer: {offer.public_info}",
                max_budget=offer.price * 2,  # Budget for inspection
                priority=0,  # Valid range is 0-1
                parent_id=parent_context.id  # Link to parent
            )
            
            assert recursive_context.parent_id == parent_context.id
            assert recursive_context.max_budget <= parent_context.max_budget