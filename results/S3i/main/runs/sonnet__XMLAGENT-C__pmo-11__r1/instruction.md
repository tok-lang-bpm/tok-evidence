Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

This process begins when a customer signs up for a subscription service, entering personal and payment information.
The system generates an account, assigns access, and triggers automated billing cycles.
Throughout the subscription, the customer receives regular updates, product enhancements, or renewal notifications.
If the customer decides to cancel, they submit a cancellation request, which the support team processes.
Depending on the terms, any refunds or charges are applied.
The process concludes when the subscription is deactivated by the support team and the final account balance is settled.
