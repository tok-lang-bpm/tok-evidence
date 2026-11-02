Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Ordering in an Online Shop  

A customer that logs into an E-Shop system and has to wait for its login confirmation (its credentials are checked by the system).
If the login was successful then the customer can continue to select products, else the shopping experience stops.
After selecting a product the customer has to add it to a shopping cart, save the product and check if every product was already selected.
These steps repeat until all products were selected.
Then the order is finished by the shopping system and simultaneously payment and shipment for the order is prepared.
For the payment the customer has to enter its payment data and has to wait until the bank confirms the payment.
While waiting for the payment confirmation the customer can enter its shipping address (an independent billing address can be entered if the shipping address is not equal to the billing address).
Finally if the address and the payment steps are executed then the order will be finished by the system.
