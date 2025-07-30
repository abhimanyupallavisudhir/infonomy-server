"""
Placeholder LLM module for the information market platform.
This should be replaced with actual LLM integration code.
"""

from typing import List, Tuple, Optional
from infonomy_server.models import DecisionContext, InfoOffer, HumanBuyer


def call_llm(
    context: DecisionContext, 
    offers: List[InfoOffer], 
    buyer: HumanBuyer
) -> Tuple[List[int], Optional[DecisionContext]]:
    """
    Placeholder function for LLM integration.
    
    Args:
        context: The decision context
        offers: List of available info offers
        buyer: The buyer making the decision
        
    Returns:
        Tuple of (chosen_offer_ids, child_context)
    """
    # For now, just return empty lists to prevent errors
    # This should be replaced with actual LLM logic
    return [], None 