Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

The process starts when an employee or department submits a request for an IT solution, such as new software or hardware.
IT assesses the request, checking for compatibility with existing systems and evaluating cost and resource needs.
If approved, IT procures the necessary tools or licenses, installs the solution, and tests it in a controlled environment.
After successful testing, the new solution is rolled out to the requesting department.
Training may be provided, and IT support remains available for troubleshooting.
