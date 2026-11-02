Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```tok.

Text:

Title: Chainsaw

You produce custom chainsaws on demand.
Your chainsaws have at least 5 properties such as length of the "guide bar" (Schwertlaenge), chain width, electric or motor chainsaw.
After your customer told you the properties, you can start ordering the parts from various online sources (in parallel).
After the parts arrive you have to do a manual inspection of all parts, and then assemble the parts.
During production, you regularly send updates to your customer.
After producing the first saw you send it to your customer.
If he likes it, the rest of his order are produced.
