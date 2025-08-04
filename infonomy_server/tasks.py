import time
from datetime import datetime
from typing import List, Optional
from celery import shared_task
from sqlmodel import Session, select

from infonomy_server.database import engine
from infonomy_server.utils import recompute_inbox_for_context  # your existing matcher helper
from infonomy_server.llm import call_llm  # your wrapper around the child‐LLM


@shared_task(bind=True)
def inspect_task(
    self,
    context_id: int,
    buyer_id: int,
    purchased: Optional[List[int]] = None,
    depth=0,
    breadth=0,
    max_depth=3,
    max_breadth=3,
) -> List[int]:
    """
    1) Load the context & all current InfoOffers
    2) Call LLM to choose offers or ask for a child context
    3) If offers chosen: record them, remove from available, recurse
    4) If child context requested: create it, recompute inbox, wait for offers, recurse
    5) When done: return full list of purchased offer IDs
    TODO: Right now this inspects *all* info offers, we might want to customize that later.
    """
    from models import (
        DecisionContext,
        InfoOffer,
        HumanBuyer,
        SellerMatcher,
        MatcherInbox,
    )
    if purchased is None:
        purchased = []
    
    if depth >= max_depth or breadth >= max_breadth:
        return purchased
    
    session = Session(engine)

    # Load context & buyer
    ctx = session.get(DecisionContext, context_id)
    buyer = session.get(HumanBuyer, buyer_id)

    # 1) Fetch all available InfoOffers for this ctx
    # not sure about whether we should let them re-inspect inspected offers
    # but for now we do not TODO
    offers: List[InfoOffer] = session.exec(
        select(InfoOffer)
        .where(InfoOffer.context_id == context_id)
        .where(InfoOffer.purchased == False)
        .where(InfoOffer.inspected == False)
    ).all()

    if not offers:
        # no more offers to inspect → finish
        return purchased

    # 2) Invoke your LLM with full, private offer data
    #    Here we assume `call_llm` returns (chosen_offer_ids, child_ctx)
    chosen_ids, child_ctx = call_llm(context=ctx, offers=offers, buyer=buyer.default_child_llm)

    for offer in offers:
        offer.inspected = True

    # 3a) If LLM picked any offers → “buy” them
    if chosen_ids:
        for oid in chosen_ids:
            off = session.get(InfoOffer, oid)
            off.purchased = True
        purchased.extend(chosen_ids)
        # # remove those offers from future consideration
        # session.exec(
        #     select(InfoOffer).where(InfoOffer.id.in_(chosen_ids))
        # ).scalars().delete(synchronize_session="fetch")
        session.commit()
        # recurse on the same context
        return inspect_task(
            context_id=context_id,
            buyer_id=buyer_id,
            purchased=purchased,
            depth=depth,
            breadth=breadth + 1,
            max_depth=max_depth,
            max_breadth=max_breadth,
        )

    # 3b) If LLM returned an empty list *but* wants more info
    if child_ctx:
        # create a new DecisionContext row
        session.add(child_ctx)
        session.commit()
        session.refresh(child_ctx)

        # notify sellers via your inbox‑recompute helper
        recompute_inbox_for_context(child_ctx, session)

        # wait (poll) until at least one InfoOffer appears
        while True:
            count = session.exec(
                select(InfoOffer)
                .where(InfoOffer.context_id == child_ctx.id)
                .where(InfoOffer.purchased == False)
            ).count()
            if count > 3:
                break
            time.sleep(5)  # or use a Pub/Sub notification
        # recurse into the child context
        # don't need to include a selection of the offers here,
        # because again we are inspecting all offers
        return inspect_task(
            context_id=child_ctx.id,
            buyer_id=buyer_id,
            purchased=purchased,
            depth=depth + 1,
            breadth=breadth,
            max_depth=max_depth,
            max_breadth=max_breadth,
        )

    # 4) Nothing to buy and no child → we’re done
    return purchased
