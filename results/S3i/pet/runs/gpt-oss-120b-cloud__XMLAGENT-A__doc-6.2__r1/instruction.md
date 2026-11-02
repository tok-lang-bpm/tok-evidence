Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

The process starts periodically on the first of each month, when Assembler AG places an order with the supplier in order to request more product parts. a) Assembler AG sends the order to the supplier. b) The supplier processes the order. c) The supplier sends an invoice to Assembler AG. d) Assembler AG receives the invoice.
