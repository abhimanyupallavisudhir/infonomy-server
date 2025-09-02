# Description

See https://abhimanyu.io/current_writing/metaculus_mockup.html for a full description.

In short: this is an information market platform. Buyers submit queries called "DecisionContexts" to the platform, which are then matched to Sellers (sent to their Inboxes) based on the Sellers' "Matchers". Sellers can post answers called InfoOffers to the DecisionContexts they receive in their Inboxes --- for human sellers they can do so in their own time, while BotSellers are run on the server (they are either a fixed text string or some LLM call). BotSellers must still be associated with a user account.

The key novelty of the system is: the InfoOffers comprise of some "private info" field as well as other public fields. The private info does not immediately become available to the Buyers; instead they must choose to "inspect" the info, which means spinning off an LLM instance to look at the private info and decide whether to buy it. Furthermore the inspecting LLM can create recursive decision contexts to help it make its decision (on whether to buy the piece of information it is inspecting), and inspect those via another spin-off, and so on. In the end, the InfoOffers the LLMs have decided to buy are purchased by the buyer.

# Usage

To start the server:

```python
# create and activate a venv, e.g.
# uv venv
# uv sync
# source .venv/bin/activate

# then in separate terminals
redis-server
celery -A celery_app worker --loglevel=info
fastapi dev infonomy_server/main.py
```

You can use the [infonomy-client](https://github.com/abhimanyupallavisudhir/infonomy-client) library to make requests to the server.

## To-do
### central to the design
- [x] figure out how *InfoOffers* appear as parent of recursive DecisionContexts
- [x] budget enforcement
- [x] implement BotSellers and make sure recursive decision contexts are only visible to bots, sellers who provided original, buyer who's already bought the inspected decision contexts
- [x] add remaining important methods: matcher CRUD, list decision contexts, list decision contexts by user, list InfoOffers by user, 
- [x] make sure inboxes are updated upon creation of new matchers, sellers or botsellers
- [x] make sure rates are correctly counted and maintained
- [x] let users put their API keys
- [x] balances
- [ ] allow llm botsellers to have pre-set prices instead of expecting the LLM to generate a price
- [ ] payments
- [ ] better solution than letting people put their API keys (which allows leakage)
- [ ] allow matchers to filter for only recursive contexts (for botsellers)

### UI improvements
- [x] fix the profile page mess
- [ ] implement inspections properly
- [x] UI for adding API keys
- [ ] check if matchers are correctly posted -- because stuff isn't showing up in the inbox for dingdong@gmail.com
- [ ] matcher deletion, update etc.

### simplificatons made
- [ ] `inspect_task` inspects *all* info offers -- we might want some way to select specific InfoOffers to inspect, ideally via some google ads kinda thing
- [ ] maybe let people other than original buyer also buy info offers
- [ ] let user customize how many infooffers child llm should wait for
- [ ] let DecisionContexts have "title" and "details"
- [ ] recursive answers on answers not bought should not be shown, even if bought

### misc infra
- [x] client library
- [x] logging=True and better handling of LLM API fails
- [ ] better logging of full inspection chain
- [ ] notifications for InfoOffers received and inspections completed
- [x] demo notebook
- [x] demo with a UI maybe
- [ ] tests

### important development
- [ ] transition to PostgreSQL
- [ ] make things async
- [ ] set up alembic 
- [ ] pre-populate with buyers and sellers
- [ ] verified info
- [ ] better flexibility in choosing LLM agents
- [ ] browser extension
- [ ] UI (maybe Q&A like UI)
- [ ] metaculus bot