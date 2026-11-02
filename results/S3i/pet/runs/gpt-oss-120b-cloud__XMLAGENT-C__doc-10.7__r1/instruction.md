Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

The MSPN registers the measurement at the GO. The GO examines the application of the MSPN. The GO rejects the application of the MSPN or the GO confirmes the application of the MSPN. The GO assigns the MSPN. The GO informs the MSPO about the assignment of MSPN. The GO informs the MPO about the assignment of the MSPN. The GO informs the SP about the assignment of MSPN.
