Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Internship

You can enter a topic that interests you, and how much money you want.
You can also enter experience and hobbies.
Several offers will arrive (at arbitrary points in time).
You can accept or deny offers.
As soon as an offer is accepted, all other offers become invalid.
You have to write at least 3 status updates about your internship (every week).
The company has to write 3 status updates about you.
After the internship is finished you can recommend the company to a list of friends (via twitter).
Separate tweets are sent in parallel.
