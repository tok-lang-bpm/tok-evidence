Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: Robotic Burger Seller near the University of Vienna

The robot receives an order.
It asks whether the customer wants a menu or just the burger.
If he wants a menu, the robot starts preparing the drink, which depending on the size can take a variable amount of time.
While doing so, he asks if you want fries or wedges.
If you want fries, he prepares the fries; if you want wedges, he prepares wedges.
Again the duration varies depending on the size fries/wedges order.
After that, he prepares the burger, and gives you enthusiastic status updates every 30 seconds.
Depending on the number of ingredients, the duration for creating the burger varies.
Your order is delivered via a conveyor belt.
