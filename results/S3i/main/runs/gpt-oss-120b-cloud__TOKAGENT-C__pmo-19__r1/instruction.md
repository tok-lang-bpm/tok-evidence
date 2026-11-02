Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Consider a process for purchasing items from an online shop.
The user starts an order by logging in to their account.
Then, the user simultaneously selects the items to purchase and sets a payment method.
Afterward, the user either pays or completes an installment agreement.
After selecting the items, the user chooses between multiple options for a free reward.
Since the reward value depends on the purchase value, this step is done after selecting the items, but it is independent of the payment activities.
Finally, the items are delivered.
The user has the right to return items for exchange.
Every time items are returned, a new delivery is made.
