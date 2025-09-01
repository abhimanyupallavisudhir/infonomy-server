from typing import List, Tuple, Optional
import instructor
from litellm import completion
from pydantic import BaseModel, model_validator
from infonomy_server.models import DecisionContext, InfoOffer, LLMBuyerType, User
from infonomy_server.logging_config import llm_logger, log_llm_call, log_function_call, log_function_return, log_function_error

CLIENT = instructor.from_litellm(completion)


class LLMResponse(BaseModel):
    chosen_offer_ids: Optional[List[int]]
    followup_query: Optional[str]
    followup_query_budget: Optional[float]
    followup_query_human_seller_ids: Optional[List[int]] = None
    followup_query_bot_seller_ids: Optional[List[int]] = None

    @model_validator(mode="before")
    def exactly_one(cls, self):
        assert (self.chosen_offer_ids is not None) != (
            self.followup_query is not None
        ), "Exactly one of chosen_offer_ids or followup_query must be provided"
        assert (self.followup_query is None) == (self.followup_query_budget is None), (
            "Iff followup_query is provided, then followup_query_budget must also be provided"
        )
        assert (self.followup_query is None) == (
            (self.followup_human_seller_ids is None)
            and (self.followup_bot_seller_ids is None)
        ), (
            "Iff followup_query is provided, then followup_human_seller_ids or followup_bot_seller_ids must be provided"
        )

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

You may return either:
- chosen_offer_ids: a list of IDs of the offers you want to purchase, or
- A followup_query and corresponding followup_query_budget: 
a query that you want to ask, if you need further information to make a decision. This query could even be
an empty string or simply "Should I buy this?", if you just want to see if someone can provide some context on the info being
offered. You can also optionally specify followup_query_human_seller_ids or followup_query_bot_seller_ids, e.g. if you want to 
direct the followup query to the specific sellers of the offers you are inspecting. Otherwise your query will be sent to all
sellers in the market.

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
    user: Optional["User"] = None,
) -> Tuple[List[int], Optional["DecisionContext"]]:
    # Log function entry
    log_function_call(llm_logger, "call_llm", {
        "context_id": context.id,
        "offers_count": len(offers),
        "known_info_count": len(known_info),
        "buyer_id": buyer.id,
        "user_id": user.id if user else None,
        "max_budget": context.max_budget,
        "used_budget": sum(io.price for io in known_info)
    })
    
    prompt = buyer.custom_prompt or INSTRUCTIONS
    used_budget = sum(io.price for io in known_info)
    messages = [
        {
            "role": "user",
            "content": prompt.format(
                ctx_str=render_decision_context(context),
                known_info_str=render_info_offers_private(known_info),
                offers_str=render_info_offers_private(offers),
                used_budget=used_budget,
            ),
        },
    ]
    accept = False
    available_ids = set(io.id for io in offers)

    # Use user's API keys if available, otherwise fall back to server defaults
    api_keys = user.api_keys if user and user.api_keys else {}

    # Import the context manager
    from infonomy_server.utils import temporary_api_keys

    while not accept:
        with temporary_api_keys(api_keys):
            import time
            start_time = time.time()
            response = CLIENT.chat.completions.create(
                model=buyer.model,
                response_model=LLMResponse,
                messages=messages,
            )
            end_time = time.time()
            
            # Log LLM call
            log_llm_call(llm_logger, buyer.model, len(str(messages)), 
                        len(str(response)), end_time - start_time, {
                            "context_id": context.id,
                            "buyer_id": buyer.id,
                            "user_id": user.id if user else None,
                            "iteration": "retry" if len(messages) > 1 else "initial"
                        })
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
