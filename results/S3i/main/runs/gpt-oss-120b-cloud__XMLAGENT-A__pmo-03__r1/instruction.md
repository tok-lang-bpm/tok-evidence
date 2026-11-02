Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

This process begins with monitoring inventory levels in a warehouse or store.
When stock reaches a predefined threshold, an automated alert or manual check signals the need to reorder.
The procurement team then places an order with suppliers, considering factors like cost, delivery time, and supplier reliability.
Once the order is placed, the inventory system updates with expected delivery dates.
Upon receiving the stock, it is inspected for quality, recorded in the system, and placed on shelves or in storage.
The process ends when the inventory levels are updated after the restock is complete.
