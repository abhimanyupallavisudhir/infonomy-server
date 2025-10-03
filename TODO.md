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
- [x] balance logic doesn't seem correct -- check line 480 of tasks.py
- [ ] balance logic still has problems + better handling for the case when the user runs an inspection twice
- [x] fix the very stupid issue of bot sellers posting stuff every time recompute_inbox is called. We need inbox items to be marked as purchased etc.
- [ ] allow llm botsellers to have pre-set prices instead of expecting the LLM to generate a price
- [ ] allow matchers to filter for only recursive contexts (for botsellers)
- [ ] make sure matcher logic is correct
- [ ] allow non-default child LLM buyer
- [ ] add a proper max_breadth logic -- you don't want LLMs asking questions forever; if breadth exceeds then force it to only return IDs

### inspection improvements
- [ ] figure out way to show recursive answers: **recursive answers on answers not bought should not be shown, even if bought**
- [ ] way to access previous recursive info offers in an inspection
- [ ] `inspect_task` inspects *all* info offers -- we might want some way to select specific InfoOffers to inspect, ideally via some google ads kinda thing
- [ ] maybe let people other than original buyer also buy info offers
- [ ] let user customize how many infooffers child llm should wait for

### UI improvements
- [x] fix the profile page mess
- [x] implement inspections properly
- [x] UI for adding API keys
- [x] check if matchers are correctly posted -- because stuff isn't showing up in the inbox for dingdong@gmail.com
- [x] matcher deletion, update etc.
- [ ] better error pages
- [ ] better UI for adding botsellers -- adding pieces of info will be the primary way that people will interact with the system

### simplificatons made
- [ ] let DecisionContexts have "title" and "details"

### misc infra
- [x] client library
- [x] logging=True and better handling of LLM API fails
- [x] better logging of full inspection chain
- [ ] notifications for InfoOffers received and inspections completed
- [x] demo notebook
- [x] demo with a UI maybe
- [ ] tests
- [ ] payments
- [ ] better login system
- [ ] better solution than letting people put their API keys (which allows leakage)

### important development
- [ ] transition to PostgreSQL
- [ ] make things async
- [ ] set up alembic 
- [ ] pre-populate with buyers and sellers
- [ ] verified info
- [ ] better flexibility in choosing LLM agents
- [ ] browser extension
- [x] UI (maybe Q&A like UI)
- [ ] metaculus bot