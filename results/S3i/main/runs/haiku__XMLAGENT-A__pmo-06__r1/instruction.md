Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

This process begins when a customer places an order through an online platform or over the phone.
The system automatically generates an order confirmation and sends it to the customer.
The warehouse team picks and packs the items, and a shipping label is generated.
The order is then handed over to a logistics provider for delivery.
Tracking information is sent to the customer.
The process continues as the shipment is monitored until it reaches the customer's address.
After successful delivery, the process ends, but customer feedback or returns may trigger further actions.
