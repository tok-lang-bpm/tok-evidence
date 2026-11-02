Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

This process begins when an employee or customer reports an incident, such as a technical issue or workplace safety concern.
The report is logged into a tracking system and assigned to the appropriate team for investigation.
The team gathers necessary information, identifies the cause of the incident, and proposes corrective actions.
The solution is implemented, whether it's a fix, training, or policy change.
After the incident is resolved, a follow-up occurs to ensure that the issue won't recur.
The process ends when the incident report is closed, and all stakeholders are notified.
