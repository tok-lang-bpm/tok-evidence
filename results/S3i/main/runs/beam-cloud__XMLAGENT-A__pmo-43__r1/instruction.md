Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Car Service

The police has a new app to remind you of your car service.
The process is started after a successful service.
When a service is necessary, the system checks if your car is still registered.
If it is registered, you are notified.
If you do not go to the service, you are fined after 30 days.
At the car service facility the mechanic enters the problems of your car for reference.
While you wait (can take several days), you get status updates via email.
You can pay through the app, when the repair is done.
The mechanic enters that the repair was successful and you got your "Pickerl".
The mechanic enters the time for you next service.
