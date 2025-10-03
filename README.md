# Description

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

