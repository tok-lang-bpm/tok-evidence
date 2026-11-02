Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: Luxury Airplane

You produce airplanes.
While the base model is always the same, your customer likes to pimp their airplane with fancy interior.
You let them decide between a number of 5 different bars, the number of seats, their color, and the amount of water in the toilets of their plane (you can come up with additional stuff).
After you received the specifications you send the requirements to different teams to manufacture the parts.
E.g. manufacturing the vodka bar is done by the Russian team, the whiskey bar is manufactured by an Irish team.
After receiving the individual bits and pieces, the interior of the plane is assembled, and the plane is sent on a test flight.
During the flight you create a test protocol which is sent to you and the customer.
The plane is delivered to the customer, which has to confirm.
