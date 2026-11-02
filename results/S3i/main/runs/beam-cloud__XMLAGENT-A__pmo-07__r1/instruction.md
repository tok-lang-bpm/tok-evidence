Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

This process begins when a customer searches for a flight, train, or bus ticket.
After selecting the preferred route, date, and time, the customer provides personal information and payment details.
The booking system generates a ticket, which is sent to the customer via email or SMS.
The travel company updates its seat inventory accordingly.
Before travel, the customer may receive reminders and instructions for check-in or boarding.
The process concludes once the customer completes their journey, though post-travel feedback or services may extend it slightly.
