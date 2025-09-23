from typing import List, Tuple, Optional
import instructor
from litellm import completion
from pydantic import BaseModel, model_validator
from infonomy_server.models import DecisionContext, InfoOffer, LLMBuyerType, User
from infonomy_server.logging_config import llm_logger, log_llm_call, log_function_call, log_function_return, log_function_error

CLIENT = instructor.from_litellm(completion, mode=instructor.Mode.JSON)


class LLMResponse(BaseModel):
    chosen_offer_ids: Optional[List[int]] = None
    followup_query: Optional[str] = None
    followup_query_budget: Optional[float] = None
    followup_query_human_seller_ids: Optional[List[int]] = None
    followup_query_bot_seller_ids: Optional[List[int]] = None

    @model_validator(mode="after")
    def exactly_one(cls, self):
        # Check that exactly one of chosen_offer_ids or followup_query is provided
        has_chosen = self.chosen_offer_ids is not None and len(self.chosen_offer_ids) > 0
        has_followup = self.followup_query is not None and self.followup_query.strip() != ""
        
        if not has_chosen and not has_followup:
            # If both are None/empty, try to provide a helpful error message
            if self.chosen_offer_ids is None and self.followup_query is None:
                raise ValueError("LLM returned a response with all None values. This usually means the LLM didn't follow the JSON format instructions.")
            else:
                raise ValueError("Either chosen_offer_ids or followup_query must be provided")
        if has_chosen and has_followup:
            raise ValueError("Cannot provide both chosen_offer_ids and followup_query")
        
        # If followup_query is provided, followup_query_budget must also be provided
        if has_followup and self.followup_query_budget is None:
            raise ValueError("followup_query_budget must be provided when followup_query is provided")
        
        return self


INSTRUCTIONS = """
You are an LLM "information buyer" employed at an information market --- your job is to inspect
pieces of information that may be relevant to a buyer, and either decide which ones to buy, or
ask a follow-up query that would help you make that decision. This allows information to be inspected
and evaluated (by you) safely, i.e. without letting the buyer have the information until they have
decided to purchase it.

You will be given a *DecisionContext*: some information on what the buyer is doing, to help you understand
what sort of information might be valuable to him. This could be a query he wants an answer to, or some
page he's viewing. Or it may be a recursive decision context --- one created by an LLM just like you,
telling you that it is deciding whether to buy some information and asking a follow-up query.

You will be given a list of *InfoOffers*: these are the pieces of information offered, which you want to evaluate
whether to purchase or not. You must evaluate each based on whether it will be useful enough to the buyer to justify
its price. This means estimating whether you think this information will actually be novel to the buyer, and affect
their decision.

You must respond with a JSON object that contains exactly one of the following:

Option 1 - Choose to buy offers:
{{
  "chosen_offer_ids": [1, 2, 3]  // List of offer IDs you want to purchase
}}

Option 2 - Ask a follow-up question:
{{
  "followup_query": "Your question here",
  "followup_query_budget": 10.0  // Budget for this follow-up query (must be <= max_budget)
}}

You can also optionally include:
- "followup_query_human_seller_ids": [1, 2]  // Specific human sellers to ask
- "followup_query_bot_seller_ids": [3, 4]    // Specific bot sellers to ask

The followup_query could even be an empty string or simply "Should I buy this?", if you just want to see if someone can provide some context on the info being offered.

NOTE: Although we use the term "information", these InfoOffers aren't verified information --- just any string of text, that
any participant in the market can offer. So you should not assume that the information is true or useful, and you should evaluate
it yourself based on what you know and the context provided.

NOTE: the followup_query_budget is taken from your given max_budget, so make sure to set a reasonable value. If you end up spending
all of your budget on follow-up queries, then the results of those queries will be useless as you won't have any budget left to purchase the 
information offered here itself.

-------
DecisionContext:
(if this is a recursive DecisionContext, it will include attributes "parent_context" and "parent_offers" --- i.e. this DecisionContext was
spawned by a buyer deciding whether to buy the parent_offers for parent_context)
-------
{ctx_str}

Budget already spent: {used_budget}

--------
Previously purchased InfoOffers:
(these are already purchased, do not purchase them again)
-------
{known_info_str}

-------
InfoOffers:
-------
{offers_str}

"""


def render_decision_context(ctx: DecisionContext) -> str:
    if ctx.parent_id is None:
        out = {
            # "id": ctx.id,
            "query": ctx.query,
            "context_pages": ctx.context_pages,
        }
    else:
        out = {
            "is_recursive": True,
            "parent_context": render_decision_context(ctx.parent),
            "parent_offers": render_info_offers_private(ctx.parent_offers),
        }
    return str(out)


def render_info_offer_private(io: InfoOffer) -> dict:
    return {
        "id": io.id,
        "human_seller_id": io.human_seller_id,
        "bot_seller_id": io.bot_seller_id,
        "seller_type": io.seller_type,
        "private_info": io.private_info,
        "public_info": io.public_info,
        "price": io.price,
        "created_at": io.created_at.isoformat(),
    }


def render_info_offers_private(offers: List[InfoOffer]) -> str:
    return str([render_info_offer_private(io) for io in offers])


def call_llm(
    context: DecisionContext,
    offers: List[InfoOffer],
    known_info: List[InfoOffer],
    buyer: LLMBuyerType,
    user: User, # Optional["User"] = None,
) -> Tuple[List[int], Optional["DecisionContext"]]:
    # Log function entry
    log_function_call(llm_logger, "call_llm", {
        "context_id": context.id,
        "offers_count": len(offers),
        "known_info_count": len(known_info),
        "buyer": buyer.dict(),
        "user_id": user.id if user else None,
        "max_budget": context.max_budget,
        "used_budget": sum(io.price for io in known_info)
    })
    
    prompt = buyer.custom_prompt
    used_budget = sum(io.price for io in known_info)
    
    formatted_prompt = prompt.format(
        ctx_str=render_decision_context(context),
        known_info_str=render_info_offers_private(known_info),
        offers_str=render_info_offers_private(offers),
        used_budget=used_budget,
    )
    
    messages = [
        {
            "role": "system",
            "content": "You are an information buyer. You MUST respond with valid JSON only. Do not include any text before or after the JSON. The JSON must contain exactly one of the two options specified in the user message."
        },
        {
            "role": "user",
            "content": formatted_prompt,
        },
    ]
    accept = False
    available_ids = set(io.id for io in offers)

    # Use user's API keys. NEED user api keys.
    api_keys = user.api_keys # if user and user.api_keys else {}

    # Import the context manager
    from infonomy_server.utils import temporary_api_keys

    while not accept:
        with temporary_api_keys(api_keys):
            import time
            import os
            start_time = time.time()
            
            # Get all environment variables (within the context manager)
            env_vars = {}
            for key_name, key_value in os.environ.items():
                if key_value and len(key_value) > 12:
                    # Truncate long values for security (show first 8 and last 4 characters)
                    env_vars[key_name] = f"{key_value[:8]}...{key_value[-4:]}"
                else:
                    env_vars[key_name] = key_value
            
            # Prepare messages for logging (truncate content for readability)
            def truncate_content(content, max_length=200):
                if isinstance(content, str) and len(content) > max_length:
                    return content[:max_length] + "..."
                return content
            
            logged_messages = []
            for msg in messages:
                logged_msg = {
                    "role": msg.get("role", "unknown"),
                    "content": truncate_content(msg.get("content", ""))
                }
                logged_messages.append(logged_msg)
            
            try:
                response = CLIENT.chat.completions.create(
                    model=buyer.model,
                    response_model=LLMResponse,
                    messages=messages,
                )
                end_time = time.time()
                
                # Log successful LLM call
                log_llm_call(llm_logger, buyer.model, len(str(messages)), 
                            len(str(response)), end_time - start_time, {
                                "context_id": context.id,
                                "buyer_model": buyer.model,
                                "buyer_name": buyer.name,
                                "user_id": user.id if user else None,
                                "iteration": "retry" if len(messages) > 1 else "initial",
                                "status": "success",
                                "messages": logged_messages,
                                "env_vars": env_vars
                            })
            except Exception as e:
                end_time = time.time()
                
                # Try to get the raw response for debugging
                raw_response = None
                try:
                    # Try to get the raw response from the exception
                    if hasattr(e, 'response') and e.response:
                        raw_response = e.response
                    elif hasattr(e, 'raw_response'):
                        raw_response = e.raw_response
                    elif hasattr(e, 'args') and e.args:
                        # Sometimes the raw response is in the exception args
                        for arg in e.args:
                            if isinstance(arg, dict) and 'choices' in arg:
                                raw_response = arg
                                break
                            elif isinstance(arg, str) and ('{' in arg or '[' in arg):
                                raw_response = arg
                                break
                    
                    # If we still don't have the raw response, try to make a direct call to get it
                    if not raw_response and "validation error" in str(e).lower():
                        try:
                            # Make a direct call without response_model to get the raw response
                            from litellm import completion
                            raw_completion = completion(
                                model=buyer.model,
                                messages=messages,
                                max_tokens=1000,
                                temperature=0.1
                            )
                            raw_response = raw_completion
                        except Exception as direct_call_error:
                            raw_response = f"Failed to get raw response: {str(direct_call_error)}"
                except:
                    pass
                
                # Log failed LLM call
                log_llm_call(llm_logger, buyer.model, len(str(messages)), 
                            0, end_time - start_time, {
                                "context_id": context.id,
                                "buyer_model": buyer.model,
                                "buyer_name": buyer.name,
                                "user_id": user.id if user else None,
                                "iteration": "retry" if len(messages) > 1 else "initial",
                                "status": "failed",
                                "error": str(e),
                                "error_type": type(e).__name__,
                                "raw_response": str(raw_response) if raw_response else None,
                                "messages": logged_messages,
                                "env_vars": env_vars
                            })
                # Re-raise the exception
                raise
        if response.chosen_offer_ids:
            # check that chosen IDs are a subset of available offers
            chosen_ids = set(response.chosen_offer_ids)
            if not chosen_ids.issubset(available_ids):
                messages.append({"role": "assistant", "content": str(response)})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Invalid chosen_offer_ids: {response.chosen_offer_ids}. Must be a subset of available offers.",
                    }
                )
                continue
            # check budget constraint
            total_cost = sum(io.price for io in offers if io.id in chosen_ids)
            if total_cost > context.max_budget - used_budget:
                messages.append({"role": "assistant", "content": str(response)})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Invalid chosen_offer_ids: {response.chosen_offer_ids}. Total cost {total_cost} exceeds max budget {context.max_budget}.",
                    }
                )
                continue
            accept = True
            result = (response.chosen_offer_ids, None)
            log_function_return(llm_logger, "call_llm", {
                "result_type": "chosen_offers",
                "chosen_offer_ids": response.chosen_offer_ids,
                "total_cost": sum(io.price for io in offers if io.id in response.chosen_offer_ids)
            })
            return result
        elif response.followup_query:
            # check followup_query_budget
            if (
                response.followup_query_budget > context.max_budget - used_budget
                or response.followup_query_budget < 0
            ):
                messages.append({"role": "assistant", "content": str(response)})
                messages.append(
                    {
                        "role": "user",
                        "content": f"Invalid followup_query_budget: {response.followup_query_budget}. Must be between 0 and {context.max_budget - used_budget}.",
                    }
                )
                continue
            accept = True
            if response.followup_query_human_seller_ids:
                human_seller_ids = response.followup_query_human_seller_ids
            elif context.human_seller_ids:
                human_seller_ids = context.human_seller_ids
            else:
                human_seller_ids = None
            if response.followup_query_bot_seller_ids:
                bot_seller_ids = response.followup_query_bot_seller_ids
            elif context.bot_seller_ids:
                bot_seller_ids = context.bot_seller_ids
            else:
                bot_seller_ids = None
            # Create a new DecisionContext for the follow-up query
            child_ctx = DecisionContext(
                query=response.followup_query,
                parent_id=context.id,
                context_pages=context.context_pages,  # Copy the context pages from the parent
                buyer_id=context.buyer_id,
                max_budget=response.followup_query_budget,
                human_seller_ids=human_seller_ids,
                bot_seller_ids=bot_seller_ids,
                priority=1,  # intentionally submitted so high priority
            )
            result = (None, child_ctx)
            log_function_return(llm_logger, "call_llm", {
                "result_type": "followup_query",
                "followup_query": response.followup_query,
                "followup_budget": response.followup_query_budget,
                "child_context_id": child_ctx.id if hasattr(child_ctx, 'id') else "new"
            })
            return result
