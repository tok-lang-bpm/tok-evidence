Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

The process of Vacations Request starts when any employee of the organization submits a vacation request. Once the requirement is registered, the request is received by the immediate supervisor of the employee requesting the vacation. The supervisor must approve or reject the request. If the request is rejected, the application is returned to the applicant / employee who can review the rejection reasons. If the request is approved a notification is generated to the Human Resources Representative, who must complete the respective management procedures.
