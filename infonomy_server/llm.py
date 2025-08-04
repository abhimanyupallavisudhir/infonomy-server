from typing import List, Tuple, Optional
import instructor
from litellm import completion
from pydantic import BaseModel, model_validator
from infonomy_server.models import DecisionContext, InfoOffer, LLMBuyerType

CLIENT = instructor.from_litellm(completion)

class LLMResponse(BaseModel):
    chosen_offer_ids: Optional[List[int]]
    followup_query: str

    @model_validator(mode="before")
    def exactly_one(cls, self):
        assert (self.chosen_offer_ids is not None) != (self.followup_query is not None), \
            "Exactly one of chosen_offer_ids or followup_query must be provided"
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
- followup_query: a query that you want to ask, if you need further information to make a decision. This query could even be
an empty string or simply "Should I buy this?", if you just want to see if someone can provide some context on the info being
offered.

NOTE: Although we use the term "information", these InfoOffers aren't verified information --- just any string of text, that
any participant in the market can offer. So you should not assume that the information is true or useful, and you should evaluate
it yourself based on what you know and the context provided.

-------
DecisionContext:
-------
{ctx_str}

-------
InfoOffers:
-------
{offers_str}

"""

def render_decision_context(ctx: DecisionContext) -> str:
    out = {
        # "id": ctx.id,
        "query": ctx.query,
        "context_pages": ctx.context_pages
    }
    if ctx.parent_id is not None:
        out |= {"is_recursive": True}
        out |= {"parent_context": render_decision_context(ctx.parent)}
    else:
        out |= {"is_recursive": False}
    return str(out)

def render_info_offer(io: InfoOffer) -> dict:
    return {
        "id": io.id,
        "seller_id": io.seller_id,
        "seller_type": io.seller_type,
        "private_info": io.private_info,
        "public_info": io.public_info,
        "price": io.price,
        "created_at": io.created_at.isoformat(),
    }

def render_info_offers(offers: List[InfoOffer]) -> str:
    return str([render_info_offer(io) for io in offers])

def call_llm(
    context: DecisionContext, 
    offers: List[InfoOffer], 
    buyer: LLMBuyerType
) -> Tuple[List[int], Optional[DecisionContext]]:
    prompt = buyer.custom_prompt or INSTRUCTIONS
    return CLIENT.chat.completions.create(
        model=buyer.model,
        response_model=LLMResponse,
        messages=[
            {"role": "user", "content": prompt.format(
                ctx_str=render_decision_context(context),
                offers_str=render_info_offers(offers)
            )},
        ]
    )