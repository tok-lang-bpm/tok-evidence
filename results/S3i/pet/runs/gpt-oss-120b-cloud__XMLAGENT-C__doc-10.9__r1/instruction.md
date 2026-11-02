Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

The SP / PU / GO request changes to the MPO or the MPO himself causes a change. The MPO reviews the change request. The MPO rejects the change of the measuring point by the SP / PU / GO or the MPO confirmes the request of the SP / PU / GO. The MPO performs the measuring point change. The MPO reports the implementation to the SP / PU / GO or notifies the SP / PU / GO about the failure of the changes.
