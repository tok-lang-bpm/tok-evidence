Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Service for Your Fridge

Your fridge produces strange noises.
You describe the symptoms, and send them together with the type of fridge to the central fridge service center.
They select a local service facility (which all have their own way of interacting with customers).
The service facility makes an appointment.
They arrive at a random time, and sometimes have to leave without repairing your fridge, because they need additional parts.
After your fridge is repaired, you have to confirm that it is OK again.
You can rate the service facility.
