Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

An e-commerce company has a comprehensive order fulfillment process:
When a customer places an order, the system records the order details.
Payment processing begins.
If the payment fails, the customer is notified, and the process ends.
Upon successful payment, the inventory system checks stock availability.
If items are out of stock, a back-order is initiated, and the customer is informed about the delay.
The process continues once the back-order is received and all required items are available in stock.
In-stock items are picked from the warehouse.
Quality control checks are performed on the picked items.
Packaging is done, including gift wrapping if the customer requested it.
Meanwhile, the shipping department prepares shipping documents and labels.
If the order is international, customs documentation is prepared.
Once packaging and shipping documents are ready, the order is dispatched.
The system sends a shipping confirmation to the customer.
After dispatch, the system updates the inventory levels.
A follow-up email for feedback is sent directly after confirming the successful delivery.
If the customer reports any issues upon delivery, a returns process is initiated, which includes:
Sending a return shipping label.
Receiving returned items.
Inspecting returned items.
Processing a refund or replacement.
