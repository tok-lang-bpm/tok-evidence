Model the business process described in the text below as one BPMN process.

- Use one pool for the organisation and one lane for each actor (a person, role, department or system) that performs activities. If the text names no actor, use a single lane.
- Every activity of the text becomes a task, named with the words of the text (a verb and its object).
- Use exclusive gateways for decisions and alternatives and parallel gateways for activities that happen at the same time, with a gateway of the same kind where the branches meet.
- Begin with a start event and finish every path with an end event.
- Answer with the complete model only, in one fenced code block marked ```xml.

Text:

Title: Inspection of an Energy Drink Bottling Machine

You develop an application that helps you with the inspection of a machine.
After entering the type of the machine, and its serial number, the inspection can begin:
* Questions are asked, and you have to input values.
* Buttons are to be pressed, and values are automatically collected from the machine and shown to you.
* Depending on the results, additional questions are asked (or not).
